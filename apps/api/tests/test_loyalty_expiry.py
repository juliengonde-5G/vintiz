"""Tests for loyalty_expiry (PR1: 24-month inactivity rule)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Client, LoyaltyAccount, LoyaltyTransaction
from app.models.client import LoyaltyTxType
from app.services.loyalty_expiry import expire_inactive_points


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


@pytest.mark.anyio
async def test_expire_zero_points_skipped(session):
    client = Client(first_name="A", last_name="B", email="a@x.fr")
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(client_id=client.id, points=0, membership_number="V100001"))
    await session.flush()

    count = await expire_inactive_points(session)
    assert count == 0


@pytest.mark.anyio
async def test_expire_recent_account_skipped(session):
    """An account with a recent earn tx must not be expired."""
    client = Client(first_name="B", last_name="C", email="b@x.fr")
    session.add(client)
    await session.flush()
    account = LoyaltyAccount(
        client_id=client.id, points=50, membership_number="V100002"
    )
    session.add(account)
    await session.flush()
    session.add(
        LoyaltyTransaction(
            account_id=account.id,
            tx_type=LoyaltyTxType.earn,
            points=50,
            description="recent",
        )
    )
    await session.flush()

    count = await expire_inactive_points(session)
    assert count == 0
    assert account.points == 50


@pytest.mark.anyio
async def test_expire_stale_account_zeroed(session):
    """An account whose latest activity is > 24mo old gets zeroed with an adjust row."""
    client = Client(first_name="C", last_name="D", email="c@x.fr")
    session.add(client)
    await session.flush()
    account = LoyaltyAccount(
        client_id=client.id, points=200, membership_number="V100003"
    )
    session.add(account)
    await session.flush()
    # Backdate the only earn tx to 25 months ago.
    old = datetime.now(timezone.utc) - timedelta(days=760)
    session.add(
        LoyaltyTransaction(
            account_id=account.id,
            tx_type=LoyaltyTxType.earn,
            points=200,
            description="ancient",
            created_at=old,
        )
    )
    await session.flush()

    count = await expire_inactive_points(session)
    assert count == 1
    assert account.points == 0

    # Adjust row recorded.
    rows = (
        await session.execute(
            select(LoyaltyTransaction).where(
                LoyaltyTransaction.account_id == account.id,
                LoyaltyTransaction.tx_type == LoyaltyTxType.adjust,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].points == -200
