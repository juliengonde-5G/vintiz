"""Tests for the public 'Sélection du moment' endpoint (#7)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.crm.account import public_account_selection
from app.models import Base
from app.models.product import Category, Product, ProductStatus


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


async def _cat(session, name):
    c = Category(name=name)
    session.add(c)
    await session.flush()
    return c


async def _prod(session, cat, name, trend, status=ProductStatus.display):
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}", name=name, category_id=cat.id,
        sale_price=40.0, trend_score=trend, status=status,
    )
    session.add(p)
    await session.flush()
    return p


@pytest.mark.anyio
async def test_selection_one_per_category_best_rated(session):
    robes = await _cat(session, "Robes")
    pulls = await _cat(session, "Pulls")
    # Two robes (95 best) + one pull. Expect best robe + pull, no duplicate cat.
    await _prod(session, robes, "Robe A", 80)
    await _prod(session, robes, "Robe B", 95)
    await _prod(session, pulls, "Pull C", 70)

    res = await public_account_selection(email=None, db=session)
    names = [it["name"] for it in res["items"]]
    assert res["ps_member"] is False
    assert "Robe B" in names         # best-rated robe kept
    assert "Robe A" not in names     # second robe (same cat) dropped
    assert "Pull C" in names
    assert len(names) == len(set(names))


@pytest.mark.anyio
async def test_selection_caps_at_ten_categories(session):
    for i in range(14):
        cat = await _cat(session, f"Cat{i}")
        await _prod(session, cat, f"P{i}", float(100 - i))
    res = await public_account_selection(email=None, db=session)
    assert len(res["items"]) == 10
    # Highest trend_score first.
    assert res["items"][0]["name"] == "P0"


@pytest.mark.anyio
async def test_selection_excludes_sold(session):
    cat = await _cat(session, "Robes")
    await _prod(session, cat, "Vendue", 99, status=ProductStatus.sold)
    await _prod(session, cat, "Dispo", 50)
    res = await public_account_selection(email=None, db=session)
    names = [it["name"] for it in res["items"]]
    assert "Vendue" not in names
    assert "Dispo" in names
