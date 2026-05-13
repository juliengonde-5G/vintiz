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
from app.models.product import PriceGrid, Product, ProductStatus

logger = logging.getLogger("vintiz.ai.pricing")


async def suggest_price(
    db: AsyncSession,
    category_id: str,
    purchase_price: float | None = None,
    brand: str | None = None,
    condition: str | None = None,
) -> dict:
    """Suggest a sale price for a new product.

    Args:
        db: Database session.
        category_id: Category UUID.
        purchase_price: What was paid for the item (optional — Vintiz dépose
            en achat-revente sans prix d'achat documenté côté caisse, donc
            ce paramètre est désormais facultatif. Quand absent, la
            suggestion s'appuie uniquement sur la grille tarifaire, le prix
            moyen vendu, la marque et l'état).
        brand: Brand name if known.
        condition: Condition (excellent, tres bon, bon, correct).

    Returns:
        Dict with suggested_price, price_range, reasoning.
    """
    has_purchase = purchase_price is not None and purchase_price > 0

    # 1. Check price grid for category
    grid_result = await db.execute(
        select(PriceGrid).where(PriceGrid.category_id == category_id)
    )
    grids = grid_result.scalars().all()

    grid_suggestion = None
    if grids:
        if has_purchase:
            # Find the grid bucket that covers the purchase price.
            for g in grids:
                if float(g.min_purchase) <= purchase_price <= float(g.max_purchase):  # type: ignore[operator]
                    grid_suggestion = float(g.sale_price)
                    break
        # Fallback when no purchase_price : prendre la médiane des grilles
        # de la catégorie (signal "prix typique" pour la cat).
        if grid_suggestion is None:
            grid_prices = sorted(float(g.sale_price) for g in grids)
            mid = grid_prices[len(grid_prices) // 2]
            grid_suggestion = mid

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

    # Margin-based (minimum 2.5x markup for seconde main) — uniquement
    # quand on connaît un prix d'achat.
    if has_purchase:
        margin_price = round(purchase_price * 2.5, 2)  # type: ignore[operator]
        suggestions.append(margin_price)
        reasoning.append(f"Prix marge x2.5 : {margin_price:.2f} EUR")

    if grid_suggestion:
        suggestions.append(grid_suggestion)
        if has_purchase:
            reasoning.append(f"Grille tarifaire : {grid_suggestion:.2f} EUR")
        else:
            reasoning.append(
                f"Grille tarifaire (mediane categorie) : {grid_suggestion:.2f} EUR"
            )

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
    elif has_purchase:
        base_price = purchase_price * 3  # type: ignore[operator]  # fallback
        reasoning.append("Aucun signal marché : fallback x3 du prix d'achat")
    else:
        # Aucun signal disponible — la cliente n'aura pas de suggestion.
        # Renvoie un fallback à 0 que l'UI peut détecter pour proposer
        # une saisie manuelle.
        return {
            "suggested_price": 0.0,
            "price_range": {"min": 0.0, "max": 0.0},
            "reasoning": [
                "Pas assez de donnees pour suggerer un prix : ajoute une "
                "grille tarifaire pour cette categorie ou attends quelques "
                "ventes de comparaison."
            ],
            "market_data": {
                "grid_price": grid_suggestion,
                "avg_sold_price": None,
                "min_sold_price": None,
                "max_sold_price": None,
                "recent_sales_count": sales_count,
            },
        }

    suggested = round(base_price * condition_factor * brand_factor, 2)

    # Round to nearest 0.50
    suggested = round(suggested * 2) / 2

    # Ensure minimum margin (only when we know what we paid)
    if has_purchase and suggested < purchase_price * 1.5:  # type: ignore[operator]
        suggested = round(purchase_price * 1.5 * 2) / 2  # type: ignore[operator]
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


