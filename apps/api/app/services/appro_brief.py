"""Approvisionnement brief — demande → appro prescriptif (PS 360 V5, §7.3).

The boutique's real lever: stop being reactive ("I recommend what's in stock")
and become prescriptive ("demand drives what we bring in"). This service turns
the aggregated demand signals into **carton-level** recommendations by
**catégorie × genre × qualité** — the granularity the sorting centre can act on
(it can't deliver by size/colour).

Signals (audit §7.3), degrading gracefully at cold-start:
1. Dominant tastes of loyal-active members (purchases) — ``compute_audience_snapshot``.
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
from app.services.predictive_targeting import compute_audience_snapshot

BRIEF_VERSION = "appro-brief-v1-2026-05"

# Below this absolute count, a (category, gender) cell is considered thin enough
# to warrant a carton even without a strong purchase signal (cold-start).
LOW_STOCK_THRESHOLD = 3


async def _stock_by_category_gender(db: AsyncSession) -> dict[tuple[str, str], int]:
    rows = await db.execute(
        select(Category.name, Product.gender, func.count(Product.id))
        .join(Product, Product.category_id == Category.id)
        .where(Product.status.in_([ProductStatus.stock, ProductStatus.display]))
        .group_by(Category.name, Product.gender)
    )
    out: dict[tuple[str, str], int] = {}
    for name, gender, count in rows.all():
        if not name:
            continue
        g = gender.value if gender is not None else "mixte"
        out[(name.lower(), g)] = int(count)
    return out


async def _member_gender_skew(db: AsyncSession) -> dict[str, int]:
    rows = await db.execute(
        select(Client.gender_profile, func.count(Client.id))
        .where(Client.gender_profile.is_not(None))
        .group_by(Client.gender_profile)
    )
    return {g: int(c) for g, c in rows.all() if g}


def _cat_stock(stock: dict[tuple[str, str], int], cat: str) -> int:
    return sum(v for (cn, _g), v in stock.items() if cn == cat)


async def build_appro_brief(
    db: AsyncSession, *, period_days: int = 90, max_lines: int = 8
) -> dict:
    """Build the weekly approvisionnement brief. See module docstring."""
    audience = await compute_audience_snapshot(db, period_days=period_days)
    demand_cats = audience.get("top_categories") or []
    top_brands = [b.get("name") for b in (audience.get("top_brands") or []) if b.get("name")]
    n_tx = int(audience.get("n_transactions") or 0)
    cold_start = n_tx == 0

    stock = await _stock_by_category_gender(db)
    total_stock = sum(stock.values()) or 1
    gender_skew = await _member_gender_skew(db)
    dominant_gender = (
        max(gender_skew, key=gender_skew.get) if gender_skew else "mixte"
    )
    # Quality dimension: Vintiz is premium 2nd-hand; the demanded brands sharpen it.
    quality_hint = "premium"
    brands_label = ", ".join(top_brands[:3]) if top_brands else "marques premium"

    lines: list[dict] = []

    if demand_cats:
        # Demand-driven: compare each demanded category's share vs its supply.
        for c in demand_cats[:max_lines]:
            cat = (c.get("name") or "").lower()
            if not cat:
                continue
            demand_share = float(c.get("share") or 0)
            cat_stock = _cat_stock(stock, cat)
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
        # Cold-start: no purchase demand yet → surface the thinnest cells for the
        # dominant member gender so the first cartons fill the obvious gaps.
        all_cats = (
            await db.execute(select(Category.name).where(Category.is_active.is_(True)))
        ).scalars().all()
        scored = []
        for name in all_cats:
            if not name:
                continue
            cat = name.lower()
            cell = stock.get((cat, dominant_gender), 0) + stock.get((cat, "mixte"), 0)
            scored.append((cell, cat))
        scored.sort()  # thinnest first
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
                    f"Pré-lancement : seulement {cell} pièce(s) en {cat} "
                    f"{dominant_gender} — carton à demander (signal déclaratif)."
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
            "n_transactions": n_tx,
            "n_customers": int(audience.get("n_customers") or 0),
            "top_brands": top_brands[:5],
            "gender_skew": gender_skew,
        },
        "lines": lines,
    }
