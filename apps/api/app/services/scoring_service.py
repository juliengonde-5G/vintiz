from datetime import datetime, timezone
from typing import Optional


# Legacy hardcoded brand sets — kept as a fallback for callers who still
# pass only the brand string. The DB-backed BrandTier table (P2-012)
# supersedes these whenever a caller resolves ``brand_score`` upstream.
_LEGACY_LUXURY_BRANDS = {
    "hermes", "chanel", "dior", "vuitton", "gucci", "prada",
    "celine", "saint laurent", "balenciaga",
}
_LEGACY_PREMIUM_BRANDS = {
    "sandro", "maje", "ba&sh", "gerard darel", "the kooples",
    "claudie pierlot", "des petits hauts",
}
_LEGACY_MID_BRANDS = {"zara", "h&m", "mango", "apc", "jacquemus", "sessun"}


def _legacy_brand_score(brand: str | None) -> float:
    """The original hardcoded brand-tier resolver (V1 §2.1.6)."""
    b_lower = (brand or "").lower()
    if any(lb in b_lower for lb in _LEGACY_LUXURY_BRANDS):
        return 20.0
    if any(pb in b_lower for pb in _LEGACY_PREMIUM_BRANDS):
        return 15.0
    if any(mb in b_lower for mb in _LEGACY_MID_BRANDS):
        return 10.0
    if brand:
        return 8.0
    return 5.0


def _photo_subscore(
    photo_url: str | None,
    photo_count: int | None,
    photo_avg_confidence: float | None,
) -> float:
    """Photo sub-score (0-20). P2-011 enrichment.

    Decision tree:
      - ``photo_count`` supplied → score on (count + Vision confidence).
        + 5 points per photo (capped at 15) for the count.
        + up to 5 points scaled by avg Vision confidence (0..1 → 0..5).
      - Else legacy binary: 20 if any photo_url, 0 otherwise.

    The new path always tops at 20 like the legacy one, so the weighted
    formula bounds stay [0, 100].
    """
    if photo_count is None:
        return 20.0 if photo_url else 0.0
    n = max(0, int(photo_count))
    if n == 0:
        # No photos at all → no score, regardless of any stale confidence
        # number that may have leaked in from a previous Vision pass.
        return 0.0
    base = min(15.0, n * 5.0)
    confidence = max(0.0, min(1.0, float(photo_avg_confidence or 0.0)))
    confidence_bonus = confidence * 5.0
    return min(20.0, base + confidence_bonus)


def compute_score(
    shelf_date: Optional[datetime],
    sale_price: float,
    category_avg_price: float,
    condition: str,
    brand: str | None,
    photo_url: str | None,
    category_trend: float = 50.0,
    *,
    brand_score: float | None = None,
    photo_count: int | None = None,
    photo_avg_confidence: float | None = None,
) -> dict:
    """Compute product score (0-100) with sub-scores.

    Optional keyword arguments (P2-011 + P2-012):

    - ``brand_score``: precomputed brand sub-score (0-20), typically from
      ``brand_tiers.get_brand_score`` which reads the DB-backed
      ``brand_tiers`` table. When supplied, takes precedence over the
      legacy hardcoded brand sets.
    - ``photo_count`` + ``photo_avg_confidence``: produce a richer photo
      sub-score that rewards having multiple analyzed shots. When
      omitted, falls back to the legacy binary 0/20 on ``photo_url``.

    Existing call sites that don't pass the new arguments behave
    identically to before — the regression suite confirms this.
    """

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

    # Brand tier (15%) — DB-driven when the caller supplies a score.
    if brand_score is not None:
        score_brand = max(0.0, min(20.0, float(brand_score)))
    else:
        score_brand = _legacy_brand_score(brand)

    # Category trend (10%)
    score_category = category_trend / 5  # 0-100 → 0-20

    # Photos (5%)
    score_photos = _photo_subscore(photo_url, photo_count, photo_avg_confidence)

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
