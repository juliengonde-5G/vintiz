"""Tests for membership_id (PR1)."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Client, LoyaltyAccount
from app.services.membership_id import (
    generate_membership_number,
    is_membership_number,
    lookup_by_membership_number,
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
async def test_is_membership_number_valid():
    assert is_membership_number("V123456")
    assert is_membership_number("V000000")
    assert is_membership_number("V999999")


@pytest.mark.anyio
async def test_is_membership_number_invalid():
    assert not is_membership_number("v123456")  # lowercase
    assert not is_membership_number("VTZ-12345")
    assert not is_membership_number("V12345")  # 5 digits
    assert not is_membership_number("V1234567")  # 7 digits
    assert not is_membership_number("")
    assert not is_membership_number(None)


@pytest.mark.anyio
async def test_generate_unique(session):
    n1 = await generate_membership_number(session)
    assert is_membership_number(n1)
    # Persist + generate another → must be different + valid.
    client = Client(first_name="A", last_name="B", email="a@x.fr")
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(client_id=client.id, points=0, membership_number=n1))
    await session.flush()
    n2 = await generate_membership_number(session)
    assert n2 != n1


@pytest.mark.anyio
async def test_lookup_by_membership_number(session):
    client = Client(first_name="Alice", last_name="M", email="alice@x.fr")
    session.add(client)
    await session.flush()
    session.add(
        LoyaltyAccount(client_id=client.id, points=10, membership_number="V482931")
    )
    await session.flush()

    found = await lookup_by_membership_number(session, "V482931")
    assert found is not None
    assert found.email == "alice@x.fr"

    none = await lookup_by_membership_number(session, "V000000")
    assert none is None

    # Invalid format → None (no DB call).
    bad = await lookup_by_membership_number(session, "xyz")
    assert bad is None
