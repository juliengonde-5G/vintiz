"""Tests for the reference pricing grid (grille tarifaire de référence).

Covers the name → default matching, the brand bucket (standard vs premium),
the floor check, and the auto-seed of defaults for matching categories.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.brand_tier import BrandTier, BrandTierLevel
from app.models.price_reference import PriceReference
from app.models.product import Category, Gender
from app.services import price_reference as svc


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        Category.__table__,
        PriceReference.__table__,
        BrandTier.__table__,
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


@pytest.fixture(autouse=True)
def _clear_brand_cache():
    from app.services import brand_tiers
    brand_tiers.invalidate_cache()
    yield
    brand_tiers.invalidate_cache()


# ---------------------------------------------------------------------------
# Default matching
# ---------------------------------------------------------------------------


def test_default_for_name_exact_and_accents():
    assert svc.default_for_name("ROBE")["standard_price"] == 10.0
    # Accent + plural insensitive: "Robes" → ROBE.
    assert svc.default_for_name("Robes")["standard_price"] == 10.0
    # Accents stripped: "Écharpes" → ECHARPES.
    assert svc.default_for_name("Écharpes")["standard_price"] == 3.0


def test_default_for_name_alternative_segments():
    # "Pull" matches the GILET/PULL/SWEAT row via the '/' split.
    d = svc.default_for_name("Pull")
    assert d is not None and d["standard_price"] == 6.0
    # "Jean" matches PANTALON/JEAN.
    assert svc.default_for_name("Jean")["premium_price"] == 15.0


def test_default_for_name_unknown_returns_none():
    assert svc.default_for_name("Gadget électronique") is None
    assert svc.default_for_name(None) is None


# ---------------------------------------------------------------------------
# Brand bucket
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_brand_bucket_premium_vs_standard(session):
    session.add_all([
        BrandTier(name="sandro", tier=BrandTierLevel.premium),
        BrandTier(name="zara", tier=BrandTierLevel.mid),
        BrandTier(name="hermès", tier=BrandTierLevel.luxury),
    ])
    await session.flush()

    assert await svc.brand_bucket(session, "Sandro Paris") == "premium"
    assert await svc.brand_bucket(session, "Hermès") == "premium"
    assert await svc.brand_bucket(session, "Zara") == "standard"
    assert await svc.brand_bucket(session, "Marque inconnue") == "standard"
    assert await svc.brand_bucket(session, None) == "standard"


# ---------------------------------------------------------------------------
# Floor check
# ---------------------------------------------------------------------------


async def _make_category(session, name: str) -> Category:
    cat = Category(name=name, gender=Gender.femme)
    session.add(cat)
    await session.flush()
    return cat


@pytest.mark.anyio
async def test_check_uses_default_when_no_row(session):
    cat = await _make_category(session, "Robe")
    # Standard brand, price below the standard floor (10 €).
    res = await svc.check(session, cat.id, brand=None, price=7.0)
    assert res["has_reference"] is True
    assert res["source"] == "default"
    assert res["bucket"] == "standard"
    assert res["floor"] == 10.0
    assert res["below"] is True

    # Same price, at/above floor → not below.
    res2 = await svc.check(session, cat.id, brand=None, price=12.0)
    assert res2["below"] is False


@pytest.mark.anyio
async def test_check_premium_brand_uses_premium_floor(session):
    cat = await _make_category(session, "Robe")
    session.add(BrandTier(name="maje", tier=BrandTierLevel.premium))
    await session.flush()
    # Premium floor for ROBE = 15 €. A 12 € Maje dress is below it…
    res = await svc.check(session, cat.id, brand="Maje", price=12.0)
    assert res["bucket"] == "premium"
    assert res["floor"] == 15.0
    assert res["below"] is True
    # …but a 12 € no-brand dress (standard floor 10) is not.
    res_std = await svc.check(session, cat.id, brand=None, price=12.0)
    assert res_std["below"] is False


@pytest.mark.anyio
async def test_check_configured_row_overrides_default(session):
    cat = await _make_category(session, "Robe")
    await svc.upsert(session, cat.id, standard_price=20, premium_price=30, note="haut de gamme")
    res = await svc.check(session, cat.id, brand=None, price=18.0)
    assert res["source"] == "configured"
    assert res["floor"] == 20.0
    assert res["below"] is True


@pytest.mark.anyio
async def test_check_no_reference_for_unknown_category(session):
    cat = await _make_category(session, "Vinyles 33 tours")
    res = await svc.check(session, cat.id, brand=None, price=1.0)
    assert res["has_reference"] is False
    assert res["below"] is False


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_seed_defaults_fills_matching_categories(session):
    await _make_category(session, "Robe")
    await _make_category(session, "Pull")
    await _make_category(session, "Bibelot")  # no match

    written = await svc.seed_defaults(session)
    assert written == 2

    rows = await svc.list_for_admin(session)
    by_name = {r["category_name"]: r for r in rows}
    assert by_name["Robe"]["standard_price"] == 10.0
    assert by_name["Pull"]["standard_price"] == 6.0
    assert by_name["Bibelot"]["standard_price"] is None
    assert by_name["Bibelot"]["has_default"] is False

    # Idempotent without overwrite: a second seed writes nothing new.
    again = await svc.seed_defaults(session)
    assert again == 0


@pytest.mark.anyio
async def test_seed_defaults_overwrite(session):
    cat = await _make_category(session, "Robe")
    await svc.upsert(session, cat.id, standard_price=99, premium_price=99)
    # Without overwrite, the manual value stays.
    assert await svc.seed_defaults(session, overwrite=False) == 0
    # With overwrite, it's reset to the grid default.
    assert await svc.seed_defaults(session, overwrite=True) == 1
    ref = await svc.get_reference(session, cat.id)
    assert float(ref.standard_price) == 10.0
