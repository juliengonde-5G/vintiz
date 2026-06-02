"""Métriques de gestion du stock & rythmes de rotation (mouvements de stock).

Trois familles de métriques, agrégées sur une fenêtre glissante :

1. **Répartition Réserve / Rayon** : combien de pièces (et quelle valeur) sont
   en réserve (cave) vs en rayon, le ratio de mise en rayon, le pré-rayon
   (réceptionné/trié/étiqueté pas encore monté).

2. **Vitesse de rotation** : délai moyen réserve→rayon (``received_at`` →
   ``displayed_at``), délai moyen de vente en rayon (``displayed_at`` →
   ``sold_at`` sur la fenêtre), et taux d'écoulement (sell-through).

3. **Rythmes de rotation** : à partir du ledger ``product_location_events`` —
   rythme VERTICAL (mises en rayon + retours réserve / semaine) et rythme
   HORIZONTAL (changements de zone / semaine), avec séries journalières.

Les diffs de dates sont calculés en Python (timestamps bruts) pour rester
portables SQLite (tests) ↔ PostgreSQL, comme ``retail_kpis.days_on_hand``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Product, ProductStatus
from app.models.product_location import LocationMoveType, ProductLocationEvent

_FLOOR = (
    ProductStatus.display,
    ProductStatus.displayed,
    ProductStatus.discounted,
    ProductStatus.deep_discounted,
)
_PRE_FLOOR = (
    ProductStatus.received,
    ProductStatus.sorted,
    ProductStatus.tagged,
)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


async def _status_snapshot(db: AsyncSession) -> dict:
    """Current count + valuation per status, folded into réserve / rayon."""
    rows = (await db.execute(
        select(
            Product.status,
            func.count(Product.id),
            func.coalesce(func.sum(Product.sale_price), 0),
            func.coalesce(func.sum(Product.purchase_price), 0),
        )
        .where(Product.is_test.is_(False))
        .group_by(Product.status)
    )).all()

    def _bucket(statuses) -> dict:
        n = sum(int(r[1]) for r in rows if r[0] in statuses)
        sale = sum(float(r[2]) for r in rows if r[0] in statuses)
        purchase = sum(float(r[3]) for r in rows if r[0] in statuses)
        return {"count": n, "sale_value": round(sale, 2), "purchase_value": round(purchase, 2)}

    reserve = _bucket({ProductStatus.stock})
    floor = _bucket(set(_FLOOR))
    pre_floor = _bucket(set(_PRE_FLOOR))

    active = reserve["count"] + floor["count"]
    return {
        "reserve": reserve,
        "floor": floor,
        "pre_floor": pre_floor,
        "active_count": active,
        # Part du stock vendable effectivement présentée au client.
        "floor_ratio": round(floor["count"] / active, 4) if active else None,
        "reserve_ratio": round(reserve["count"] / active, 4) if active else None,
    }


async def _rotation_velocity(
    db: AsyncSession, *, start: datetime, now: datetime
) -> dict:
    """Time-in-stock before display + time-on-floor before sale + sell-through."""
    # Délai réserve → rayon : sur les pièces actuellement en rayon ayant les
    # deux ancres (received_at, displayed_at).
    floor_rows = (await db.execute(
        select(Product.received_at, Product.displayed_at)
        .where(Product.status.in_(_FLOOR))
    )).all()
    time_to_floor: list[float] = []
    for received_at, displayed_at in floor_rows:
        r, d = _aware(received_at), _aware(displayed_at)
        if r and d and d >= r:
            time_to_floor.append((d - r).total_seconds() / 86400.0)

    # Délai de vente en rayon : pièces vendues sur la fenêtre.
    sold_rows = (await db.execute(
        select(Product.displayed_at, Product.sold_at)
        .where(
            Product.status == ProductStatus.sold,
            Product.sold_at.is_not(None),
            Product.sold_at >= start,
            Product.sold_at < now,
        )
    )).all()
    time_on_floor: list[float] = []
    for displayed_at, sold_at in sold_rows:
        d, s = _aware(displayed_at), _aware(sold_at)
        if d and s and s >= d:
            time_on_floor.append((s - d).total_seconds() / 86400.0)

    # Sell-through sur la fenêtre : vendus / (vendus + présents en rayon).
    items_sold = int((await db.execute(
        select(func.coalesce(func.sum(TransactionItem.quantity), 0))
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= start,
            Transaction.created_at < now,
        )
    )).scalar_one() or 0)
    on_floor_count = int((await db.execute(
        select(func.count(Product.id)).where(Product.status.in_(_FLOOR))
    )).scalar_one() or 0)
    denom = items_sold + on_floor_count

    return {
        "avg_days_reserve_to_floor": _avg(time_to_floor),
        "avg_days_on_floor_before_sale": _avg(time_on_floor),
        "items_sold": items_sold,
        "on_floor_count": on_floor_count,
        "sell_through_rate": round(items_sold / denom, 4) if denom else 0.0,
    }


async def _movement_rhythm(
    db: AsyncSession, *, start: datetime, now: datetime, period_days: int
) -> dict:
    """Vertical (réserve↔rayon) + horizontal (zone↔zone) cadence from the ledger."""
    # Totals per move type over the window.
    type_rows = (await db.execute(
        select(ProductLocationEvent.move_type, func.count(ProductLocationEvent.id))
        .where(
            ProductLocationEvent.occurred_at >= start,
            ProductLocationEvent.occurred_at < now,
        )
        .group_by(ProductLocationEvent.move_type)
    )).all()
    counts = {mt.value if isinstance(mt, LocationMoveType) else str(mt): int(n)
              for mt, n in type_rows}

    to_floor = counts.get(LocationMoveType.to_floor.value, 0)
    to_stock = counts.get(LocationMoveType.to_stock.value, 0)
    zone_change = counts.get(LocationMoveType.zone_change.value, 0)
    vertical_total = to_floor + to_stock

    weeks = max(period_days / 7.0, 1e-9)
    days = max(period_days, 1)

    # Daily series (portable func.date) for the sparkline.
    series_rows = (await db.execute(
        select(
            func.date(ProductLocationEvent.occurred_at).label("day"),
            ProductLocationEvent.move_type,
            func.count(ProductLocationEvent.id),
        )
        .where(
            ProductLocationEvent.occurred_at >= start,
            ProductLocationEvent.occurred_at < now,
        )
        .group_by(func.date(ProductLocationEvent.occurred_at), ProductLocationEvent.move_type)
        .order_by(func.date(ProductLocationEvent.occurred_at))
    )).all()
    by_day: dict[str, dict] = {}
    for day, mt, n in series_rows:
        key = str(day)
        slot = by_day.setdefault(key, {"day": key, "vertical": 0, "horizontal": 0})
        mtv = mt.value if isinstance(mt, LocationMoveType) else str(mt)
        if mtv in (LocationMoveType.to_floor.value, LocationMoveType.to_stock.value):
            slot["vertical"] += int(n)
        elif mtv == LocationMoveType.zone_change.value:
            slot["horizontal"] += int(n)

    # Top zones by horizontal churn (where the weekly reshuffle concentrates).
    churn_rows = (await db.execute(
        select(ProductLocationEvent.to_zone_id, func.count(ProductLocationEvent.id))
        .where(
            ProductLocationEvent.move_type == LocationMoveType.zone_change,
            ProductLocationEvent.occurred_at >= start,
            ProductLocationEvent.occurred_at < now,
            ProductLocationEvent.to_zone_id.is_not(None),
        )
        .group_by(ProductLocationEvent.to_zone_id)
        .order_by(func.count(ProductLocationEvent.id).desc())
        .limit(5)
    )).all()

    return {
        "vertical": {
            "to_floor": to_floor,
            "to_stock": to_stock,
            "total": vertical_total,
            "per_week": round(vertical_total / weeks, 2),
            "per_day": round(vertical_total / days, 2),
        },
        "horizontal": {
            "zone_changes": zone_change,
            "per_week": round(zone_change / weeks, 2),
            "per_day": round(zone_change / days, 2),
            "top_target_zones": [
                {"zone_id": str(zid), "moves": int(n)} for zid, n in churn_rows
            ],
        },
        "exits": counts.get(LocationMoveType.exit.value, 0),
        "intakes": counts.get(LocationMoveType.intake.value, 0),
        "daily_series": list(by_day.values()),
    }


async def stock_movement_metrics(
    db: AsyncSession, *, period_days: int = 30, now: datetime | None = None
) -> dict:
    """Top-level metric bundle for ``GET /api/reports/stock-movement``."""
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=period_days)

    snapshot = await _status_snapshot(db)
    velocity = await _rotation_velocity(db, start=start, now=now)
    rhythm = await _movement_rhythm(db, start=start, now=now, period_days=period_days)

    return {
        "period_days": period_days,
        "period_start": start.isoformat(),
        "period_end": now.isoformat(),
        "repartition": snapshot,
        "velocity": velocity,
        "rhythm": rhythm,
    }
