"""Tests for Personal Shopper gating (PR2)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Client, Consent, ConsentPurpose, LoyaltyAccount
from app.services.personal_shopper import (
    PersonalShopperGatedError,
    PersonalShopperService,
)


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


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _make_member(session, *, with_profiling: bool):
    client = Client(first_name="Alice", last_name="Martin", email="alice@x.fr")
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(
        client_id=client.id, points=10, membership_number="V100100"
    ))
    client.loyalty_subscribed_at = _now()
    client.loyalty_expires_at = _now() + timedelta(days=730)
    await session.flush()
    if with_profiling:
        session.add(Consent(
            client_id=client.id,
            purpose=ConsentPurpose.profiling,
            granted=True,
            policy_version="v2",
            source="test",
        ))
        await session.flush()
    return client


@pytest.mark.anyio
async def test_non_member_raises_loyalty_required(session):
    client = Client(first_name="Bob", last_name="Smith", email="bob@x.fr")
    session.add(client)
    await session.flush()

    with pytest.raises(PersonalShopperGatedError) as exc:
        await PersonalShopperService(session).recommend(client.id)
    assert exc.value.reason == "loyalty_required"


@pytest.mark.anyio
async def test_member_without_profiling_raises_consent_required(session):
    client = await _make_member(session, with_profiling=False)
    with pytest.raises(PersonalShopperGatedError) as exc:
        await PersonalShopperService(session).recommend(client.id)
    assert exc.value.reason == "profiling_consent_required"


@pytest.mark.anyio
async def test_member_with_revoked_profiling_raises(session):
    client = await _make_member(session, with_profiling=True)
    # Revoke the consent (latest row wins). Explicit created_at to avoid
    # tied timestamps with the prior row on SQLite (1s granularity).
    revoke = Consent(
        client_id=client.id,
        purpose=ConsentPurpose.profiling,
        granted=False,
        policy_version="v2",
        source="test",
    )
    revoke.created_at = _now() + timedelta(seconds=1)
    session.add(revoke)
    await session.flush()

    with pytest.raises(PersonalShopperGatedError) as exc:
        await PersonalShopperService(session).recommend(client.id)
    assert exc.value.reason == "profiling_consent_required"


@pytest.mark.anyio
async def test_expired_loyalty_raises_loyalty_required(session):
    client = await _make_member(session, with_profiling=True)
    client.loyalty_expires_at = _now() - timedelta(days=1)
    await session.flush()

    with pytest.raises(PersonalShopperGatedError) as exc:
        await PersonalShopperService(session).recommend(client.id)
    assert exc.value.reason == "loyalty_required"
