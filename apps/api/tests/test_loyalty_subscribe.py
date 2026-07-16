"""Tests for loyalty.subscribe + loyalty_active (PR1)."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import (
    Base,
    Client,
    Consent,
    ConsentPurpose,
)
from app.services.loyalty import (
    LoyaltyDuplicateError,
    loyalty_active,
    subscribe,
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


@pytest.mark.anyio
async def test_subscribe_creates_client_and_account(session):
    client, account = await subscribe(
        session,
        first_name="Alice",
        last_name="Martin",
        email="alice@x.fr",
        postal_code="27200",
        mode="free",
        optin_newsletter=True,
        optin_profiling=False,
    )
    await session.commit()

    assert client.email == "alice@x.fr"
    assert client.email_optin is True
    assert client.loyalty_subscription_mode == "free"
    assert client.loyalty_subscribed_at is not None
    assert client.loyalty_expires_at is not None
    assert account.membership_number.startswith("V")
    assert len(account.membership_number) == 7

    # Consent rows persisted (1 newsletter granted, 1 profiling denied).
    from sqlalchemy import select

    rows = (
        await session.execute(select(Consent).where(Consent.client_id == client.id))
    ).scalars().all()
    purposes = {(r.purpose, r.granted) for r in rows}
    assert (ConsentPurpose.email_marketing, True) in purposes
    assert (ConsentPurpose.profiling, False) in purposes


@pytest.mark.anyio
async def test_subscribe_anti_duplicate(session):
    await subscribe(
        session,
        first_name="Alice",
        last_name="Martin",
        email="alice@x.fr",
        postal_code="27200",
        mode="free",
    )
    await session.commit()

    with pytest.raises(LoyaltyDuplicateError) as exc:
        await subscribe(
            session,
            first_name="Other",
            last_name="Person",
            email="alice@x.fr",
            postal_code="33000",
            mode="paid",
        )
    assert exc.value.membership_number.startswith("V")


@pytest.mark.anyio
async def test_subscribe_attaches_to_existing_client(session):
    """Existing client without a loyalty account gets one without a duplicate row."""
    client = Client(first_name="Bob", last_name="Smith", email="bob@x.fr")
    session.add(client)
    await session.flush()

    new_client, account = await subscribe(
        session,
        first_name="Bob",
        last_name="Smith",
        email="bob@x.fr",
        postal_code=None,
        mode="free",
    )
    assert new_client.id == client.id
    assert account.client_id == client.id


@pytest.mark.anyio
async def test_subscribe_invalid_mode_raises(session):
    from app.core.exceptions import InvalidOperation

    with pytest.raises(InvalidOperation):
        await subscribe(
            session,
            first_name="X",
            last_name="Y",
            email="x@y.fr",
            postal_code=None,
            mode="vip",
        )


@pytest.mark.anyio
async def test_loyalty_active_no_account():
    client = Client(first_name="A", last_name="B", email="a@x.fr")
    assert loyalty_active(client) is False
    assert loyalty_active(None) is False


@pytest.mark.anyio
async def test_loyalty_active_after_subscribe(session):
    client, _ = await subscribe(
        session,
        first_name="Alice",
        last_name="Martin",
        email="alice@x.fr",
        postal_code=None,
        mode="free",
    )
    await session.commit()
    # Reload with relationship resolved.
    from sqlalchemy import select

    row = await session.execute(select(Client).where(Client.id == client.id))
    fresh = row.scalar_one()
    assert loyalty_active(fresh) is True
