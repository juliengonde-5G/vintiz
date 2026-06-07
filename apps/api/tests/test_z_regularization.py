"""Tests de la clôture de régularisation a posteriori (jour de caisse oublié).

Vérifie : détection des ventes orphelines, création d'un Z de régularisation
flaggé + chaîné (jamais antidaté), refus en cas de chevauchement (409) et
absence d'orphelines (400).
"""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
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
from app.models.user import User, UserRole
from app.services.fiscal import FiscalService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        Payment.__table__,
        Receipt.__table__,
        CashDrawer.__table__,
        ZReport.__table__,
    ]
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as s:
        yield s
    await eng.dispose()


async def _user(session) -> User:
    u = User(
        username="manager",
        email="m@v.fr",
        password_hash="x" * 60,
        role=UserRole.manager,
        is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


async def _cash_sale(session, user_id, when, amount, no):
    t = Transaction(
        transaction_number=no,
        transaction_type=TransactionType.sale,
        user_id=user_id,
        total_ht=round(amount * 0.8333, 2),
        total_tva=round(amount * 0.1667, 2),
        total_ttc=amount,
        hash_chain=f"h{no}",
        created_at=when,
    )
    session.add(t)
    await session.flush()
    session.add(Payment(transaction_id=t.id, method=PaymentMethod.cash, amount=amount))
    await session.flush()
    return t


# Journée à régulariser
DAY_FROM = datetime(2026, 6, 5, 0, 0, 0, tzinfo=timezone.utc)
DAY_TO = datetime(2026, 6, 5, 23, 59, 59, tzinfo=timezone.utc)


@pytest.mark.anyio
async def test_preview_finds_orphans(session):
    u = await _user(session)
    await _cash_sale(session, u.id, datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc), 30.0, 1)
    await _cash_sale(session, u.id, datetime(2026, 6, 5, 15, 0, tzinfo=timezone.utc), 20.0, 2)

    preview = await FiscalService(session).preview_regularization(DAY_FROM, DAY_TO)
    assert preview["orphan_count"] == 2
    assert preview["sale_count"] == 2
    assert preview["has_overlap"] is False
    assert preview["can_regularize"] is True
    assert preview["total_sales"] == 50.0
    assert preview["by_method"]["cash"] == 50.0
    assert preview["transaction_numbers"] == [1, 2]


@pytest.mark.anyio
async def test_create_regularization_z(session):
    u = await _user(session)
    await _cash_sale(session, u.id, datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc), 30.0, 1)
    await _cash_sale(session, u.id, datetime(2026, 6, 5, 15, 0, tzinfo=timezone.utc), 20.0, 2)

    fiscal = FiscalService(session)
    z = await fiscal.create_regularization_z(DAY_FROM, DAY_TO, "Ouverture oubliée", u.id)
    await session.flush()

    assert z.is_regularization is True
    assert z.regularization_reason == "Ouverture oubliée"
    assert float(z.total_sales) == 50.0
    assert z.transaction_count == 2
    assert z.report_number == 1
    assert z.previous_hash == "0"  # premier Z de la chaîne

    # Un Z normal ultérieur se chaîne bien sur le Z de régularisation.
    drawer = CashDrawer(
        user_id=u.id,
        opened_at=datetime(2026, 6, 6, 9, 0, tzinfo=timezone.utc),
        closed_at=datetime(2026, 6, 6, 19, 0, tzinfo=timezone.utc),
        opening_amount=0,
        is_open=False,
    )
    session.add(drawer)
    await session.flush()
    z2 = await fiscal.generate_z_report(drawer, u.id)
    assert z2.report_number == 2
    assert z2.previous_hash == z.hash
    assert z2.is_regularization is False


@pytest.mark.anyio
async def test_overlap_is_refused(session):
    u = await _user(session)
    # Session de caisse couvrant le 5 juin 09h-19h…
    drawer = CashDrawer(
        user_id=u.id,
        opened_at=datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc),
        closed_at=datetime(2026, 6, 5, 19, 0, tzinfo=timezone.utc),
        opening_amount=0,
        is_open=False,
    )
    session.add(drawer)
    await session.flush()
    # …avec une vente dedans → déjà couverte.
    await _cash_sale(session, u.id, datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc), 30.0, 1)

    preview = await FiscalService(session).preview_regularization(DAY_FROM, DAY_TO)
    assert preview["has_overlap"] is True
    assert preview["can_regularize"] is False

    with pytest.raises(HTTPException) as exc:
        await FiscalService(session).create_regularization_z(
            DAY_FROM, DAY_TO, "test", u.id
        )
    assert exc.value.status_code == 409


@pytest.mark.anyio
async def test_no_orphans_is_400(session):
    u = await _user(session)  # aucune vente le 5
    with pytest.raises(HTTPException) as exc:
        await FiscalService(session).create_regularization_z(
            DAY_FROM, DAY_TO, "test", u.id
        )
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_reason_required(session):
    u = await _user(session)
    await _cash_sale(session, u.id, datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc), 30.0, 1)
    with pytest.raises(HTTPException) as exc:
        await FiscalService(session).create_regularization_z(DAY_FROM, DAY_TO, "  ", u.id)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_close_open_drawers(session):
    u = await _user(session)
    # Caisse restée ouverte (ouverte le 5 à 9h, jamais clôturée) + une vente.
    drawer = CashDrawer(
        user_id=u.id,
        opened_at=datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc),
        closed_at=None,
        opening_amount=50.0,
        is_open=True,
    )
    session.add(drawer)
    await session.flush()
    await _cash_sale(session, u.id, datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc), 30.0, 1)

    fiscal = FiscalService(session)
    reports = await fiscal.close_open_drawers(u.id)
    await session.flush()

    assert len(reports) == 1
    assert reports[0].is_regularization is False  # Z normal
    assert float(reports[0].total_sales) == 30.0
    # La caisse est désormais fermée.
    assert drawer.is_open is False
    assert drawer.closed_at is not None
    # Fond attendu = ouverture 50 + 30 de vente espèces.
    assert float(drawer.expected_amount) == 80.0
    # Plus aucune caisse ouverte.
    from sqlalchemy import select as _select
    remaining = (
        await session.execute(_select(CashDrawer).where(CashDrawer.is_open.is_(True)))
    ).scalars().all()
    assert remaining == []
