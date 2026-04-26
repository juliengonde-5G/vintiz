"""Tests for the DB-backed brand-tier lookup (P2-012)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.brand_tier import (
    BRAND_TIER_SCORE,
    BrandTier,
    BrandTierLevel,
)
from app.services.brand_tiers import (
    SCORE_NO_BRAND,
    SCORE_UNKNOWN_BRAND,
    get_brand_score,
    invalidate_cache,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [BrandTier.__table__]
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
def _reset_cache():
    """Each test starts from a clean cache."""
    invalidate_cache()
    yield
    invalidate_cache()


async def _seed(session, name, tier, override=None):
    row = BrandTier(name=name.lower(), tier=tier, score_override=override)
    session.add(row)
    await session.flush()
    return row


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_brand_returns_no_brand_constant(session):
    assert await get_brand_score(session, None) == SCORE_NO_BRAND
    assert await get_brand_score(session, "") == SCORE_NO_BRAND


@pytest.mark.anyio
async def test_unknown_brand_returns_unknown_constant(session):
    assert await get_brand_score(session, "un-brand-jamais-vu") == SCORE_UNKNOWN_BRAND


@pytest.mark.anyio
async def test_exact_match_returns_tier_score(session):
    await _seed(session, "Sandro", BrandTierLevel.premium)
    assert (
        await get_brand_score(session, "Sandro")
        == BRAND_TIER_SCORE[BrandTierLevel.premium]
    )


@pytest.mark.anyio
async def test_substring_match_finds_brand(session):
    """A tag that reads "SANDRO PARIS S.A.S." still resolves to Sandro."""
    await _seed(session, "Sandro", BrandTierLevel.premium)
    assert (
        await get_brand_score(session, "SANDRO PARIS S.A.S.")
        == BRAND_TIER_SCORE[BrandTierLevel.premium]
    )


@pytest.mark.anyio
async def test_score_override_wins(session):
    """A per-row override beats the tier default."""
    await _seed(session, "exclusive", BrandTierLevel.mid, override=18.5)
    assert await get_brand_score(session, "exclusive") == 18.5


@pytest.mark.anyio
async def test_longest_substring_match_wins(session):
    """When two seeded brands both substring-match, the longer name wins."""
    await _seed(session, "saint", BrandTierLevel.mid)
    await _seed(session, "saint laurent", BrandTierLevel.luxury)
    assert (
        await get_brand_score(session, "Saint Laurent Paris")
        == BRAND_TIER_SCORE[BrandTierLevel.luxury]
    )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cache_serves_subsequent_calls_without_db_changes(session):
    """Adding a brand AFTER the cache is loaded must NOT show up until
    invalidate_cache() is called — the in-process cache holds for its
    TTL and lookups stay deterministic."""
    await _seed(session, "Sandro", BrandTierLevel.premium)
    # Prime the cache via a first lookup.
    sandro = await get_brand_score(session, "Sandro")
    assert sandro == BRAND_TIER_SCORE[BrandTierLevel.premium]

    # Add a brand-new entry without invalidating.
    await _seed(session, "newcomer", BrandTierLevel.luxury)

    # Lookup for the new brand must MISS — the cache is still stale.
    assert await get_brand_score(session, "newcomer") == SCORE_UNKNOWN_BRAND
    # And the existing entry is unchanged.
    assert await get_brand_score(session, "Sandro") == sandro


@pytest.mark.anyio
async def test_invalidate_cache_picks_up_new_data(session):
    await _seed(session, "Sandro", BrandTierLevel.premium)
    _ = await get_brand_score(session, "Sandro")

    # Drop the only row, invalidate, ask again.
    invalidate_cache()
    from sqlalchemy import delete

    await session.execute(delete(BrandTier))
    await session.flush()
    invalidate_cache()
    # Now Sandro is unknown again.
    assert await get_brand_score(session, "Sandro") == SCORE_UNKNOWN_BRAND
