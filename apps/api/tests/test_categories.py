"""Tests for category editing + activation (admin categories management).

Drives the route coroutines directly on an in-memory aiosqlite session.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.inventory.router import list_categories, update_category
from app.models import Base
from app.models.product import Category, Gender
from app.schemas.product import CategoryUpdate


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[Category.__table__]))
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


async def _cat(session, name, gender=Gender.femme, is_active=True) -> Category:
    now = datetime.now(timezone.utc)
    c = Category(name=name, gender=gender, is_active=is_active, created_at=now, updated_at=now)
    session.add(c)
    await session.flush()
    return c


@pytest.mark.anyio
async def test_update_name_and_gender(session):
    c = await _cat(session, "Robes", Gender.femme)
    out = await update_category(c.id, CategoryUpdate(name="Robes & combinaisons", gender="mixte"), session, None)
    assert out.name == "Robes & combinaisons"
    assert out.gender == "mixte"


@pytest.mark.anyio
async def test_update_rejects_duplicate_name(session):
    await _cat(session, "Vestes")
    c2 = await _cat(session, "Pulls")
    with pytest.raises(HTTPException) as exc:
        await update_category(c2.id, CategoryUpdate(name="vestes"), session, None)  # case-insensitive clash
    assert exc.value.status_code == 409


@pytest.mark.anyio
async def test_update_unknown_category_404(session):
    with pytest.raises(HTTPException) as exc:
        await update_category(uuid.uuid4(), CategoryUpdate(name="X"), session, None)
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_toggle_active_and_list_filtering(session):
    a = await _cat(session, "Sacs")
    await _cat(session, "Bijoux")

    # Default list returns both active categories.
    active = await list_categories(session, None, include_inactive=False)
    assert {c.name for c in active} == {"Sacs", "Bijoux"}

    # Deactivate one → it drops from the default list…
    await update_category(a.id, CategoryUpdate(is_active=False), session, None)
    active = await list_categories(session, None, include_inactive=False)
    assert {c.name for c in active} == {"Bijoux"}

    # …but the management view still sees it.
    everything = await list_categories(session, None, include_inactive=True)
    assert {c.name for c in everything} == {"Sacs", "Bijoux"}
    sacs = next(c for c in everything if c.name == "Sacs")
    assert sacs.is_active is False

    # Re-enable.
    await update_category(a.id, CategoryUpdate(is_active=True), session, None)
    active = await list_categories(session, None, include_inactive=False)
    assert {c.name for c in active} == {"Sacs", "Bijoux"}
