"""Per-category trend signal feeding the scoring engine (P2-010).

Replaces the static ``category_trend = 50.0`` default in
``scoring_service.compute_score``. The signal is the relative sales
velocity of each category over the last 4 weeks, normalised to 0..100
so it plugs straight into the existing formula
(``score_category = category_trend / 5``).

A live recomputation reads recent transactions; results are cached as
JSON in the ``app_settings`` table so cheap callers (per-product score
endpoint) don't pay the aggregation cost on every hit. The monthly
scoring cron refreshes the cache too.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Settings
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Product

logger = logging.getLogger("vintiz.category_trends")


CACHE_KEY = "category_trends_cache"
DEFAULT_WINDOW_DAYS = 28
DEFAULT_MAX_CACHE_AGE_HOURS = 24
NEUTRAL_TREND = 50.0


async def compute_category_trends(
    db: AsyncSession, *, window_days: int = DEFAULT_WINDOW_DAYS
) -> dict[str, float]:
    """Compute the trend signal per category from the last ``window_days``.

    Returns ``{category_id_str: score_0_100}``. The category with the
    most sales gets 100; the rest scale linearly. Categories with no
    sales in the window appear with the neutral value (50) so a brand-new
    category isn't penalised on day one.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    sales_result = await db.execute(
        select(
            Product.category_id,
            func.count(TransactionItem.id).label("n"),
        )
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= cutoff,
            Product.category_id.is_not(None),
        )
        .group_by(Product.category_id)
    )
    sales_by_cat: dict[uuid.UUID, int] = {
        row[0]: int(row[1]) for row in sales_result.all() if row[0] is not None
    }

    cats_result = await db.execute(select(Category.id))
    all_cat_ids = [row[0] for row in cats_result.all()]

    if not sales_by_cat:
        return {str(cid): NEUTRAL_TREND for cid in all_cat_ids}

    max_sales = max(sales_by_cat.values())
    trends: dict[str, float] = {}
    for cat_id in all_cat_ids:
        n = sales_by_cat.get(cat_id, 0)
        if n == 0:
            trends[str(cat_id)] = NEUTRAL_TREND
        else:
            trends[str(cat_id)] = round(100.0 * n / max_sales, 1)
    return trends


async def _read_cache(db: AsyncSession) -> tuple[dict[str, float], datetime] | None:
    result = await db.execute(
        select(Settings).where(Settings.key == CACHE_KEY)
    )
    row = result.scalar_one_or_none()
    if row is None or not row.value:
        return None
    try:
        payload = json.loads(row.value)
        cached_at = datetime.fromisoformat(payload["computed_at"])
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        return payload["trends"], cached_at
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("category_trends cache unreadable: %s", exc)
        return None


async def _write_cache(db: AsyncSession, trends: dict[str, float]) -> None:
    payload = json.dumps({
        "trends": trends,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    result = await db.execute(
        select(Settings).where(Settings.key == CACHE_KEY)
    )
    row = result.scalar_one_or_none()
    if row is None:
        db.add(Settings(
            key=CACHE_KEY,
            value=payload,
            description="Auto-computed per-category trend (P2-010)",
        ))
    else:
        row.value = payload
    await db.flush()


async def get_category_trends(
    db: AsyncSession,
    *,
    max_age_hours: int = DEFAULT_MAX_CACHE_AGE_HOURS,
) -> dict[str, float]:
    """Return the trend per category, recomputing if the cache is stale."""
    cached = await _read_cache(db)
    if cached is not None:
        trends, computed_at = cached
        age = datetime.now(timezone.utc) - computed_at
        if age <= timedelta(hours=max_age_hours):
            return trends

    trends = await compute_category_trends(db)
    await _write_cache(db, trends)
    return trends


async def get_category_trend(
    db: AsyncSession, category_id: uuid.UUID | str | None
) -> float:
    """Single-category lookup with fallback to the neutral signal."""
    if category_id is None:
        return NEUTRAL_TREND
    trends = await get_category_trends(db)
    return trends.get(str(category_id), NEUTRAL_TREND)


async def refresh_cache(db: AsyncSession) -> dict[str, float]:
    """Force a cache refresh — used by the monthly scoring cron."""
    trends = await compute_category_trends(db)
    await _write_cache(db, trends)
    return trends
