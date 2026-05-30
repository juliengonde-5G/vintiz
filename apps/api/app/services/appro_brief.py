"""Approvisionnement brief — demande → appro prescriptif (PS 360 V5, §7.3).

The boutique's real lever: stop being reactive ("I recommend what's in stock")
and become prescriptive ("demand drives what we bring in"). This service turns
the aggregated demand signals into **carton-level** recommendations by
**catégorie × genre × qualité** — the granularity the sorting centre can act on
(it can't deliver by size/colour).

Signals (audit §7.3), degrading gracefully at cold-start:
1. Dominant tastes of the loyalty-active cohort (purchases) —
   ``predictive_targeting.dominant_tastes_loyal_active``.
2. Member gender skew (declarative ``Client.gender_profile``).
3. Current in-stock supply per category × gender.
(Unsatisfied PS searches + sell-through plug in here once volume exists.)

Read-only, cron-free: computed on demand for the IA Booster screen. Connecting
it to the sorting centre is a deliberate 2nd step (décision #5).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.product import Category, Product, ProductStatus
from app.services.predictive_targeting import dominant_tastes_loyal_active

BRIEF_VERSION = "appro-brief-v1-2026-05"

# Below this absolute count, a category cell is thin enough to warrant a carton
# even without a strong purchase signal (cold-start).
LOW_STOCK_THRESHOLD = 3


async def _stock_by_category(db: AsyncSession) -> dict[str, int]:
    """In-stock count per (lowercased) category name."""
    rows = await db.execute(
        select(Category.name, func.count(Product.id))
        .join(Product, Product.category_id == Category.id)
        .where(Product.status.in_([ProductStatus.stock, ProductStatus.display]))
        .group_by(Category.name)
    )
    return {name.lower(): int(c) for name, c in rows.all() if name}


async def _member_gender_skew(db: AsyncSession) -> dict[str, int]:
    rows = await db.execute(
        select(Client.gender_profile, func.count(Client.id))
        .where(Client.gender_profile.is_not(None))
        .group_by(Client.gender_profile)
    )
    return {g: int(c) for g, c in rows.all() if g}


async def build_appro_brief(
    db: AsyncSession, *, period_days: int = 90, max_lines: int = 8
) -> dict:
    """Build the weekly approvisionnement brief. See module docstring."""
    tastes = await dominant_tastes_loyal_active(db, period_days=period_days)
    demand_cats = tastes.top_categories  # [(name, count)]
    top_brands = [b for b, _ in tastes.top_brands]
    total_demand = sum(c for _, c in demand_cats) or 1

    stock = await _stock_by_category(db)
    total_stock = sum(stock.values()) or 1
    gender_skew = await _member_gender_skew(db)
    dominant_gender = (
        max(gender_skew, key=gender_skew.get) if gender_skew else "mixte"
    )
    cold_start = not demand_cats

    quality_hint = "premium"  # Vintiz positioning; sharpened by the demanded brands
    brands_label = ", ".join(top_brands[:3]) if top_brands else "marques premium"

    lines: list[dict] = []

    if demand_cats:
        for name, count in demand_cats[:max_lines]:
            cat = (name or "").lower()
            if not cat:
                continue
            demand_share = count / total_demand
            cat_stock = stock.get(cat, 0)
            stock_share = cat_stock / total_stock
            gap = demand_share - stock_share
            if gap > 0.05 or cat_stock <= LOW_STOCK_THRESHOLD:
                action = "demander"
                rationale = (
                    f"Demande {demand_share:.0%} vs stock {stock_share:.0%} "
                    f"({cat_stock} pièces) — carton à demander."
                )
            elif stock_share - demand_share > 0.10:
                action = "reduire"
                rationale = (
                    f"Sur-stock : {stock_share:.0%} du stock pour {demand_share:.0%} "
                    f"de la demande — réduire les arrivages."
                )
            else:
                action = "maintenir"
                rationale = f"Offre alignée sur la demande ({demand_share:.0%})."
            lines.append({
                "category": cat,
                "gender": dominant_gender,
                "quality_hint": quality_hint,
                "action": action,
                "demand_share": round(demand_share, 3),
                "stock_count": cat_stock,
                "brands": brands_label,
                "rationale": rationale,
            })
    else:
        # Cold-start: no purchase demand yet → surface the thinnest categories so
        # the first cartons fill the obvious gaps for the dominant member gender.
        all_cats = (
            await db.execute(
                select(Category.name).where(Category.is_active.is_(True))
            )
        ).scalars().all()
        scored = sorted(
            ((stock.get((n or "").lower(), 0), (n or "").lower()) for n in all_cats if n)
        )
        for cell, cat in scored[:max_lines]:
            lines.append({
                "category": cat,
                "gender": dominant_gender,
                "quality_hint": quality_hint,
                "action": "demander",
                "demand_share": None,
                "stock_count": cell,
                "brands": brands_label,
                "rationale": (
                    f"Pré-lancement : seulement {cell} pièce(s) en {cat} — "
                    f"carton à demander (signal déclaratif, audience {dominant_gender})."
                ),
            })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": BRIEF_VERSION,
        "period_days": period_days,
        "cold_start": cold_start,
        "dominant_gender": dominant_gender,
        "n_members_profiled": sum(gender_skew.values()),
        "signals": {
            "cohort_size": tastes.cohort_size,
            "top_brands": top_brands[:5],
            "gender_skew": gender_skew,
        },
        "lines": lines,
    }
