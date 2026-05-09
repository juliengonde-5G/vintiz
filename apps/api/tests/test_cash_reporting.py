"""Tests pour cash_reporting.py — anticipation COSI TRACFIN (audit C11).

Vérifie que le service agrège correctement les flux espèces sur un mois
calendaire et déclenche l'alerte au seuil 10 000 € (CMF L.561-15-1).
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.cash_movement import (
    CashMovement,
    CashMovementDirection,
    CashMovementReason,
)
from app.models.client import (
    AvoirTransaction,
    Client,
    Consent,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.pos import (
    CashDrawer,
    Payment,
    PaymentMethod,
    Receipt,
    Transaction,
    TransactionItem,
    TransactionType,
    ZReport,
)
from app.models.product import Category, Product, ProductPhoto
from app.models.user import User, UserRole
from app.services.cash_reporting import (
    COSI_THRESHOLD_EUR,
    cash_volume_for_month,
    cash_volume_last_n_months,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Category.__table__,
        Product.__table__,
        ProductPhoto.__table__,
        Client.__table__,
        Consent.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        Payment.__table__,
        Receipt.__table__,
        CashDrawer.__table__,
        ZReport.__table__,
        CashMovement.__table__,
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        AvoirTransaction.__table__,
    ]
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


async def _seed_user_and_drawer(session) -> tuple[User, CashDrawer]:
    user = User(
        username="manager",
        email="m@v.fr",
        password_hash="x" * 60,
        role=UserRole.manager,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    drawer = CashDrawer(
        user_id=user.id,
        opened_at=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        opening_amount=100.0,
        is_open=True,
    )
    session.add(drawer)
    await session.flush()
    return user, drawer


async def _add_cash_sale(session, user_id, when: datetime, amount: float, txn_no: int):
    sale = Transaction(
        transaction_number=txn_no,
        transaction_type=TransactionType.sale,
        user_id=user_id,
        total_ht=amount * 0.8333,
        total_tva=amount * 0.1667,
        total_ttc=amount,
        hash_chain=f"hash-sale-{txn_no}",
        created_at=when,
    )
    session.add(sale)
    await session.flush()
    session.add(Payment(
        transaction_id=sale.id,
        method=PaymentMethod.cash,
        amount=amount,
    ))
    await session.flush()
    return sale


async def _add_cash_refund(session, user_id, when: datetime, amount: float, txn_no: int):
    rfd = Transaction(
        transaction_number=txn_no,
        transaction_type=TransactionType.refund,
        user_id=user_id,
        total_ht=-amount * 0.8333,
        total_tva=-amount * 0.1667,
        total_ttc=-amount,
        hash_chain=f"hash-refund-{txn_no}",
        created_at=when,
    )
    session.add(rfd)
    await session.flush()
    session.add(Payment(
        transaction_id=rfd.id,
        method=PaymentMethod.cash,
        amount=amount,
    ))
    await session.flush()
    return rfd


async def _add_movement(
    session,
    user_id,
    drawer_id,
    when: datetime,
    direction: CashMovementDirection,
    reason: CashMovementReason,
    amount: float,
):
    mv = CashMovement(
        drawer_id=drawer_id,
        direction=direction,
        amount=amount,
        reason=reason,
        user_id=user_id,
        created_at=when,
    )
    session.add(mv)
    await session.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_empty_month_returns_zero(session):
    """Aucune transaction → tout à zéro, pas d'alerte."""
    await _seed_user_and_drawer(session)
    res = await cash_volume_for_month(session, year=2026, month=5)

    assert res["sales_cash_eur"] == 0.0
    assert res["refunds_cash_eur"] == 0.0
    assert res["bank_deposits_eur"] == 0.0
    assert res["net_eur"] == 0.0
    assert res["above_cosi_threshold"] is False
    assert res["alert_message"] is None
    assert res["cosi_threshold_eur"] == float(COSI_THRESHOLD_EUR)


@pytest.mark.anyio
async def test_aggregates_only_target_month(session):
    """Seules les txs du mois ciblé comptent — bordures incluses."""
    user, _drawer = await _seed_user_and_drawer(session)

    # Avant (avril) — exclus
    await _add_cash_sale(session, user.id,
        datetime(2026, 4, 30, 23, 30, tzinfo=timezone.utc), 200.0, 1)
    # Premier jour du mois ciblé (05/2026)
    await _add_cash_sale(session, user.id,
        datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc), 50.0, 2)
    # Au milieu
    await _add_cash_sale(session, user.id,
        datetime(2026, 5, 15, 14, 0, tzinfo=timezone.utc), 75.0, 3)
    # Dernière seconde du mois — incluse
    await _add_cash_sale(session, user.id,
        datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc), 25.0, 4)
    # Mois suivant — exclus
    await _add_cash_sale(session, user.id,
        datetime(2026, 6, 1, 0, 0, 1, tzinfo=timezone.utc), 999.0, 5)

    res = await cash_volume_for_month(session, year=2026, month=5)
    assert res["sales_cash_eur"] == pytest.approx(150.0, abs=0.01)


@pytest.mark.anyio
async def test_card_payments_excluded(session):
    """Les paiements CB ne sont pas comptés dans les flux espèces."""
    user, _ = await _seed_user_and_drawer(session)

    # Sale réglée CB → exclu
    sale = Transaction(
        transaction_number=10,
        transaction_type=TransactionType.sale,
        user_id=user.id,
        total_ht=82.50, total_tva=16.50, total_ttc=99.00,
        hash_chain="cb-sale",
        created_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )
    session.add(sale)
    await session.flush()
    session.add(Payment(
        transaction_id=sale.id, method=PaymentMethod.card, amount=99.0,
    ))
    await session.flush()

    res = await cash_volume_for_month(session, year=2026, month=5)
    assert res["sales_cash_eur"] == 0.0


@pytest.mark.anyio
async def test_net_eur_subtracts_refunds_and_deposits(session):
    """net = sales_cash − refunds_cash − bank_deposits."""
    user, drawer = await _seed_user_and_drawer(session)

    when = datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc)
    await _add_cash_sale(session, user.id, when, 1000.0, 1)
    await _add_cash_refund(session, user.id, when + timedelta(hours=1), 100.0, 2)
    await _add_movement(session, user.id, drawer.id,
        when + timedelta(days=1),
        CashMovementDirection.outflow,
        CashMovementReason.bank_deposit, 500.0)

    res = await cash_volume_for_month(session, year=2026, month=5)
    assert res["sales_cash_eur"] == pytest.approx(1000.0)
    assert res["refunds_cash_eur"] == pytest.approx(100.0)
    assert res["bank_deposits_eur"] == pytest.approx(500.0)
    assert res["net_eur"] == pytest.approx(400.0)


@pytest.mark.anyio
async def test_alert_when_bank_deposits_exceed_threshold(session):
    """Dépôts banque ≥ 10 000 € → alerte COSI explicite."""
    user, drawer = await _seed_user_and_drawer(session)

    when = datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc)
    await _add_movement(session, user.id, drawer.id, when,
        CashMovementDirection.outflow,
        CashMovementReason.bank_deposit, 12000.0)

    res = await cash_volume_for_month(session, year=2026, month=5)
    assert res["above_cosi_threshold"] is True
    assert res["alert_message"] is not None
    assert "COSI" in res["alert_message"]
    assert "12000" in res["alert_message"].replace(" ", "").replace(",", ".")


@pytest.mark.anyio
async def test_alert_when_sales_cash_exceed_threshold(session):
    """Encaissements espèces ≥ 10 000 € → alerte d'anticipation."""
    user, _ = await _seed_user_and_drawer(session)

    when = datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)
    # Une grosse vente fictive — légalement le plafond espèces 1000 € sur
    # commerçant rendrait ça impossible, mais ici on stresse le pur volume
    # mensuel cumulé qui matche le critère COSI.
    await _add_cash_sale(session, user.id, when, 10500.0, 1)

    res = await cash_volume_for_month(session, year=2026, month=5)
    assert res["above_cosi_threshold"] is True
    assert "10500" in res["alert_message"].replace(" ", "").replace(",", ".")


@pytest.mark.anyio
async def test_movements_other_outflow_classified_separately(session):
    """Sorties non-bank_deposit → other_outflow (ne déclenche pas COSI)."""
    user, drawer = await _seed_user_and_drawer(session)

    when = datetime(2026, 5, 6, 14, 0, tzinfo=timezone.utc)
    await _add_movement(session, user.id, drawer.id, when,
        CashMovementDirection.outflow,
        CashMovementReason.supplier_payment, 800.0)
    await _add_movement(session, user.id, drawer.id, when,
        CashMovementDirection.inflow,
        CashMovementReason.float_top_up, 200.0)

    res = await cash_volume_for_month(session, year=2026, month=5)
    assert res["bank_deposits_eur"] == 0.0
    assert res["other_outflow_eur"] == pytest.approx(800.0)
    assert res["inflow_eur"] == pytest.approx(200.0)
    assert res["above_cosi_threshold"] is False


@pytest.mark.anyio
async def test_last_n_months_returns_chronological_order(session):
    """cash_volume_last_n_months → liste ordonnée du plus ancien au plus récent."""
    user, _ = await _seed_user_and_drawer(session)
    # Sale en mars + en mai
    await _add_cash_sale(session, user.id,
        datetime(2026, 3, 5, tzinfo=timezone.utc), 50.0, 1)
    await _add_cash_sale(session, user.id,
        datetime(2026, 5, 10, tzinfo=timezone.utc), 75.0, 2)

    # Aujourd'hui = 2026-05-09 (cf. mémoire conversation) — on demande 4 mois
    from datetime import date as _date
    rows = await cash_volume_last_n_months(
        session, n_months=4, today=_date(2026, 5, 9),
    )
    assert len(rows) == 4
    months = [(r["year"], r["month"]) for r in rows]
    assert months == [(2026, 2), (2026, 3), (2026, 4), (2026, 5)]
    # Mars a bien la sale de 50 €, mai celle de 75 €
    assert rows[1]["sales_cash_eur"] == pytest.approx(50.0)
    assert rows[3]["sales_cash_eur"] == pytest.approx(75.0)


@pytest.mark.anyio
async def test_december_january_month_bounds(session):
    """Bordure de fin d'année — décembre n'inclut pas janvier suivant."""
    user, _ = await _seed_user_and_drawer(session)

    await _add_cash_sale(session, user.id,
        datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc), 60.0, 1)
    await _add_cash_sale(session, user.id,
        datetime(2027, 1, 1, 0, 1, tzinfo=timezone.utc), 999.0, 2)

    res = await cash_volume_for_month(session, year=2026, month=12)
    assert res["sales_cash_eur"] == pytest.approx(60.0)
