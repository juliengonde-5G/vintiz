"""Tests for the Personal Shopper free-text search service (PR2)."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.product import Category, Product, ProductStatus
from app.services.personal_shopper_search import (
    _normalize,
    _regex_filters,
    search,
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
async def test_normalize_collapses_whitespace_and_sorts():
    assert _normalize("  T-Shirt   blanc  ") == "blanc t-shirt"
    assert _normalize("BLANC t-shirt") == _normalize("t-shirt blanc")


@pytest.mark.anyio
async def test_regex_filters_extract_size_color_category():
    f = _regex_filters("je cherche un t-shirt blanc taille M")
    assert f.size == "M"
    assert f.color == "blanc"
    assert f.category == "t-shirt"


@pytest.mark.anyio
async def test_regex_filters_max_price():
    f = _regex_filters("robe rouge moins de 40 euros")
    assert f.color == "rouge"
    assert f.category == "robe"
    assert f.max_price_cents == 4000


@pytest.mark.anyio
async def test_search_filters_inventory(session, monkeypatch):
    # Disable LLM extraction to deterministically use regex filters.
    async def fake_llm(_db, _q):
        return None
    monkeypatch.setattr(
        "app.services.personal_shopper_search._llm_filters", fake_llm
    )
    # Reset module-level caches between tests.
    from app.services import personal_shopper_search as ps_search
    ps_search._memory_cache.clear()
    ps_search._redis = None
    ps_search._redis_probed = True

    cat = Category(name="t-shirt")
    session.add(cat)
    await session.flush()
    items = [
        Product(
            barcode=f"V20{i:03d}", name=name, category_id=cat.id,
            sale_price=price, condition="A", status=status,
            color=color, size=size, trend_score=score,
        )
        for i, (name, price, status, color, size, score) in enumerate([
            ("T-shirt blanc bio", 25, ProductStatus.display, "blanc", "M", 80),
            ("T-shirt blanc col V", 30, ProductStatus.display, "blanc", "L", 70),
            ("T-shirt noir", 22, ProductStatus.display, "noir", "M", 60),
            ("T-shirt blanc vendu", 25, ProductStatus.sold, "blanc", "M", 90),
        ])
    ]
    for item in items:
        session.add(item)
    await session.flush()

    result = await search(session, "t-shirt blanc taille M")
    assert result["cache_hit"] is False
    names = [it["name"] for it in result["items"]]
    # Only the displayed white M t-shirt qualifies (sold one excluded,
    # noir filtered out, blanc col V is L not M).
    assert "T-shirt blanc bio" in names
    assert "T-shirt noir" not in names
    assert "T-shirt blanc vendu" not in names


@pytest.mark.anyio
async def test_search_uses_cache_on_second_call(session, monkeypatch):
    async def fake_llm(_db, _q):
        return None
    monkeypatch.setattr(
        "app.services.personal_shopper_search._llm_filters", fake_llm
    )
    from app.services import personal_shopper_search as ps_search
    ps_search._memory_cache.clear()
    ps_search._redis = None
    ps_search._redis_probed = True

    cat = Category(name="robe")
    session.add(cat)
    await session.flush()
    session.add(Product(
        barcode="V99001", name="Robe rouge fluide", category_id=cat.id,
        sale_price=45, condition="A", status=ProductStatus.display,
        color="rouge", size="M", trend_score=50,
    ))
    await session.flush()

    first = await search(session, "robe rouge taille M")
    assert first["cache_hit"] is False
    second = await search(session, "robe rouge taille M")
    assert second["cache_hit"] is True
    # Stable ids despite cache reload.
    assert {it["product_id"] for it in first["items"]} == {
        it["product_id"] for it in second["items"]
    }
