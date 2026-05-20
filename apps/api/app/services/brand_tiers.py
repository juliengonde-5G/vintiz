"""DB-backed brand-tier lookup (P2-012).

Replaces the hardcoded brand sets in ``scoring_service``. The lookup is
cached in-process for 60 seconds so the per-product score endpoint
doesn't hit the DB on every call. Mutations through the admin endpoints
clear the cache explicitly so Camille sees her changes immediately.
"""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand_tier import BRAND_TIER_SCORE, BrandTier


# Score the legacy code returned for a product with no brand at all.
SCORE_NO_BRAND = 5.0
# Score the legacy code returned when a brand was set but didn't match
# any tier — kept the same so existing tests / behaviour stay stable.
SCORE_UNKNOWN_BRAND = 8.0

_CACHE_TTL_SECONDS = 60.0
_cache: dict[str, float] = {}
_cache_loaded_at: float = 0.0
# Parallel cache: brand name (lowercase) → tier level value ("luxury" …).
_tier_cache: dict[str, str] = {}


def invalidate_cache() -> None:
    """Drop the in-process cache. Called by the admin write endpoints."""
    global _cache, _cache_loaded_at, _tier_cache
    _cache = {}
    _tier_cache = {}
    _cache_loaded_at = 0.0


async def _load_cache(db: AsyncSession) -> None:
    """Pre-load every brand → score mapping from the DB into memory."""
    global _cache, _cache_loaded_at, _tier_cache
    result = await db.execute(select(BrandTier))
    rows = result.scalars().all()
    new_cache: dict[str, float] = {}
    new_tier_cache: dict[str, str] = {}
    for row in rows:
        score = (
            row.score_override
            if row.score_override is not None
            else BRAND_TIER_SCORE[row.tier]
        )
        new_cache[row.name.lower()] = float(score)
        new_tier_cache[row.name.lower()] = row.tier.value
    _cache = new_cache
    _tier_cache = new_tier_cache
    _cache_loaded_at = time.monotonic()


async def get_brand_score(db: AsyncSession, brand: str | None) -> float:
    """Return the score component for the supplied brand label.

    Lookup is substring-based — the audit V1 calls Sandro Paris a Sandro
    item, even if the tag reads "SANDRO PARIS S.A.S.". A brand string
    that contains any seeded brand name as a substring inherits its
    tier; otherwise we fall back to the unknown-brand score (8) or the
    no-brand score (5).
    """
    if not brand:
        return SCORE_NO_BRAND

    if (
        not _cache
        or (time.monotonic() - _cache_loaded_at) > _CACHE_TTL_SECONDS
    ):
        await _load_cache(db)

    needle = brand.lower()
    # Exact lowercase match first.
    if needle in _cache:
        return _cache[needle]
    # Substring fallback (longest match wins so "saint laurent" beats
    # a hypothetical "saint" entry).
    best_key: str | None = None
    for key in _cache:
        if key in needle and (best_key is None or len(key) > len(best_key)):
            best_key = key
    if best_key is not None:
        return _cache[best_key]

    return SCORE_UNKNOWN_BRAND


async def get_brand_tier(db: AsyncSession, brand: str | None) -> str | None:
    """Return the configured tier level ("luxury"/"premium"/"mid"/"basic")
    for ``brand``, or ``None`` when the brand isn't referenced.

    Same substring-tolerant matching as :func:`get_brand_score` so
    "SANDRO PARIS" resolves to the "sandro" tier. Used by the pricing engine
    to set a brand-aware multiplier from the manager-editable table rather
    than a hardcoded list.
    """
    if not brand:
        return None
    if (
        not _tier_cache
        or (time.monotonic() - _cache_loaded_at) > _CACHE_TTL_SECONDS
    ):
        await _load_cache(db)

    needle = brand.lower()
    if needle in _tier_cache:
        return _tier_cache[needle]
    best_key: str | None = None
    for key in _tier_cache:
        if key in needle and (best_key is None or len(key) > len(best_key)):
            best_key = key
    return _tier_cache[best_key] if best_key is not None else None
