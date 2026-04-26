"""Tests for wallet pass payload (P4-004)."""

import uuid

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
    _membership_number,
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


def test_membership_number_is_stable():
    cid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    a = _membership_number(cid)
    b = _membership_number(cid)
    assert a == b
    assert a.startswith("VTZ-")
    assert len(a) == 14


@pytest.mark.anyio
async def test_build_pass_for_unknown_client_returns_none(session):
    payload = await build_pass_for_client(session, uuid.uuid4())
    assert payload is None


@pytest.mark.anyio
async def test_build_pass_uses_loyalty_when_present(session):
    client = Client(
        first_name="Alice", last_name="Martin", email="alice@x.fr",
    )
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(
        client_id=client.id, points=420, tier="silver",
    ))
    await session.flush()

    payload = await build_pass_for_client(session, client.id)
    assert payload is not None
    assert payload.points == 420
    assert payload.tier == "silver"
    assert payload.holder_name == "Alice Martin"
    assert payload.membership_number.startswith("VTZ-")
    assert payload.apple["passTypeIdentifier"]
    assert payload.google["accountId"] == payload.membership_number


@pytest.mark.anyio
async def test_build_pass_falls_back_to_bronze_when_no_loyalty(session):
    client = Client(
        first_name="Bob", last_name="Test", email="bob@x.fr",
    )
    session.add(client)
    await session.flush()

    payload = await build_pass_for_client(session, client.id)
    assert payload is not None
    assert payload.tier == "bronze"
    assert payload.points == 0


@pytest.mark.anyio
async def test_build_pass_by_email_normalises_input(session):
    client = Client(
        first_name="Charlie", last_name="Test", email="charlie@x.fr",
    )
    session.add(client)
    await session.flush()

    payload = await build_pass_by_email(session, "  CHARLIE@X.FR  ")
    assert payload is not None
    assert payload.holder_name == "Charlie Test"


@pytest.mark.anyio
async def test_payload_to_dict_serialises(session):
    client = Client(
        first_name="Dana", last_name="Test", email="dana@x.fr",
    )
    session.add(client)
    await session.flush()
    payload = await build_pass_for_client(session, client.id)
    data = payload_to_dict(payload)
    assert data["holder_name"] == "Dana Test"
    assert "apple" in data
    assert "google" in data
