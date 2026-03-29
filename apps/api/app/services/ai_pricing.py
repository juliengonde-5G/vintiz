"""AI Pricing suggestion service.

Suggests optimal sale price based on:
- Purchase price and target margin
- Category price grid
- Recent sales data in same category
- Trend score
- Time on shelf (progressive markdowns)
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, PriceGrid, Product, ProductStatus

logger = logging.getLogger("vintiz.ai.pricing")


async def suggest_price(
    db: AsyncSession,
    category_id: str,
    purchase_price: float,
    brand: str | None = None,
    condition: str | None = None,
) -> dict:
    """Suggest a sale price for a new product.

    Args:
        db: Database session.
        category_id: Category UUID.
        purchase_price: What was paid for the item.
        brand: Brand name if known.
        condition: Condition (excellent, tres bon, bon, correct).

    Returns:
        Dict with suggested_price, price_range, reasoning.
    """
    # 1. Check price grid for category
    grid_result = await db.execute(
        select(PriceGrid).where(PriceGrid.category_id == category_id)
    )
    grids = grid_result.scalars().all()

    grid_suggestion = None
    if grids:
        for g in grids:
            if float(g.min_purchase) <= purchase_price <= float(g.max_purchase):
                grid_suggestion = float(g.sale_price)
                break

    # 2. Get recent sales in this category (last 8 weeks)
    eight_weeks_ago = datetime.now() - timedelta(weeks=8)
    sales_result = await db.execute(
        select(
            func.avg(TransactionItem.unit_price).label("avg_price"),
            func.min(TransactionItem.unit_price).label("min_price"),
            func.max(TransactionItem.unit_price).label("max_price"),
            func.count(TransactionItem.id).label("count"),
        )
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .join(Product, TransactionItem.product_id == Product.id)
        .where(
            Product.category_id == category_id,
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= eight_weeks_ago,
        )
    )
    sales_row = sales_result.one()
    avg_sold_price = float(sales_row[0]) if sales_row[0] else None
    min_sold_price = float(sales_row[1]) if sales_row[1] else None
    max_sold_price = float(sales_row[2]) if sales_row[2] else None
    sales_count = sales_row[3]

    # 3. Compute suggestion
    suggestions = []
    reasoning = []

    # Margin-based (minimum 2.5x markup for seconde main)
    margin_price = round(purchase_price * 2.5, 2)
    suggestions.append(margin_price)
    reasoning.append(f"Prix marge x2.5 : {margin_price:.2f} EUR")

    if grid_suggestion:
        suggestions.append(grid_suggestion)
        reasoning.append(f"Grille tarifaire : {grid_suggestion:.2f} EUR")

    if avg_sold_price and sales_count >= 3:
        suggestions.append(avg_sold_price)
        reasoning.append(
            f"Prix moyen vendu (categorie, {sales_count} ventes) : {avg_sold_price:.2f} EUR"
        )

    # Condition adjustment
    condition_factor = 1.0
    if condition == "excellent":
        condition_factor = 1.15
        reasoning.append("Bonus etat excellent : +15%")
    elif condition == "tres bon":
        condition_factor = 1.05
        reasoning.append("Bonus tres bon etat : +5%")
    elif condition == "correct":
        condition_factor = 0.85
        reasoning.append("Decote etat correct : -15%")

    # Brand premium
    premium_brands = {
        "chanel", "dior", "hermes", "louis vuitton", "gucci", "prada",
        "ysl", "saint laurent", "celine", "balenciaga", "givenchy",
        "burberry", "valentino", "fendi", "loewe", "bottega veneta",
    }
    mid_brands = {
        "sandro", "maje", "claudie pierlot", "iro", "ba&sh", "the kooples",
        "isabel marant", "zadig & voltaire", "comptoir des cotonniers",
        "gerard darel", "american vintage", "sessun", "vanessa bruno",
        "cos", "arket", "& other stories", "massimo dutti",
    }

    brand_factor = 1.0
    if brand:
        brand_lower = brand.lower()
        if brand_lower in premium_brands:
            brand_factor = 1.3
            reasoning.append(f"Marque premium ({brand}) : +30%")
        elif brand_lower in mid_brands:
            brand_factor = 1.1
            reasoning.append(f"Marque milieu de gamme ({brand}) : +10%")

    # Final suggestion: weighted average
    if suggestions:
        base_price = sum(suggestions) / len(suggestions)
    else:
        base_price = purchase_price * 3  # fallback

    suggested = round(base_price * condition_factor * brand_factor, 2)

    # Round to nearest 0.50
    suggested = round(suggested * 2) / 2

    # Ensure minimum margin
    if suggested < purchase_price * 1.5:
        suggested = round(purchase_price * 1.5 * 2) / 2
        reasoning.append("Ajuste au minimum x1.5 du prix d'achat")

    price_min = round(suggested * 0.8 * 2) / 2
    price_max = round(suggested * 1.2 * 2) / 2

    return {
        "suggested_price": suggested,
        "price_range": {"min": price_min, "max": price_max},
        "reasoning": reasoning,
        "market_data": {
            "grid_price": grid_suggestion,
            "avg_sold_price": round(avg_sold_price, 2) if avg_sold_price else None,
            "min_sold_price": round(min_sold_price, 2) if min_sold_price else None,
            "max_sold_price": round(max_sold_price, 2) if max_sold_price else None,
            "recent_sales_count": sales_count,
        },
    }


async def suggest_markdowns(db: AsyncSession) -> list[dict]:
    """Suggest price reductions for stale products.

    Products > 3 weeks: -10%
    Products > 5 weeks: -20%
    Products > 7 weeks: -30%
    Products > 10 weeks: -40%
    """
    now = datetime.now()
    result = await db.execute(
        select(Product).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
        ).order_by(Product.created_at.asc())
    )
    products = result.scalars().all()

    suggestions = []
    for p in products:
        days = (now - p.created_at.replace(tzinfo=None)).days
        weeks = days / 7

        if weeks < 3:
            continue

        if weeks >= 10:
            discount = 0.40
            urgency = "critique"
        elif weeks >= 7:
            discount = 0.30
            urgency = "haute"
        elif weeks >= 5:
            discount = 0.20
            urgency = "moyenne"
        else:
            discount = 0.10
            urgency = "basse"

        current_price = float(p.sale_price)
        new_price = round(current_price * (1 - discount) * 2) / 2  # round to 0.50

        # Don't go below purchase price
        if new_price < float(p.purchase_price):
            new_price = float(p.purchase_price)

        if new_price < current_price:
            suggestions.append({
                "product_id": str(p.id),
                "product_name": p.name,
                "barcode": p.barcode,
                "current_price": current_price,
                "suggested_price": new_price,
                "discount_percent": round(discount * 100),
                "days_on_shelf": days,
                "weeks_on_shelf": round(weeks, 1),
                "urgency": urgency,
                "category": p.category.name if p.category else None,
            })

    return suggestions
