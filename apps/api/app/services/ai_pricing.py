"""AI Pricing suggestion service.

Suggests optimal sale price based on:
- Purchase price and target margin
- Category price grid
- Recent sales data in same category
- Trend score
- Time on shelf (progressive markdowns)
"""

import logging
import re
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, PriceGrid, Product
from app.services import brand_tiers

logger = logging.getLogger("vintiz.ai.pricing")

# Brand tier → price multiplier (applied to category-level signals when no
# original-new-price anchor is available). Mirrors the brand_tiers ladder.
_TIER_FACTOR = {"luxury": 1.45, "premium": 1.30, "mid": 1.12, "basic": 1.0}

# Fallback brand classification when a brand isn't in the manager-editable
# brand_tiers table yet. Kept so a fresh install still prices premium labels
# sensibly; the DB table always wins when populated.
_FALLBACK_PREMIUM = {
    "chanel", "dior", "hermes", "louis vuitton", "gucci", "prada", "ysl",
    "saint laurent", "celine", "balenciaga", "givenchy", "burberry",
    "valentino", "fendi", "loewe", "bottega veneta", "moncler", "max mara",
}
_FALLBACK_MID = {
    "sandro", "maje", "claudie pierlot", "iro", "ba&sh", "the kooples",
    "isabel marant", "zadig & voltaire", "comptoir des cotonniers",
    "gerard darel", "american vintage", "sessun", "vanessa bruno", "sezane",
    "cos", "arket", "& other stories", "massimo dutti", " daad",
}

# Share of the original new-retail price a second-hand premium item fetches,
# by condition. Drives the brand-aware anchor when we can estimate the new price.
_RESALE_RATIO = {"neuf": 0.55, "tres_bon": 0.45, "bon": 0.38, "correct": 0.28}


def _normalize_condition(condition: str | None) -> str | None:
    """Map both AI ``etat`` strings and stored codes to a canonical code."""
    if not condition:
        return None
    e = condition.lower().replace("é", "e").replace("è", "e").strip()
    if "neuf" in e or "excellent" in e:
        return "neuf"
    if "tres bon" in e or "tres_bon" in e:
        return "tres_bon"
    if "correct" in e:
        return "correct"
    if "bon" in e:
        return "bon"
    return None


def _fallback_brand_factor(brand: str | None) -> tuple[float, str | None]:
    if not brand:
        return 1.0, None
    b = brand.lower()
    if any(k in b for k in _FALLBACK_PREMIUM):
        return _TIER_FACTOR["premium"], "premium"
    if any(k in b for k in _FALLBACK_MID):
        return _TIER_FACTOR["mid"], "mid"
    return 1.0, None


async def _estimate_original_retail(
    category_name: str | None, brand: str | None, cond_code: str | None
) -> float | None:
    """Best-effort estimate of the original NEW retail price (€) for the
    brand + category, via Claude Haiku. Returns ``None`` without a key or on
    any failure so pricing degrades gracefully.
    """
    if not settings.ANTHROPIC_API_KEY or not brand or not category_name:
        return None
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = (
            f"Quel est le prix de vente NEUF (prix boutique d'origine) en euros "
            f"d'un article de type « {category_name} » de la marque « {brand} » ? "
            f"Donne une estimation réaliste pour le marché français. "
            f"Réponds UNIQUEMENT par un nombre entier en euros, sans symbole ni texte."
        )
        msg = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=16,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (msg.content[0].text if msg.content else "") or ""
        match = re.search(r"\d[\d\s]*", raw)
        if match:
            val = float(match.group().replace(" ", ""))
            if 5 <= val <= 10000:
                return val
    except Exception as exc:  # noqa: BLE001 — never break pricing on AI failure
        logger.info("new-retail estimate unavailable: %s", exc)
    return None


def _build_justification(
    *, suggested: float, brand: str | None, brand_label: str | None,
    cond_code: str | None, new_price: float | None, resale_from_new: float | None,
    grid_suggestion: float | None, avg_sold_price: float | None, sales_count: int,
) -> str:
    """Human-readable rationale shown to the operator under the suggested price."""
    parts: list[str] = []
    if new_price and resale_from_new:
        parts.append(
            f"Prix neuf estimé pour {brand or 'cette pièce'} ≈ {new_price:.0f} € ; "
            f"en seconde main ({cond_code or 'bon'} état) on vise ~{resale_from_new:.0f} €."
        )
    elif brand_label:
        parts.append(
            f"Marque {brand} positionnée « {brand_label} » : prix rehaussé "
            f"par rapport à la médiane catégorie."
        )
    else:
        parts.append("Prix basé sur la grille catégorie et les ventes récentes.")
    if grid_suggestion:
        parts.append(f"Grille catégorie {grid_suggestion:.0f} €.")
    if avg_sold_price and sales_count >= 3:
        parts.append(f"Moyenne {sales_count} ventes similaires : {avg_sold_price:.0f} €.")
    parts.append(f"Proposition : {suggested:.2f} € (ajustable).")
    return " ".join(parts)


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

    # Category name — used to ground the original-new-price estimate.
    cat_name_row = await db.execute(
        select(Category.name).where(Category.id == category_id)
    )
    category_name = cat_name_row.scalar_one_or_none()

    # 3. Compute suggestion
    reasoning: list[str] = []
    category_signals: list[float] = []  # category-level (brand-agnostic) prices

    if has_purchase:
        margin_price = round(purchase_price * 2.5, 2)  # type: ignore[operator]
        category_signals.append(margin_price)
        reasoning.append(f"Prix marge x2.5 du prix d'achat : {margin_price:.2f} €")

    if grid_suggestion:
        category_signals.append(grid_suggestion)
        reasoning.append(
            f"Grille tarifaire catégorie : {grid_suggestion:.2f} €"
            if has_purchase
            else f"Grille tarifaire (médiane catégorie) : {grid_suggestion:.2f} €"
        )

    if avg_sold_price and sales_count >= 3:
        category_signals.append(avg_sold_price)
        reasoning.append(
            f"Prix moyen vendu (catégorie, {sales_count} ventes) : {avg_sold_price:.2f} €"
        )

    # Condition (robust to AI 'etat' strings and stored codes alike).
    cond_code = _normalize_condition(condition)
    condition_factor = {
        "neuf": 1.15, "tres_bon": 1.05, "bon": 1.0, "correct": 0.85,
    }.get(cond_code or "bon", 1.0)

    # Brand tier — manager-editable table first, hardcoded fallback otherwise.
    brand_tier = await brand_tiers.get_brand_tier(db, brand) if brand else None
    if brand_tier:
        brand_factor, brand_label = _TIER_FACTOR.get(brand_tier, 1.0), brand_tier
    else:
        brand_factor, brand_label = _fallback_brand_factor(brand)

    # Original new-retail price → brand-aware resale anchor.
    new_price = await _estimate_original_retail(category_name, brand, cond_code)
    resale_from_new: float | None = None
    if new_price:
        ratio = _RESALE_RATIO.get(cond_code or "bon", 0.38)
        resale_from_new = round(new_price * ratio, 2)
        reasoning.append(
            f"Prix neuf estimé ~{new_price:.0f} € → revente {int(ratio * 100)} % "
            f"(état {cond_code or 'bon'}) : {resale_from_new:.2f} €"
        )

    # ---- Blend the signals into a final price ----
    if resale_from_new:
        # The new-price anchor already reflects the brand AND the condition,
        # so we don't re-apply the brand/condition multipliers on top of it.
        if category_signals:
            base = sum(category_signals) / len(category_signals)
            suggested = 0.6 * resale_from_new + 0.4 * base
        else:
            suggested = resale_from_new
        if brand_label:
            reasoning.append(f"Marque {brand} positionnée « {brand_label} »")
    elif category_signals or has_purchase:
        if category_signals:
            base = sum(category_signals) / len(category_signals)
        else:
            base = purchase_price * 3  # type: ignore[operator]
            reasoning.append("Aucun signal marché : repli x3 du prix d'achat")
        if brand_label and brand_factor != 1.0:
            reasoning.append(f"Marque « {brand_label} » ({brand}) : ×{brand_factor:.2f}")
        if condition_factor != 1.0:
            pct = round((condition_factor - 1) * 100)
            reasoning.append(f"État {cond_code} : {'+' if pct >= 0 else ''}{pct} %")
        suggested = base * condition_factor * brand_factor
    else:
        # No signal at all — let the UI prompt a manual price.
        return {
            "suggested_price": 0.0,
            "price_range": {"min": 0.0, "max": 0.0},
            "reasoning": [
                "Pas assez de données pour suggérer un prix : ajoutez une "
                "grille tarifaire pour cette catégorie, renseignez la marque, "
                "ou attendez quelques ventes de comparaison."
            ],
            "justification": (
                "Aucune donnée exploitable (ni grille, ni ventes, ni estimation "
                "neuf). Saisissez le prix manuellement."
            ),
            "market_data": {
                "grid_price": grid_suggestion,
                "new_price_estimate": new_price,
                "avg_sold_price": None,
                "min_sold_price": None,
                "max_sold_price": None,
                "recent_sales_count": sales_count,
            },
        }

    # Round to nearest 0.50.
    suggested = round(round(suggested, 2) * 2) / 2

    # Ensure minimum margin (only when we know what we paid).
    if has_purchase and suggested < purchase_price * 1.5:  # type: ignore[operator]
        suggested = round(purchase_price * 1.5 * 2) / 2  # type: ignore[operator]
        reasoning.append("Ajusté au minimum x1.5 du prix d'achat")

    price_min = round(suggested * 0.8 * 2) / 2
    price_max = round(suggested * 1.2 * 2) / 2

    justification = _build_justification(
        suggested=suggested, brand=brand, brand_label=brand_label,
        cond_code=cond_code, new_price=new_price, resale_from_new=resale_from_new,
        grid_suggestion=grid_suggestion, avg_sold_price=avg_sold_price,
        sales_count=sales_count,
    )

    return {
        "suggested_price": suggested,
        "price_range": {"min": price_min, "max": price_max},
        "reasoning": reasoning,
        "justification": justification,
        "market_data": {
            "grid_price": grid_suggestion,
            "new_price_estimate": new_price,
            "avg_sold_price": round(avg_sold_price, 2) if avg_sold_price else None,
            "min_sold_price": round(min_sold_price, 2) if min_sold_price else None,
            "max_sold_price": round(max_sold_price, 2) if max_sold_price else None,
            "recent_sales_count": sales_count,
        },
    }


