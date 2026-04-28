"""Tests for wallet pass payload (PR1: single-tier, V###### card)."""

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
from app.models.user import User
from app.services.wallet import (
    PRIMARY_COLOR,
    build_pass_by_email,
    build_pass_for_client,
    payload_to_dict,
)


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


@pytest.mark.anyio
async def test_build_pass_for_unknown_client_returns_none(session):
    import uuid as _uuid

    payload = await build_pass_for_client(session, _uuid.uuid4())
    assert payload is None


@pytest.mark.anyio
async def test_build_pass_uses_loyalty_when_present(session):
    client = Client(
        first_name="Alice", last_name="Martin", email="alice@x.fr",
    )
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(
        client_id=client.id, points=420, membership_number="V482931",
    ))
    await session.flush()

    payload = await build_pass_for_client(session, client.id)
    assert payload is not None
    assert payload.points == 420
    assert payload.holder_name == "Alice Martin"
    assert payload.membership_number == "V482931"
    assert payload.primary_color == PRIMARY_COLOR
    assert payload.apple["passTypeIdentifier"]
    assert payload.google["accountId"] == "V482931"


@pytest.mark.anyio
async def test_build_pass_returns_none_when_no_loyalty(session):
    """A client without a loyalty account has no card to render."""
    client = Client(
        first_name="Bob", last_name="Test", email="bob@x.fr",
    )
    session.add(client)
    await session.flush()

    payload = await build_pass_for_client(session, client.id)
    assert payload is None


@pytest.mark.anyio
async def test_build_pass_by_email_normalises_input(session):
    client = Client(
        first_name="Charlie", last_name="Test", email="charlie@x.fr",
    )
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(
        client_id=client.id, points=10, membership_number="V300001",
    ))
    await session.flush()

    payload = await build_pass_by_email(session, "  CHARLIE@X.FR  ")
    assert payload is not None
    assert payload.holder_name == "Charlie Test"
    assert payload.membership_number == "V300001"


@pytest.mark.anyio
async def test_payload_to_dict_serialises(session):
    client = Client(
        first_name="Diana", last_name="Test", email="diana@x.fr",
    )
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(
        client_id=client.id, points=5, membership_number="V300002",
    ))
    await session.flush()

    payload = await build_pass_for_client(session, client.id)
    d = payload_to_dict(payload)
    assert d["membership_number"] == "V300002"
    assert "tier" not in d
    assert "apple" in d and "google" in d
