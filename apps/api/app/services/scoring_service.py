from datetime import datetime, timezone
from typing import Optional


def compute_score(
    shelf_date: Optional[datetime],
    sale_price: float,
    category_avg_price: float,
    condition: str,
    brand: str | None,
    photo_url: str | None,
    category_trend: float = 50.0,
) -> dict:
    """Compute product score (0-100) with sub-scores."""

    # Age score (30%)
    if shelf_date:
        days_on_shelf = (datetime.now(timezone.utc) - shelf_date.replace(tzinfo=timezone.utc)).days
        score_age = max(0, 20 - (days_on_shelf // 3))
    else:
        score_age = 15  # unknown, neutral

    # Price competitiveness (20%)
    if category_avg_price > 0:
        ratio = sale_price / category_avg_price
        if ratio <= 0.5:
            score_prix = 20
        elif ratio <= 0.8:
            score_prix = 16
        elif ratio <= 1.0:
            score_prix = 12
        elif ratio <= 1.5:
            score_prix = 8
        elif ratio <= 2.0:
            score_prix = 4
        else:
            score_prix = 0
    else:
        score_prix = 10

    # Condition (20%)
    condition_map = {
        "neuf_etiquette": 20, "neuf": 18, "tres_bon": 15, "bon": 10, "correct": 5
    }
    score_condition = condition_map.get(
        condition.lower().replace(" ", "_") if condition else "tres_bon", 12
    )

    # Brand tier (15%)
    luxury_brands = {
        "hermes", "chanel", "dior", "vuitton", "gucci", "prada",
        "celine", "saint laurent", "balenciaga"
    }
    premium_brands = {
        "sandro", "maje", "ba&sh", "gerard darel", "the kooples",
        "claudie pierlot", "des petits hauts"
    }
    mid_brands = {"zara", "h&m", "mango", "apc", "jacquemus", "sessun"}
    b_lower = (brand or "").lower()
    if any(lb in b_lower for lb in luxury_brands):
        score_brand = 20
    elif any(pb in b_lower for pb in premium_brands):
        score_brand = 15
    elif any(mb in b_lower for mb in mid_brands):
        score_brand = 10
    elif brand:
        score_brand = 8
    else:
        score_brand = 5

    # Category trend (10%)
    score_category = category_trend / 5  # 0-100 → 0-20

    # Photos (5%)
    score_photos = 20 if photo_url else 0

    # Weighted total
    total = (
        score_age * 0.30
        + score_prix * 0.20
        + score_condition * 0.20
        + score_brand * 0.15
        + score_category * 0.10
        + score_photos * 0.05
    ) * 5  # scale to 100

    # Recommended action
    if total < 30:
        action = "RETIRER — produit trop longtemps en rayon"
        action_color = "red"
    elif total < 50:
        action = "RÉDUIRE PRIX — -15% suggéré"
        action_color = "orange"
    elif total < 70:
        action = "METTRE EN AVANT — déplacer en vitrine"
        action_color = "yellow"
    else:
        action = "MAINTENIR — bon potentiel de vente"
        action_color = "green"

    days_on_shelf_val: int | None = None
    if shelf_date:
        days_on_shelf_val = (
            datetime.now(timezone.utc) - shelf_date.replace(tzinfo=timezone.utc)
        ).days

    return {
        "total_score": round(total, 1),
        "score_age": round(score_age, 1),
        "score_prix": round(score_prix, 1),
        "score_condition": round(score_condition, 1),
        "score_brand": round(score_brand, 1),
        "score_category": round(score_category, 1),
        "score_photos": round(score_photos, 1),
        "action": action,
        "action_color": action_color,
        "days_on_shelf": days_on_shelf_val,
    }
