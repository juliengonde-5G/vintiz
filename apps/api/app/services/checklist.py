"""Weekly checklist generators (Lot 4).

Each function builds (or refreshes) a ``WeeklyTask`` row for the day it
runs. Cron triggers live in ``app/jobs.py``; the manager can also fire
them manually from ``/api/checklist/regenerate``.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductStatus
from app.models.weekly_task import WeeklyTask, WeeklyTaskKind, WeeklyTaskStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _upsert_task(
    db: AsyncSession, *, kind: WeeklyTaskKind, scheduled_for: date, payload: dict
) -> WeeklyTask:
    """Replace any existing pending task of the same kind for that day."""
    existing = (
        await db.execute(
            select(WeeklyTask).where(
                WeeklyTask.kind == kind,
                WeeklyTask.scheduled_for == scheduled_for,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.payload = payload
        existing.status = WeeklyTaskStatus.pending
        return existing
    task = WeeklyTask(
        kind=kind,
        scheduled_for=scheduled_for,
        payload=payload,
        status=WeeklyTaskStatus.pending,
    )
    db.add(task)
    await db.flush()
    return task


def _weeks_on_shelf(shelf_date: datetime | None, now: datetime) -> int:
    if shelf_date is None:
        return 0
    if shelf_date.tzinfo is None:
        shelf_date = shelf_date.replace(tzinfo=timezone.utc)
    return max(0, (now - shelf_date).days // 7)


# ---------------------------------------------------------------------------
# Thursday — sortie automatique des produits ≥ 6 semaines
# ---------------------------------------------------------------------------


async def run_thursday_six_weeks_exit(db: AsyncSession) -> dict:
    """List + transition products that crossed the 6-week shelf horizon.

    Uses ``ProductLifecycleService`` so the transition emits the right
    audit log + event. Returns a summary used by both the cron and the
    manual trigger.
    """
    from app.services.product_lifecycle import ProductLifecycleService

    now = datetime.now(timezone.utc)
    today = now.date()

    rows = (
        await db.execute(
            select(Product).where(
                Product.status.in_(
                    [
                        ProductStatus.stock,
                        ProductStatus.display,
                        ProductStatus.displayed,
                        ProductStatus.discounted,
                        ProductStatus.deep_discounted,
                    ]
                )
            )
        )
    ).scalars().all()

    eligible: list[Product] = [
        p for p in rows if _weeks_on_shelf(p.shelf_date, now) >= 6
    ]
    payload_items: list[dict] = []
    transitioned = 0
    lifecycle = ProductLifecycleService(db)

    for product in eligible:
        weeks = _weeks_on_shelf(product.shelf_date, now)
        payload_items.append(
            {
                "product_id": str(product.id),
                "barcode": product.barcode,
                "name": product.name,
                "weeks_on_shelf": weeks,
                "from_status": product.status.value,
            }
        )
        try:
            await lifecycle.transition(
                product,
                ProductStatus.returned_to_sorting,
                reason="6 weeks on shelf — automatic Thursday exit",
                move_source="cron",
            )
            transitioned += 1
        except Exception:
            # The lifecycle service raises on invalid transitions (e.g.
            # already in a terminal state). We log via the audit trail
            # already; just skip the row here.
            pass

    payload = {
        "items": payload_items,
        "transitioned": transitioned,
        "total_eligible": len(eligible),
    }
    await _upsert_task(
        db,
        kind=WeeklyTaskKind.thursday_six_weeks_exit,
        scheduled_for=today,
        payload=payload,
    )
    return payload


# ---------------------------------------------------------------------------
# Morning restock (each day at 8 a.m. except Monday)
# ---------------------------------------------------------------------------


async def run_morning_restock(db: AsyncSession) -> dict:
    """List products in stock not yet on display — to be put on the floor."""
    today = datetime.now(timezone.utc).date()

    rows = (
        await db.execute(
            select(Product).where(
                Product.status == ProductStatus.stock,
                Product.is_test.is_(False),
            )
        )
    ).scalars().all()

    items = [
        {
            "product_id": str(p.id),
            "barcode": p.barcode,
            "name": p.name,
            "category": p.category.name if p.category else None,
            "zone_id": str(p.zone_id) if p.zone_id else None,
        }
        for p in rows[:30]  # cap to keep the UI snappy
    ]
    payload = {"items": items, "total": len(rows)}
    await _upsert_task(
        db,
        kind=WeeklyTaskKind.morning_restock,
        scheduled_for=today,
        payload=payload,
    )
    return payload


# ---------------------------------------------------------------------------
# Monday — repositioning hint + scoring refresh follow-up
# ---------------------------------------------------------------------------


async def run_monday_position_reco(db: AsyncSession) -> dict:
    """List products whose score dropped below 50 and suggest moving them."""
    rows = (
        await db.execute(
            select(Product).where(
                Product.status.in_(
                    [ProductStatus.display, ProductStatus.displayed]
                ),
                Product.trend_score.is_not(None),
                Product.trend_score < 50,
            )
        )
    ).scalars().all()
    items = [
        {
            "product_id": str(p.id),
            "barcode": p.barcode,
            "name": p.name,
            "trend_score": float(p.trend_score or 0),
            "current_zone_id": str(p.zone_id) if p.zone_id else None,
        }
        for p in rows[:50]
    ]
    payload = {"items": items, "total": len(rows)}
    await _upsert_task(
        db,
        kind=WeeklyTaskKind.monday_scoring_update,
        scheduled_for=datetime.now(timezone.utc).date(),
        payload=payload,
    )
    return payload
