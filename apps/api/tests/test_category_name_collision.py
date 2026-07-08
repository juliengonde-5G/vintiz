"""Regression: category creation/rename must not 500 on a normalized-name clash.

Root cause (bug « impossible de créer une catégorie / il ne se passe rien ») :
``POST /inventory/categories`` probed for an existing category with
``Category.name.ilike(name)``. That probe is case-insensitive but does NOT
trim, whereas the DB unique index ``uq_categories_name_lower`` (migration 0046)
is ``lower(btrim(name))``. A legacy row stored with stray whitespace ("Gilet ",
"Robes " — the latter cited verbatim in migration 0046) therefore slipped past
the ``ILIKE`` lookup, so the endpoint tried to INSERT a fresh row, which
collided with the unique index → ``IntegrityError`` → HTTP 500. On the settings
screen the error banner renders at the top of the page, far from the form, so
the manager just saw "rien ne se passe".

These tests recreate the production unique index (spelled with ``trim`` so it
runs on SQLite, identical semantics to Postgres ``btrim``) and assert the
endpoints now resolve the clash idempotently instead of raising.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.inventory.router import create_category, update_category
from app.models import Base
from app.models.product import Category
from app.models.user import User, UserRole
from app.schemas.product import CategoryCreate, CategoryUpdate


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _memory_session_with_index():
    """In-memory SQLite + the production unique index on lower(trim(name))."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(c, tables=[Category.__table__])
        )
        # Mirror uq_categories_name_lower from migration 0046. Postgres uses
        # btrim; trim is the portable equivalent and identical for spaces.
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX uq_categories_name_lower "
                "ON categories (lower(trim(name)))"
            )
        )
    return eng, async_sessionmaker(eng, expire_on_commit=False)


def _fake_user() -> User:
    return User(
        id=uuid.uuid4(), username="mgr", email="m@v.fr",
        password_hash="x" * 60, role=UserRole.manager, is_active=True,
    )


@pytest.mark.anyio
async def test_create_over_active_whitespace_row_is_idempotent():
    """Adding "Gilet" when an active "Gilet " (trailing space) exists returns
    the existing row (201) instead of crashing on the unique index."""
    eng, Session = await _memory_session_with_index()
    async with Session() as s:
        s.add(Category(name="Gilet ", gender="femme"))  # legacy trailing space
        await s.commit()

    async with Session() as s:
        resp = await create_category(
            CategoryCreate(name="Gilet", gender="femme"), s, _fake_user()
        )
        await s.commit()
        assert resp.name.strip() == "Gilet"
        rows = (await s.execute(select(Category))).scalars().all()
        assert len(rows) == 1  # no duplicate, no IntegrityError
    await eng.dispose()


@pytest.mark.anyio
async def test_create_over_inactive_whitespace_row_reactivates():
    """A disabled "  Robes" (leading spaces) must be reactivated, not shadowed
    by a colliding insert."""
    eng, Session = await _memory_session_with_index()
    async with Session() as s:
        s.add(Category(name="  Robes", gender="femme", is_active=False))
        await s.commit()
        cat_id = (await s.execute(select(Category))).scalars().first().id

    async with Session() as s:
        resp = await create_category(
            CategoryCreate(name="robes", gender="femme"), s, _fake_user()
        )
        await s.commit()
        assert str(resp.id) == str(cat_id)  # same row
        assert resp.is_active is True       # reactivated
        rows = (await s.execute(select(Category))).scalars().all()
        assert len(rows) == 1
    await eng.dispose()


@pytest.mark.anyio
async def test_create_brand_new_name_still_inserts():
    """The clash handling must not regress the happy path."""
    eng, Session = await _memory_session_with_index()
    async with Session() as s:
        resp = await create_category(
            CategoryCreate(name="Chemise", gender="homme"), s, _fake_user()
        )
        await s.commit()
        assert resp.name == "Chemise"
        assert resp.gender == "homme"
        rows = (await s.execute(select(Category))).scalars().all()
        assert len(rows) == 1
    await eng.dispose()


@pytest.mark.anyio
async def test_rename_into_whitespace_duplicate_is_409_not_500():
    """Renaming a category onto a whitespace-laden twin returns a clean 409."""
    eng, Session = await _memory_session_with_index()
    async with Session() as s:
        s.add(Category(name="Vestes ", gender="femme"))  # trailing space
        keep = Category(name="Pulls", gender="femme")
        s.add(keep)
        await s.commit()
        keep_id = keep.id

    async with Session() as s:
        with pytest.raises(HTTPException) as exc:
            await update_category(
                keep_id, CategoryUpdate(name="vestes"), s, _fake_user()
            )
        assert exc.value.status_code == 409
    await eng.dispose()
