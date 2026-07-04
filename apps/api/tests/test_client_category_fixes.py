"""Tests for the category-creation + client-edit fixes.

- BUG A : ``POST /inventory/categories`` reactivates an inactive same-name
  category instead of returning it still-disabled (which read as "rien ne se
  passe" in the settings screen).
- FEATURE C : ``PUT /crm/clients/{id}`` now edits ``notes`` and ``birth_date``
  (in addition to the existing coordonnées), so the fiche client is editable
  from the back-office.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.crm.router import UpdateClientRequest, update_client
from app.api.inventory.router import create_category
from app.models import Base
from app.models.client import Client
from app.models.product import Category
from app.models.user import User, UserRole
from app.schemas.product import CategoryCreate


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _memory_session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return eng, async_sessionmaker(eng, expire_on_commit=False)


def _fake_user() -> User:
    return User(
        id=uuid.uuid4(), username="mgr", email="m@v.fr",
        password_hash="x" * 60, role=UserRole.manager, is_active=True,
    )


# ---------------------------------------------------------------------------
# BUG A — category creation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_category_inserts_new():
    eng, Session = await _memory_session()
    async with Session() as s:
        resp = await create_category(
            CategoryCreate(name="Manteaux", gender="femme"), s, _fake_user()
        )
        await s.commit()
        assert resp.name == "Manteaux"
        rows = (await s.execute(select(Category))).scalars().all()
        assert len(rows) == 1
        assert rows[0].is_active is True
    await eng.dispose()


@pytest.mark.anyio
async def test_create_category_reactivates_inactive_same_name():
    eng, Session = await _memory_session()
    async with Session() as s:
        cat = Category(name="Robes", gender="femme", is_active=False)
        s.add(cat)
        await s.commit()
        cat_id = cat.id

    async with Session() as s:
        # Re-adding a case-insensitive match that is disabled must reactivate it
        # (not silently return it greyed out → "rien ne se passe").
        resp = await create_category(
            CategoryCreate(name="robes", gender="femme"), s, _fake_user()
        )
        await s.commit()
        assert str(resp.id) == str(cat_id)  # same row, not a duplicate

    async with Session() as s:
        row = await s.get(Category, cat_id)
        assert row.is_active is True
        # Still exactly one row (idempotent, no duplicate).
        rows = (await s.execute(select(Category))).scalars().all()
        assert len(rows) == 1
    await eng.dispose()


@pytest.mark.anyio
async def test_create_category_blank_name_400():
    from fastapi import HTTPException

    eng, Session = await _memory_session()
    async with Session() as s:
        with pytest.raises(HTTPException) as exc:
            await create_category(CategoryCreate(name="   "), s, _fake_user())
        assert exc.value.status_code == 400
    await eng.dispose()


# ---------------------------------------------------------------------------
# FEATURE C — client edit (notes + birth_date)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_client_sets_notes_and_birth_date():
    eng, Session = await _memory_session()
    async with Session() as s:
        c = Client(first_name="Marie", last_name="Curie")
        s.add(c)
        await s.commit()
        cid = c.id

    async with Session() as s:
        out = await update_client(
            cid,
            UpdateClientRequest(
                phone="0102030405",
                notes="Cliente VIP",
                birth_date="1990-05-22",
            ),
            s,
            _fake_user(),
        )
        assert out["phone"] == "0102030405"
        assert out["notes"] == "Cliente VIP"
        assert out["birth_date"] == "1990-05-22"

    async with Session() as s:
        row = await s.get(Client, cid)
        assert row.notes == "Cliente VIP"
        assert row.birth_date == date(1990, 5, 22)
    await eng.dispose()


@pytest.mark.anyio
async def test_update_client_notes_wins_over_legacy_city():
    eng, Session = await _memory_session()
    async with Session() as s:
        c = Client(first_name="A", last_name="B")
        s.add(c)
        await s.commit()
        cid = c.id

    async with Session() as s:
        # Legacy `city` maps to notes, but explicit `notes` must win.
        await update_client(
            cid, UpdateClientRequest(notes="real note", city="ignored"), s, _fake_user()
        )

    async with Session() as s:
        row = await s.get(Client, cid)
        assert row.notes == "real note"
    await eng.dispose()


@pytest.mark.anyio
async def test_update_client_clears_birth_date_with_empty_string():
    eng, Session = await _memory_session()
    async with Session() as s:
        c = Client(first_name="A", last_name="B", birth_date=date(2000, 1, 1))
        s.add(c)
        await s.commit()
        cid = c.id

    async with Session() as s:
        await update_client(cid, UpdateClientRequest(birth_date=""), s, _fake_user())

    async with Session() as s:
        row = await s.get(Client, cid)
        assert row.birth_date is None
    await eng.dispose()


@pytest.mark.anyio
async def test_update_client_bad_birth_date_400():
    from fastapi import HTTPException

    eng, Session = await _memory_session()
    async with Session() as s:
        c = Client(first_name="A", last_name="B")
        s.add(c)
        await s.commit()
        cid = c.id

    async with Session() as s:
        with pytest.raises(HTTPException) as exc:
            await update_client(
                cid, UpdateClientRequest(birth_date="22/05/1990"), s, _fake_user()
            )
        assert exc.value.status_code == 400
    await eng.dispose()
