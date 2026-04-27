"""Per-product insights for the POS AI badge (P4-010).

Each call returns a small list of badges, ranked by relevance, that the
cashier sees beside the cart line. Examples :

  🔥  "Vendue 3× cette semaine"     (sales velocity)
  ⏳  "En vitrine depuis 38 jours"  (stale stock — markdown soon)
  ⭐  "Marque premium"               (brand_tier)
  🎯  "Score Vintiz 87/100"         (top scoring quartile)
  🛍  "Réservée — 36h restantes"    (active hold)

The signal source is the existing data store — no new ML, no new API.
This is deliberately a heuristic feature, not a model: it surfaces
information Camille is already typing into Slack today.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Product, ProductStatus


@dataclass
class Insight:
    icon: str           # emoji shown on the badge
    label: str          # short FR text
    severity: str       # "info" | "warn" | "good"


@dataclass
class ProductInsights:
    product_id: uuid.UUID
    insights: list[Insight]


_HOT_SALES_THRESHOLD = 3      # ≥ N sales in 7 days = "hot"
_STALE_DAYS = 30              # > N days on the floor = "stale"
_TOP_SCORE = 80               # ≥ N (0..100) = "top"


async def compute_for_product(
    db: AsyncSession, product_id: uuid.UUID, *, now: datetime | None = None
) -> ProductInsights:
    now = now or datetime.now(timezone.utc)

    product = (await db.execute(
        select(Product).where(Product.id == product_id)
    )).scalar_one_or_none()
    if product is None:
        return ProductInsights(product_id=product_id, insights=[])

    insights: list[Insight] = []

    # 1. Sales velocity over the last 7 days.
    week_ago = now - timedelta(days=7)
    sold_this_week = (await db.execute(
        select(func.coalesce(func.sum(TransactionItem.quantity), 0))
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            TransactionItem.product_id == product_id,
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= week_ago,
        )
    )).scalar_one() or 0
    if sold_this_week >= _HOT_SALES_THRESHOLD:
        insights.append(Insight(
            icon="🔥",
            label=f"Vendue {sold_this_week}× cette semaine",
            severity="good",
        ))

    # 2. Stale on the floor — only surface if no recent sale (otherwise
    # the velocity badge already conveys a positive signal).
    if product.status in (ProductStatus.display, ProductStatus.displayed,
                          ProductStatus.discounted, ProductStatus.deep_discounted):
        anchor = product.displayed_at or product.created_at
        if anchor is not None:
            anchor_aware = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)
            days = max(0, (now - anchor_aware).days)
            if days > _STALE_DAYS and sold_this_week == 0:
                insights.append(Insight(
                    icon="⏳",
                    label=f"En vitrine depuis {days} jours",
                    severity="warn",
                ))

    # 3. Brand tier (luxury / premium).
    if product.brand:
        from app.services.brand_tiers import get_brand_score

        score = await get_brand_score(db, product.brand)
        label = _brand_score_label(score)
        if label:
            insights.append(Insight(icon="⭐", label=label, severity="info"))

    # 4. Top Vintiz score.
    if product.trend_score is not None and float(product.trend_score) >= _TOP_SCORE:
        insights.append(Insight(
            icon="🎯",
            label=f"Score Vintiz {int(product.trend_score)}/100",
            severity="good",
        ))

    return ProductInsights(product_id=product_id, insights=insights)


def _brand_score_label(score: float) -> str | None:
    # Thresholds match BRAND_TIER_SCORE in app.models.brand_tier:
    # luxury=20, premium=15, mid=10, basic=8.
    if score >= 20:
        return "Marque luxe"
    if score >= 15:
        return "Marque premium"
    if score >= 10:
        return "Marque mid-range"
    return None


def to_dict(p: ProductInsights) -> dict:
    return {
        "product_id": str(p.product_id),
        "insights": [asdict(i) for i in p.insights],
    }
