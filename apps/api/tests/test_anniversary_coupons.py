"""Tests for anniversary email + coupon flow (P4-008)."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    AvoirTransaction,
    Client,
    Consent,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.communications import CommunicationLog, MessageTemplate
from app.models.coupon import Coupon, CouponSource
from app.models.pos import Transaction
from app.models.user import User
from app.services.anniversary import run_anniversary_pass
from app.services.coupon import issue_anniversary_coupon


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Client.__table__,
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        AvoirTransaction.__table__,
        Consent.__table__,
        Transaction.__table__,
        Coupon.__table__,
        MessageTemplate.__table__,
        CommunicationLog.__table__,
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


@pytest.fixture(autouse=True)
def _no_email_creds(monkeypatch):
    """Force the email gateway into simulation mode."""
    for key in ("BREVO_API_KEY", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# Coupon issuance
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_issue_anniversary_coupon_creates_unique_code(session):
    client = Client(first_name="A", last_name="B", email="a@b.fr")
    session.add(client)
    await session.flush()

    coupon = await issue_anniversary_coupon(session, client.id)
    assert coupon.code.startswith("ANNIV-")
    assert coupon.source == CouponSource.anniversary
    assert coupon.discount_value == 10.0
    assert coupon.is_active


@pytest.mark.anyio
async def test_issue_anniversary_coupon_is_idempotent_per_day(session):
    client = Client(first_name="A", last_name="B", email="a@b.fr")
    session.add(client)
    await session.flush()
    now = datetime.now(timezone.utc)

    first = await issue_anniversary_coupon(session, client.id, now=now)
    second = await issue_anniversary_coupon(session, client.id, now=now)
    assert first.id == second.id


# ---------------------------------------------------------------------------
# Anniversary pass
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_anniversary_pass_picks_today_birthdays_only(session):
    today = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)

    a = Client(
        first_name="Alice", last_name="X", email="alice@x.fr",
        email_optin=True, birth_date=date(1990, 4, 26),
    )
    b = Client(
        first_name="Bob", last_name="X", email="bob@x.fr",
        email_optin=True, birth_date=date(1990, 4, 27),  # not today
    )
    c = Client(  # birthday today but not opted in
        first_name="Charlie", last_name="X", email="charlie@x.fr",
        email_optin=False, birth_date=date(1985, 4, 26),
    )
    session.add_all([a, b, c])
    await session.flush()

    summary = await run_anniversary_pass(session, now=today)
    assert summary["considered"] == 1
    assert summary["coupons"] == 1
    assert summary["emails_sent"] == 1
    assert summary["failures"] == 0


@pytest.mark.anyio
async def test_anniversary_pass_handles_no_candidates(session):
    today = datetime(2026, 4, 26, tzinfo=timezone.utc)
    summary = await run_anniversary_pass(session, now=today)
    assert summary == {"considered": 0, "coupons": 0, "emails_sent": 0, "failures": 0}


@pytest.mark.anyio
async def test_anniversary_pass_skips_clients_pending_deletion(session):
    today = datetime(2026, 4, 26, tzinfo=timezone.utc)
    a = Client(
        first_name="Alice", last_name="X", email="alice@x.fr",
        email_optin=True, birth_date=date(1990, 4, 26),
        deletion_requested_at=today - timedelta(days=1),
    )
    session.add(a)
    await session.flush()

    summary = await run_anniversary_pass(session, now=today)
    assert summary["considered"] == 0
