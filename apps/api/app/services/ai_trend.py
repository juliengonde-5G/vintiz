"""AI Trend scoring service.

Computes a trend score for each product based on:
- Sales velocity in the category
- Season alignment
- Time on shelf (older = lower score)
- Price competitiveness
- Style popularity (from sales data)
"""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Product, ProductStatus

logger = logging.getLogger("vintiz.ai.trend")


async def compute_trend_scores(db: AsyncSession) -> list[dict]:
    """Compute trend scores for all active products (stock + display).

    Returns list of {product_id, score, factors} dicts.
    """
    today = date.today()
    now = datetime.now()

    # Get all active products
    result = await db.execute(
        select(Product).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display])
        )
    )
    products = result.scalars().all()

    if not products:
        return []

    # Get category sales in last 4 weeks
    four_weeks_ago = datetime.combine(today - timedelta(weeks=4), datetime.min.time())
    cat_sales = await db.execute(
        select(
            Product.category_id,
            func.count(TransactionItem.id).label("sales_count"),
            func.sum(TransactionItem.line_total).label("sales_revenue"),
        )
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .where(
            Transaction.created_at >= four_weeks_ago,
            Transaction.transaction_type == TransactionType.sale,
        )
        .group_by(Product.category_id)
    )
    category_velocity = {str(r[0]): {"count": r[1], "revenue": float(r[2])} for r in cat_sales.all()}

    # Get total sales for normalization
    total_sales_count = sum(v["count"] for v in category_velocity.values()) or 1

    # Current month for season mapping
    month = today.month
    if month in (3, 4, 5):
        current_season = "mi-saison"
    elif month in (6, 7, 8):
        current_season = "ete"
    elif month in (9, 10, 11):
        current_season = "mi-saison"
    else:
        current_season = "hiver"

    scored = []
    for product in products:
        factors = {}

        # 1. Category velocity (0-30 points)
        cat_id = str(product.category_id)
        cat_data = category_velocity.get(cat_id, {"count": 0, "revenue": 0})
        velocity_score = min(30, (cat_data["count"] / total_sales_count) * 100)
        factors["category_velocity"] = round(velocity_score, 1)

        # 2. Freshness - time on shelf (0-25 points, newer = higher)
        days_on_shelf = (now - product.created_at.replace(tzinfo=None)).days if product.created_at else 0
        if days_on_shelf <= 7:
            freshness = 25
        elif days_on_shelf <= 14:
            freshness = 20
        elif days_on_shelf <= 21:
            freshness = 15
        elif days_on_shelf <= 28:
            freshness = 10
        else:
            freshness = max(0, 5 - (days_on_shelf - 28) // 7)
        factors["freshness"] = freshness

        # 3. Season alignment (0-20 points)
        # We don't have season on product model yet, use week_number as proxy
        week = product.week_number or 0
        if week > 0:
            # Products from recent weeks score higher
            current_week = today.isocalendar()[1]
            week_diff = abs(current_week - week)
            season_score = max(0, 20 - week_diff * 2)
        else:
            season_score = 10  # neutral
        factors["season_alignment"] = season_score

        # 4. Price attractiveness (0-15 points)
        # Lower price relative to category avg = more attractive
        if cat_data["count"] > 0 and cat_data["revenue"] > 0:
            avg_price = cat_data["revenue"] / cat_data["count"]
            price_ratio = float(product.sale_price) / avg_price if avg_price > 0 else 1
            if price_ratio <= 0.7:
                price_score = 15
            elif price_ratio <= 0.9:
                price_score = 12
            elif price_ratio <= 1.1:
                price_score = 10
            elif price_ratio <= 1.3:
                price_score = 7
            else:
                price_score = 4
        else:
            price_score = 8  # neutral
        factors["price_attractiveness"] = price_score

        # 5. Display bonus (0-10 points)
        display_bonus = 10 if product.status == ProductStatus.display else 0
        factors["display_bonus"] = display_bonus

        total_score = sum(factors.values())
        scored.append({
            "product_id": str(product.id),
            "product_name": product.name,
            "barcode": product.barcode,
            "score": round(total_score, 1),
            "max_score": 100,
            "factors": factors,
        })

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


async def update_product_scores(db: AsyncSession) -> int:
    """Compute and persist trend scores to products. Returns count updated."""
    scores = await compute_trend_scores(db)
    for item in scores:
        result = await db.execute(
            select(Product).where(Product.id == item["product_id"])
        )
        product = result.scalar_one_or_none()
        if product:
            product.trend_score = item["score"]
    await db.flush()
    return len(scores)


async def get_stale_products(db: AsyncSession, weeks: int = 4) -> list[dict]:
    """Get products that have been in stock for more than N weeks without selling."""
    cutoff = datetime.now() - timedelta(weeks=weeks)
    result = await db.execute(
        select(Product).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
            Product.created_at < cutoff,
        ).order_by(Product.created_at.asc())
    )
    products = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "barcode": p.barcode,
            "sale_price": float(p.sale_price),
            "days_on_shelf": (datetime.now() - p.created_at.replace(tzinfo=None)).days,
            "trend_score": p.trend_score,
            "category": p.category.name if p.category else None,
        }
        for p in products
    ]
