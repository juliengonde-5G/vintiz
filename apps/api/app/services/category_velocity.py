"""Compute the 90-day sales velocity per category.

Used by the v3 scoring engine for the *Attractivity* criterion. Cached in
``app_settings`` under the key ``category_velocity_cache_v1`` (refreshed by
the Monday weekly cron, with TTL 24h as a safety net).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Settings
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Product


SETTINGS_KEY = "category_velocity_cache_v1"
WINDOW_DAYS = 90
TTL_HOURS = 24


async def compute_category_velocity(db: AsyncSession) -> dict[str, float]:
    """Return ``{category_id: sales_per_week}`` for the last 90 days.

    A category that sold 50 units over 90 days has velocity ≈ 3.9 / week.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    weeks = WINDOW_DAYS / 7.0

    result = await db.execute(
        select(
            Product.category_id,
            func.count(TransactionItem.id).label("n_sold"),
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
    raw = {str(row[0]): int(row[1]) / weeks for row in result.all()}
    return raw


async def get_velocity_cache(db: AsyncSession) -> dict[str, float]:
    """Read the cached velocities. Falls back to computing them if expired."""
    row = (
        await db.execute(select(Settings).where(Settings.key == SETTINGS_KEY))
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if row and row.value:
        try:
            payload = json.loads(row.value)
            cached_at = datetime.fromisoformat(payload.get("cached_at"))
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            if now - cached_at < timedelta(hours=TTL_HOURS):
                return payload.get("velocity", {})
        except Exception:
            pass

    fresh = await compute_category_velocity(db)
    new_value = json.dumps({"cached_at": now.isoformat(), "velocity": fresh})
    if row:
        row.value = new_value
    else:
        db.add(Settings(key=SETTINGS_KEY, value=new_value, description="90j sales velocity per category"))
    await db.flush()
    return fresh


async def refresh_cache(db: AsyncSession) -> dict[str, float]:
    """Force-refresh and persist the cache. Called by the Monday cron."""
    fresh = await compute_category_velocity(db)
    payload = json.dumps(
        {"cached_at": datetime.now(timezone.utc).isoformat(), "velocity": fresh}
    )
    row = (
        await db.execute(select(Settings).where(Settings.key == SETTINGS_KEY))
    ).scalar_one_or_none()
    if row:
        row.value = payload
    else:
        db.add(Settings(key=SETTINGS_KEY, value=payload, description="90j sales velocity per category"))
    await db.flush()
    return fresh


async def get_velocity_for_category(db: AsyncSession, category_id) -> float:
    if category_id is None:
        return 0.0
    cache = await get_velocity_cache(db)
    return float(cache.get(str(category_id), 0.0))


async def top_categories(db: AsyncSession, limit: int = 10) -> list[dict]:
    """Return the top-N categories by velocity, joined with their human name.

    Used by the admin scoring page to show the attractivity breakdown.
    """
    cache = await get_velocity_cache(db)
    if not cache:
        return []
    cat_rows = (await db.execute(select(Category))).scalars().all()
    name_by_id = {str(c.id): c.name for c in cat_rows}
    pairs = sorted(cache.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [
        {
            "category_id": cid,
            "category_name": name_by_id.get(cid, "(inconnue)"),
            "sales_per_week": round(velocity, 2),
        }
        for cid, velocity in pairs
    ]
