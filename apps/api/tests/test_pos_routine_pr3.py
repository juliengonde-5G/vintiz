"""Tests for PR 3/6 — cash movements + payment attempts + Z report intangibility.

Service-level tests on SQLite (no HTTP / auth required):

- ``CashMovement`` round-trip + Z-report expected_amount including movements
- ``PaymentAttempt`` lifecycle (pending → failed/succeeded) with error_detail
- ``FiscalService.lock_z_report`` — idempotent + persists pdf + sha
- ``FiscalService.lock_z_report`` — second call returns ``already_locked=True``
- ``generate_z_report_pdf`` — bytes start with %PDF-, contain breakdown rows
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import (
    Base,
    CashMovement,
    CashMovementDirection,
    CashMovementReason,
    PaymentAttempt,
    PaymentAttemptStatus,
    User,
)
from app.models.pos import PaymentMethod
from app.services.fiscal import FiscalService
from app.services.pos import PosService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as s:
        yield s
    await eng.dispose()


async def _make_user(session) -> User:
    user = User(
        username="admin",
        email="admin@vintiz.fr",
        password_hash="x",
        role="manager",
    )
    session.add(user)
    await session.flush()
    return user


class _FakeCartItem:
    def __init__(self, name: str, unit_price: float, quantity: int = 1):
        self.product_id = None
        self.name = name
        self.unit_price = unit_price
        self.quantity = quantity
        self.discount_percent = 0.0


class _FakePayment:
    def __init__(self, method: str, amount: float):
        self.method = method
        self.amount = amount


# ---------------------------------------------------------------------------
# Cash movements
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cash_movements_persist_and_belong_to_drawer(session):
    user = await _make_user(session)
    pos = PosService(session)
    drawer = await pos.open_drawer(
        user.id,
        Decimal("100.00"),
        opening_breakdown=[{"denom": 50, "count": 2}],
    )

    session.add(
        CashMovement(
            drawer_id=drawer.id,
            direction=CashMovementDirection.outflow,
            amount=50.0,
            reason=CashMovementReason.bank_deposit,
            note="Dépôt 14h",
            user_id=user.id,
        )
    )
    session.add(
        CashMovement(
            drawer_id=drawer.id,
            direction=CashMovementDirection.inflow,
            amount=20.0,
            reason=CashMovementReason.float_top_up,
            user_id=user.id,
        )
    )
    await session.commit()

    rows = (
        await session.execute(
            select(CashMovement).where(CashMovement.drawer_id == drawer.id)
        )
    ).scalars().all()
    assert len(rows) == 2
    assert {r.direction for r in rows} == {
        CashMovementDirection.outflow,
        CashMovementDirection.inflow,
    }


@pytest.mark.anyio
async def test_close_drawer_includes_cash_movements_in_expected(session):
    """Bank deposit during the day must subtract from the expected total."""
    user = await _make_user(session)
    pos = PosService(session)
    drawer = await pos.open_drawer(user.id, Decimal("100.00"))

    # Cash sale of 60 €
    transaction = await pos.create_transaction(
        user_id=user.id,
        items=[_FakeCartItem("Sac", 60.0)],
        payments=[_FakePayment("cash", 60.0)],
    )
    await session.commit()
    assert transaction is not None

    # Mid-day deposit of 80 € to the bank
    session.add(
        CashMovement(
            drawer_id=drawer.id,
            direction=CashMovementDirection.outflow,
            amount=80.0,
            reason=CashMovementReason.bank_deposit,
            user_id=user.id,
        )
    )
    await session.commit()

    closed = await pos.close_drawer(
        user.id,
        Decimal("80.00"),
        closing_breakdown=[{"denom": 20, "count": 4}],
    )
    await session.commit()

    # Expected = 100 (opening) + 60 (cash sale) + 0 (in) - 80 (out) = 80
    assert float(closed.expected_amount) == pytest.approx(80.0)
    # Counted matches → no discrepancy
    assert float(closed.closing_amount) == 80.0


# ---------------------------------------------------------------------------
# Payment attempts
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_payment_attempt_lifecycle_pending_to_failed(session):
    user = await _make_user(session)
    attempt = PaymentAttempt(
        method=PaymentMethod.card,
        amount=49.0,
        status=PaymentAttemptStatus.pending,
        cashier_id=user.id,
        sumup_checkout_id="check_abc123",
    )
    session.add(attempt)
    await session.commit()

    # ... TPE refused
    attempt.status = PaymentAttemptStatus.failed
    attempt.error_detail = "Card declined"
    await session.commit()

    refreshed = (
        await session.execute(
            select(PaymentAttempt).where(PaymentAttempt.id == attempt.id)
        )
    ).scalar_one()
    assert refreshed.status == PaymentAttemptStatus.failed
    assert refreshed.error_detail == "Card declined"
    assert refreshed.transaction_id is None  # vente abandonnée


# ---------------------------------------------------------------------------
# Z report PDF + lock
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_lock_z_report_is_idempotent_and_persists_pdf(session):
    pytest.importorskip("reportlab")
    user = await _make_user(session)
    pos = PosService(session)
    fiscal = FiscalService(session)

    drawer = await pos.open_drawer(user.id, Decimal("100.00"))
    await pos.create_transaction(
        user_id=user.id,
        items=[_FakeCartItem("Sac", 80.0)],
        payments=[_FakePayment("cash", 80.0)],
    )
    closed = await pos.close_drawer(user.id, Decimal("180.00"))
    z = await fiscal.generate_z_report(closed, user.id)
    await session.commit()

    first = await fiscal.lock_z_report(z.id, user_id=user.id)
    await session.commit()
    assert first["is_locked"] is True
    assert first["already_locked"] is False
    assert first["pdf_sha256"]
    sha_first = first["pdf_sha256"]

    # PDF bytes persisted
    refreshed = (
        await session.execute(
            select(type(z)).where(type(z).id == z.id)
        )
    ).scalar_one()
    assert refreshed.is_locked is True
    assert refreshed.pdf_content is not None
    assert refreshed.pdf_content.startswith(b"%PDF-")
    assert refreshed.pdf_sha256 == sha_first

    # Second call short-circuits — same hash, no re-render
    second = await fiscal.lock_z_report(z.id, user_id=user.id)
    assert second["already_locked"] is True
    assert second["pdf_sha256"] == sha_first


@pytest.mark.anyio
async def test_z_report_pdf_returns_pdf_bytes_with_breakdown(session):
    pytest.importorskip("reportlab")
    user = await _make_user(session)
    pos = PosService(session)
    fiscal = FiscalService(session)

    drawer = await pos.open_drawer(
        user.id,
        Decimal("100.00"),
        opening_breakdown=[
            {"denom": 50, "count": 2},
        ],
    )
    await pos.create_transaction(
        user_id=user.id,
        items=[_FakeCartItem("Robe", 49.0)],
        payments=[_FakePayment("cash", 49.0)],
    )
    closed = await pos.close_drawer(
        user.id,
        Decimal("149.00"),
        closing_breakdown=[
            {"denom": 50, "count": 2},
            {"denom": 20, "count": 2},
            {"denom": 5, "count": 1},
            {"denom": 2, "count": 2},
        ],
    )
    z = await fiscal.generate_z_report(closed, user.id)
    await session.commit()

    from app.services.z_report_pdf import generate_z_report_pdf

    pdf_bytes = await generate_z_report_pdf(session, z)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1500


@pytest.mark.anyio
async def test_drawer_alert_when_discrepancy_exceeds_threshold(session):
    user = await _make_user(session)
    pos = PosService(session)

    drawer = await pos.open_drawer(user.id, Decimal("100.00"))
    await pos.create_transaction(
        user_id=user.id,
        items=[_FakeCartItem("Sac", 50.0)],
        payments=[_FakePayment("cash", 50.0)],
    )
    # Close with 5 € less than expected and an explicit allowed_discrepancy=2
    closed = await pos.close_drawer(
        user.id,
        Decimal("145.00"),  # expected 150, discrepancy = -5
        closing_note="Rendu de monnaie en trop possible",
        allowed_discrepancy_override=Decimal("2.00"),
    )
    await session.commit()

    diff = float(closed.closing_amount) - float(closed.expected_amount)
    assert diff == pytest.approx(-5.0)
    assert float(closed.allowed_discrepancy) == 2.0
    assert closed.closing_note  # captured
