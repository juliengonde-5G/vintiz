"""Predictive engine — audience-aware targeting (PR4).

Two helpers exposed:

- :func:`weighted_sales_count` — returns the count of *sale items* in a
  category over a window, with a multiplier on items sold to clients
  with an active loyalty membership. Hooked into the scoring service
  via the ``audience`` parameter.

- :func:`dominant_tastes_loyal_active` — aggregates the top categories,
  brands and colors purchased by the loyalty-active cohort over the
  last N days. Powers an admin debug endpoint and (later) the window
  display generator.

The cohort eligibility mirrors :func:`loyalty.loyalty_active`: a client
is "loyal_active" if they hold a non-expired loyalty account.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client import Client, LoyaltyAccount
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Product


LOYAL_ACTIVE_MULTIPLIER = 2.0
# Below this cohort size, fall back to a flat audience to avoid biasing
# the scoring on noise.
MIN_COHORT_SIZE = 30


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _is_loyal_active(client: Client | None) -> bool:
    if client is None or client.loyalty_account is None:
        return False
    expires = _aware(client.loyalty_expires_at)
    if expires is None:
        return True
    return expires > datetime.now(timezone.utc)


@dataclass
class DominantTastes:
    top_categories: list[tuple[str, int]]
    top_brands: list[tuple[str, int]]
    top_colors: list[tuple[str, int]]
    top_sizes: list[tuple[str, int]]
    cohort_size: int
    period_days: int


async def weighted_sales_count(
    db: AsyncSession,
    *,
    audience: str = "all",
    window_days: int = 90,
) -> dict[str, float]:
    """Return ``{category_id: weighted_count}`` over the last ``window_days``.

    With ``audience="all"`` the count is plain (one item = 1). With
    ``audience="loyal_active"`` items sold to a loyalty-active client
    count for :data:`LOYAL_ACTIVE_MULTIPLIER` × 1, the rest count for 1.

    Falls back to a flat count when the loyalty cohort is too small to
    avoid pathological scores in early-life prod.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    rows = await db.execute(
        select(Product.category_id, Transaction.client_id)
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= cutoff,
            Product.category_id.is_not(None),
        )
    )
    raw = rows.all()

    if audience != "loyal_active":
        weighted: dict[str, float] = {}
        for cat_id, _ in raw:
            weighted[str(cat_id)] = weighted.get(str(cat_id), 0.0) + 1.0
        return weighted

    # Resolve loyalty status for the clients involved (one query, not N).
    client_ids = {c for _, c in raw if c is not None}
    if not client_ids:
        return {}
    cohort_rows = await db.execute(
        select(Client.id, Client.loyalty_expires_at)
        .join(LoyaltyAccount, LoyaltyAccount.client_id == Client.id)
        .where(Client.id.in_(client_ids))
    )
    now = datetime.now(timezone.utc)
    loyal_active_ids: set = set()
    for cid, expires in cohort_rows.all():
        expires = _aware(expires)
        if expires is None or expires > now:
            loyal_active_ids.add(cid)

    if len(loyal_active_ids) < MIN_COHORT_SIZE:
        # Cohort too small — degrade gracefully to flat counting so the
        # scoring isn't whipsawed by a few power users.
        weighted = {}
        for cat_id, _ in raw:
            weighted[str(cat_id)] = weighted.get(str(cat_id), 0.0) + 1.0
        return weighted

    weighted = {}
    for cat_id, client_id in raw:
        weight = LOYAL_ACTIVE_MULTIPLIER if client_id in loyal_active_ids else 1.0
        weighted[str(cat_id)] = weighted.get(str(cat_id), 0.0) + weight
    return weighted


async def dominant_tastes_loyal_active(
    db: AsyncSession, *, period_days: int = 90, top_n: int = 10
) -> DominantTastes:
    """Aggregate top tastes over the loyalty-active cohort."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

    rows = await db.execute(
        select(Product, Transaction.client_id)
        .options(selectinload(Product.category))
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= cutoff,
            Transaction.client_id.is_not(None),
        )
    )
    pairs = rows.all()

    client_ids = {c for _, c in pairs}
    cohort_rows = await db.execute(
        select(Client.id, Client.loyalty_expires_at)
        .join(LoyaltyAccount, LoyaltyAccount.client_id == Client.id)
        .where(Client.id.in_(client_ids))
    )
    now = datetime.now(timezone.utc)
    loyal_active: set = set()
    for cid, expires in cohort_rows.all():
        expires = _aware(expires)
        if expires is None or expires > now:
            loyal_active.add(cid)

    cat_counter: Counter[str] = Counter()
    brand_counter: Counter[str] = Counter()
    color_counter: Counter[str] = Counter()
    size_counter: Counter[str] = Counter()
    for product, client_id in pairs:
        if client_id not in loyal_active:
            continue
        if product.category and product.category.name:
            cat_counter[product.category.name] += 1
        if product.brand:
            brand_counter[product.brand] += 1
        if product.color:
            color_counter[product.color.lower()] += 1
        if product.size:
            size_counter[product.size] += 1

    return DominantTastes(
        top_categories=cat_counter.most_common(top_n),
        top_brands=brand_counter.most_common(top_n),
        top_colors=color_counter.most_common(top_n),
        top_sizes=size_counter.most_common(top_n),
        cohort_size=len(loyal_active),
        period_days=period_days,
    )


def serialize_dominant(d: DominantTastes) -> dict:
    return {
        "top_categories": [{"name": n, "count": c} for n, c in d.top_categories],
        "top_brands": [{"name": n, "count": c} for n, c in d.top_brands],
        "top_colors": [{"name": n, "count": c} for n, c in d.top_colors],
        "top_sizes": [{"name": n, "count": c} for n, c in d.top_sizes],
        "cohort_size": d.cohort_size,
        "period_days": d.period_days,
    }
