"""AI Trend scoring service.

Delegates to the canonical 5-criteria scoring engine (scoring_service.py) so
every surface (inventory list, product detail, IA trend tab) shows the same
score for the same product.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Category, Product, ProductStatus

logger = logging.getLogger("vintiz.ai.trend")


async def compute_trend_scores(db: AsyncSession) -> list[dict]:
    """Compute trend scores for all active products using the canonical 5-criteria engine.

    Uses the same formula as GET /inventory/products/{id}/score so the IA trend
    tab, the inventory table, and the product detail all agree.
    """
    from app.services.category_trends import get_category_trends
    from app.services.category_velocity import get_velocity_cache
    from app.services.scoring_config import get_scoring_config
    from app.services.scoring_service import compute_score

    # Load all active products
    result = await db.execute(
        select(Product).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display])
        )
    )
    products = result.scalars().all()

    if not products:
        return []

    # Load category names in one query
    cat_result = await db.execute(select(Category.id, Category.name))
    category_names: dict[str, str] = {str(r[0]): r[1] for r in cat_result.all()}

    # Load shared context (cached per session)
    config = await get_scoring_config(db)
    category_trends = await get_category_trends(db)
    velocity_cache = await get_velocity_cache(db)

    scored = []
    for product in products:
        cat_id = str(product.category_id) if product.category_id else None
        cat_name = category_names.get(cat_id) if cat_id else None
        trend = category_trends.get(cat_id, 50.0) if cat_id else 50.0
        velocity = velocity_cache.get(cat_id) if cat_id else None

        result_score = compute_score(
            shelf_date=product.shelf_date,
            sale_price=float(product.sale_price),
            market_price_estimate=None,
            category_name=cat_name,
            category_trend=trend,
            category_avg_velocity=velocity,
            condition=getattr(product, "condition", None),
            config=config,
        )

        scored.append({
            "product_id": str(product.id),
            "product_name": product.name,
            "barcode": product.barcode,
            "score": round(result_score["total_score"], 1),
            "max_score": 100,
            "factors": {
                "score_attractivity": result_score["score_attractivity"],
                "score_season": result_score["score_season"],
                "score_age": result_score["score_age"],
                "score_trend": result_score["score_trend"],
                "score_price": result_score["score_price"],
            },
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


async def update_product_scores(db: AsyncSession) -> int:
    """Compute and persist scores using the canonical scoring engine. Returns count updated."""
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
    """Return products that have been on shelf for more than N weeks."""
    from datetime import date, timedelta

    cutoff = date.today() - timedelta(weeks=weeks)
    result = await db.execute(
        select(Product).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
            Product.shelf_date.is_not(None),
            Product.shelf_date <= cutoff,
        )
    )
    products = result.scalars().all()
    return [
        {
            "product_id": str(p.id),
            "product_name": p.name,
            "barcode": p.barcode,
            "shelf_date": p.shelf_date.isoformat() if p.shelf_date else None,
        }
        for p in products
    ]
