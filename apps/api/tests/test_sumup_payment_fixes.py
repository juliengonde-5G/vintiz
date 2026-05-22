"""Tests pour les correctifs paiement SumUp / caisse.

Couvre :
- la normalisation des statuts SumUp (Checkouts vs Transactions/reader) ;
- les cas limites de redaction PCI corrigés (PAN 20+, CVV 5 chiffres,
  header Authorization multi-lignes, sur-match de nombres séparés) ;
- la persistance de la VALEUR de l'enum CashMovementDirection ("in"/"out")
  et non de son NOM ("inflow"/"outflow") que Postgres rejetterait.
"""

import uuid

import pytest

from app.services.sumup_service import _normalize_txn_status, redact_sumup_error


# -- Normalisation des statuts -------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("PAID", "PAID"),
        ("SUCCESSFUL", "PAID"),          # vocabulaire Transactions API (reader)
        ("successful", "PAID"),          # casse indifférente
        ("FAILED", "FAILED"),
        ("EXPIRED", "FAILED"),           # checkout expiré → ne doit pas hang
        ("CANCELLED", "CANCELLED"),
        ("CANCELED", "CANCELLED"),       # orthographe US
        ("PENDING", "PENDING"),
        ("", "PENDING"),
        (None, "PENDING"),
        ("WHATEVER", "PENDING"),
    ],
)
def test_normalize_txn_status(raw, expected):
    assert _normalize_txn_status(raw) == expected


# -- Redaction PCI : cas limites corrigés --------------------------------


def test_redact_pan_unbroken_20_digits():
    """Un run continu de 20+ chiffres (au-dessus de la borne PAN) doit
    quand même être masqué (ancienne regex le laissait fuiter)."""
    out = redact_sumup_error("ref 12345678901234567890 end")
    assert "12345678901234567890" not in out
    assert "<PAN_REDACTED>" in out


def test_redact_does_not_over_match_separated_numbers():
    """Un timestamp en groupes de 2/3 ne doit PAS être pris pour un PAN."""
    text = "at 2026 05 22 12 30 45 999 ok"
    out = redact_sumup_error(text)
    assert out == text  # inchangé


def test_redact_cvv_five_digits_fully_redacted():
    """Une valeur CVV malformée à 5 chiffres ne doit pas laisser fuiter
    le 5e chiffre (ancienne regex \\d{3,4})."""
    out = redact_sumup_error("card refused cvv: 12345 x")
    assert "12345" not in out
    assert "1234" not in out


def test_redact_auth_header_does_not_swallow_next_line():
    """La classe valeur du header Authorization ne doit pas avaler le
    retour-ligne et la ligne de diagnostic suivante."""
    text = "Authorization: Basic dXNlcjpwYXNz\nstatus: 401 detail"
    out = redact_sumup_error(text)
    assert "dXNlcjpwYXNz" not in out          # secret masqué
    assert "status: 401 detail" in out         # ligne suivante préservée


def test_redact_formatted_pan_still_masked():
    """Régression : un PAN groupé 4-4-4-4 reste masqué."""
    out = redact_sumup_error("card 4111 1111 1111 1111 invalid")
    assert "4111 1111" not in out


# -- Enum CashMovementDirection : valeur stockée -------------------------


@pytest.mark.anyio
async def test_cash_movement_direction_stores_value_not_name():
    """SQLAlchemy doit persister la VALEUR de l'enum ("out"), pas son NOM
    ("outflow"). Sur Postgres le type n'accepte que "in"/"out" (migration
    0035) → sans values_callable chaque mouvement de caisse ferait un 500.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base
    from app.models.cash_movement import (
        CashMovement,
        CashMovementDirection,
        CashMovementReason,
    )

    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(c, tables=[CashMovement.__table__])
        )
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as s:
        s.add(
            CashMovement(
                drawer_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                direction=CashMovementDirection.outflow,
                reason=CashMovementReason.bank_deposit,
                amount=50.0,
            )
        )
        await s.commit()
        raw = (
            await s.execute(text("SELECT direction FROM cash_movements"))
        ).scalar_one()
    await eng.dispose()

    assert raw == "out"
