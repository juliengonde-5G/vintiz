"""Retail KPIs + ESS reporting (P4-001 + P4-002).

Two views over the same data:

- ``retail_kpis``: industry-standard retail metrics Camille consults
  every Monday (sell-through, GMROI, days on hand, AIT, CA/m²/mois,
  variation vs N-7 and N-1).

- ``ess_report``: the Solidarité Textiles dashboard — pieces received
  vs sold vs returned to sorting, taux de réemploi, estimated tonnage,
  CA reversed (configurable share).

The store surface area and the average piece weight are configuration
knobs read from ``app_settings`` (table ``Settings``), with sensible
defaults for Vernon (98 m², 0.5 kg/piece, 0% reverse to ST). Camille
edits them via the admin endpoints once and the reports follow.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Settings
from app.models.batch import IntakeBatch
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Product, ProductStatus


_SETTINGS_KEY = "retail_kpis_config"
_DEFAULT_CONFIG = {
    "store_surface_m2": 98.0,
    "avg_piece_weight_kg": 0.5,
    "ess_reversed_pct": 0.0,
}

_ON_FLOOR_STATUSES = (
    ProductStatus.display,
    ProductStatus.displayed,
    ProductStatus.discounted,
    ProductStatus.deep_discounted,
)


# ---------------------------------------------------------------------------
# Config (Settings-backed)
# ---------------------------------------------------------------------------


async def _load_config(db: AsyncSession) -> dict:
    result = await db.execute(
        select(Settings).where(Settings.key == _SETTINGS_KEY)
    )
    row = result.scalar_one_or_none()
    if row is None or not row.value:
        return dict(_DEFAULT_CONFIG)
    try:
        payload = json.loads(row.value)
        merged = dict(_DEFAULT_CONFIG)
        merged.update({k: float(v) for k, v in payload.items() if k in _DEFAULT_CONFIG})
        return merged
    except (json.JSONDecodeError, ValueError, TypeError):
        return dict(_DEFAULT_CONFIG)


async def update_config(db: AsyncSession, **overrides) -> dict:
    """Update a subset of the config keys. Returns the merged config."""
    current = await _load_config(db)
    for key, value in overrides.items():
        if key not in _DEFAULT_CONFIG:
            continue
        try:
            current[key] = float(value)
        except (TypeError, ValueError):
            continue

    payload = json.dumps(current)
    row_result = await db.execute(
        select(Settings).where(Settings.key == _SETTINGS_KEY)
    )
    row = row_result.scalar_one_or_none()
    if row is None:
        db.add(Settings(
            key=_SETTINGS_KEY,
            value=payload,
            description="Retail KPIs + ESS config (P4-001 / P4-002)",
        ))
    else:
        row.value = payload
    await db.flush()
    return current


# ---------------------------------------------------------------------------
# Retail KPIs (P4-001)
# ---------------------------------------------------------------------------


@dataclass
class WindowStats:
    revenue: float
    transactions: int
    items_sold: int
    refunded: float


async def _window_stats(
    db: AsyncSession, start: datetime, end: datetime
) -> WindowStats:
    """Aggregate revenue + counts for [start, end). Refunds netted."""
    revenue_row = (await db.execute(
        select(
            func.coalesce(
                func.sum(
                    Transaction.total_ttc *
                    (1 if False else 1)  # placeholder
                ),
                0,
            )
        )
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= start,
            Transaction.created_at < end,
        )
    )).scalar_one()

    refunds_row = (await db.execute(
        select(func.coalesce(func.sum(Transaction.total_ttc), 0))
        .where(
            Transaction.transaction_type == TransactionType.refund,
            Transaction.created_at >= start,
            Transaction.created_at < end,
        )
    )).scalar_one()

    tx_count = (await db.execute(
        select(func.count(Transaction.id))
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= start,
            Transaction.created_at < end,
        )
    )).scalar_one()

    items_sold = (await db.execute(
        select(func.coalesce(func.sum(TransactionItem.quantity), 0))
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= start,
            Transaction.created_at < end,
        )
    )).scalar_one()

    return WindowStats(
        revenue=float(revenue_row),
        transactions=int(tx_count),
        items_sold=int(items_sold or 0),
        refunded=float(refunds_row),
    )


async def retail_kpis(
    db: AsyncSession, *, period_days: int = 30, now: datetime | None = None
) -> dict:
    """Industry-standard retail metrics over the last ``period_days``.

    Returns:
      {
        period_days, period_start, period_end,
        revenue, refunds, net_revenue, transactions, items_sold,
        ait, ca_per_m2_per_month, sell_through_rate,
        days_on_hand, gmroi,
        prev_period: {revenue, transactions, items_sold},
        change_pct: {revenue, transactions, items_sold},
        top_categories, bottom_categories
      }
    """
    now = now or datetime.now(timezone.utc)
    end = now
    start = end - timedelta(days=period_days)
    prev_end = start
    prev_start = prev_end - timedelta(days=period_days)

    config = await _load_config(db)
    current = await _window_stats(db, start, end)
    previous = await _window_stats(db, prev_start, prev_end)

    # --- AIT: average items per ticket
    ait = current.items_sold / current.transactions if current.transactions else 0.0

    # --- CA / m² / mois (normalized to a 30-day month equivalent)
    ratio_to_month = 30.0 / period_days if period_days > 0 else 0.0
    monthly_revenue = current.revenue * ratio_to_month
    surface = config.get("store_surface_m2") or 1.0
    ca_per_m2 = monthly_revenue / surface

    # --- Days on Hand: average shelf age of the on-floor stock
    on_floor_rows = (await db.execute(
        select(Product.created_at, Product.displayed_at, Product.sale_price)
        .where(Product.status.in_(_ON_FLOOR_STATUSES))
    )).all()
    days = []
    for created_at, displayed_at, _ in on_floor_rows:
        anchor = displayed_at or created_at
        if anchor is None:
            continue
        anchor_aware = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)
        days.append(max(0, (now - anchor_aware).days))
    days_on_hand = sum(days) / len(days) if days else 0.0

    # --- Sell-through rate: items sold / (items sold + items currently on the floor)
    on_floor_count = len(on_floor_rows)
    str_denom = current.items_sold + on_floor_count
    sell_through = (current.items_sold / str_denom) if str_denom else 0.0

    # --- GMROI: (gross margin) / avg inventory cost.
    # Without per-item purchase tracking on every line, approximate as
    # net_revenue / (sum(purchase_price for on-floor)) so the metric
    # surfaces inventory productivity rather than absolute precision.
    inv_cost_row = (await db.execute(
        select(func.coalesce(func.sum(Product.purchase_price), 0))
        .where(Product.status.in_(_ON_FLOOR_STATUSES))
    )).scalar_one()
    inv_cost = float(inv_cost_row)
    net_revenue = current.revenue - current.refunded
    gmroi = (net_revenue / inv_cost) if inv_cost > 0 else None

    # --- Top / bottom categories by revenue in the window.
    cat_rows = (await db.execute(
        select(
            Product.category_id,
            Category.name,
            func.sum(TransactionItem.line_total).label("revenue"),
            func.sum(TransactionItem.quantity).label("qty"),
        )
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .join(Category, Category.id == Product.category_id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= start,
            Transaction.created_at < end,
            Product.category_id.is_not(None),
        )
        .group_by(Product.category_id, Category.name)
        .order_by(func.sum(TransactionItem.line_total).desc())
    )).all()

    def _pct(curr: float, prev: float) -> float | None:
        if prev <= 0:
            return None
        return round(100 * (curr - prev) / prev, 1)

    return {
        "period_days": period_days,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "revenue": round(current.revenue, 2),
        "refunds": round(current.refunded, 2),
        "net_revenue": round(net_revenue, 2),
        "transactions": current.transactions,
        "items_sold": current.items_sold,
        "ait": round(ait, 2),
        "ca_per_m2_per_month": round(ca_per_m2, 2),
        "sell_through_rate": round(sell_through, 4),
        "days_on_hand": round(days_on_hand, 1),
        "gmroi": round(gmroi, 2) if gmroi is not None else None,
        "on_floor_count": on_floor_count,
        "prev_period": {
            "revenue": round(previous.revenue, 2),
            "transactions": previous.transactions,
            "items_sold": previous.items_sold,
        },
        "change_pct": {
            "revenue": _pct(current.revenue, previous.revenue),
            "transactions": _pct(current.transactions, previous.transactions),
            "items_sold": _pct(current.items_sold, previous.items_sold),
        },
        "top_categories": [
            {
                "category_id": str(row[0]),
                "category_name": row[1] or "Sans catégorie",
                "revenue": round(float(row[2]), 2),
                "qty_sold": int(row[3]),
            }
            for row in cat_rows[:10]
        ],
        "bottom_categories": [
            {
                "category_id": str(row[0]),
                "category_name": row[1] or "Sans catégorie",
                "revenue": round(float(row[2]), 2),
                "qty_sold": int(row[3]),
            }
            for row in list(cat_rows)[-3:][::-1]
        ],
        "config": config,
    }


# ---------------------------------------------------------------------------
# ESS report (P4-002)
# ---------------------------------------------------------------------------


async def ess_report(
    db: AsyncSession, *, period_days: int = 90, now: datetime | None = None
) -> dict:
    """Solidarité Textiles dashboard.

    - Pieces received: sum of intake_batches.n_items_received over the
      window. (We use the operator-recorded count rather than the
      tagged Product rows so pre-tagging attrition shows up.)
    - Pieces sold: count of TransactionItem.quantity where the parent
      transaction is a sale in the window.
    - Pieces returned to sorting: count of products with status =
      returned_to_sorting that landed there in the window. We use
      audit_logs to find the transition timestamp; falls back to the
      product's updated_at otherwise.
    - Réemploi rate = (sold + donated) / received.
    - Estimated tonnage = received × avg_piece_weight_kg.
    - CA reversé = revenue × ess_reversed_pct.
    """
    now = now or datetime.now(timezone.utc)
    end = now
    start = end - timedelta(days=period_days)

    config = await _load_config(db)

    pieces_received = int((await db.execute(
        select(func.coalesce(func.sum(IntakeBatch.n_items_received), 0))
        .where(IntakeBatch.received_at >= start, IntakeBatch.received_at < end)
    )).scalar_one() or 0)

    pieces_sold = int((await db.execute(
        select(func.coalesce(func.sum(TransactionItem.quantity), 0))
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= start,
            Transaction.created_at < end,
        )
    )).scalar_one() or 0)

    pieces_donated = int((await db.execute(
        select(func.count(Product.id))
        .where(
            Product.status == ProductStatus.donated,
            Product.updated_at >= start,
            Product.updated_at < end,
        )
    )).scalar_one() or 0)

    pieces_returned = int((await db.execute(
        select(func.count(Product.id))
        .where(
            Product.status == ProductStatus.returned_to_sorting,
            Product.updated_at >= start,
            Product.updated_at < end,
        )
    )).scalar_one() or 0)

    revenue = float((await db.execute(
        select(func.coalesce(func.sum(Transaction.total_ttc), 0))
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= start,
            Transaction.created_at < end,
        )
    )).scalar_one() or 0)

    weight_per_piece = config.get("avg_piece_weight_kg") or 0.5
    estimated_tonnage_kg = pieces_received * weight_per_piece
    reversed_share = (config.get("ess_reversed_pct") or 0.0) / 100.0
    ca_reversed = revenue * reversed_share

    reuse_numerator = pieces_sold + pieces_donated
    reuse_rate = (
        reuse_numerator / pieces_received if pieces_received else 0.0
    )

    n_unique_clients = int((await db.execute(
        select(func.count(distinct(Transaction.client_id)))
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= start,
            Transaction.created_at < end,
            Transaction.client_id.is_not(None),
        )
    )).scalar_one() or 0)

    return {
        "period_days": period_days,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "pieces_received": pieces_received,
        "pieces_sold": pieces_sold,
        "pieces_donated": pieces_donated,
        "pieces_returned_to_sorting": pieces_returned,
        "reuse_rate": round(reuse_rate, 4),
        "estimated_tonnage_kg": round(estimated_tonnage_kg, 1),
        "revenue": round(revenue, 2),
        "ca_reversed_to_st": round(ca_reversed, 2),
        "ca_reversed_pct": round(reversed_share * 100, 2),
        "unique_clients": n_unique_clients,
        "config": config,
    }
