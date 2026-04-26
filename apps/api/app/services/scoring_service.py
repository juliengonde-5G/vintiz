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


_DEFAULT_WEIGHTS_V1 = {
    "age": 0.30, "price": 0.20, "condition": 0.20, "brand": 0.15,
    "category": 0.10, "photos": 0.05,
    "season_transition": 0.0, "fashion_watch": 0.0,
}


def _resolve_weights(config: dict | None) -> dict[str, float]:
    """Pick weights from config or fall back to v1 defaults (regression-safe)."""
    if not config or "weights" not in config:
        return _DEFAULT_WEIGHTS_V1
    w = config["weights"]
    return {
        "age": float(w.get("age", 0.30)),
        "price": float(w.get("price", 0.20)),
        "condition": float(w.get("condition", 0.20)),
        "brand": float(w.get("brand", 0.15)),
        "category": float(w.get("category", 0.10)),
        "photos": float(w.get("photos", 0.05)),
        "season_transition": float(w.get("season_transition", 0.0)),
        "fashion_watch": float(w.get("fashion_watch", 0.0)),
    }


def _age_decay_score(days_on_shelf: int, decay: dict | None) -> float:
    """Age sub-score [0, 20] with configurable decay curve.

    - linear (default v1) : ``20 - days // 3``, clamped at 0
    - exponential       : ``20 * 0.5^(days / half_life)`` with half_life =
                           ``min_score_days``
    - step              : 20 until ``max_score_days``, then linear toward
                           ``min_score_days``, then 0 after ``saturation_days``
    """
    if not decay:
        return float(max(0, 20 - (days_on_shelf // 3)))
    curve = decay.get("curve", "linear")
    max_days = int(decay.get("max_score_days", 0))
    min_days = int(decay.get("min_score_days", 60))
    sat_days = int(decay.get("saturation_days", 90))

    if curve == "exponential":
        half_life = max(1, min_days)
        return max(0.0, min(20.0, 20.0 * (0.5 ** (days_on_shelf / half_life))))

    if curve == "step":
        if days_on_shelf <= max_days:
            return 20.0
        if days_on_shelf >= sat_days:
            return 0.0
        # Between max_days and sat_days, linear ramp 20 → 0
        span = max(1, sat_days - max_days)
        return max(0.0, 20.0 - 20.0 * (days_on_shelf - max_days) / span)

    # linear (default) : honors min_score_days as the day where the score reaches 0
    if days_on_shelf <= max_days:
        return 20.0
    if days_on_shelf >= min_days:
        return 0.0
    span = max(1, min_days - max_days)
    return max(0.0, 20.0 - 20.0 * (days_on_shelf - max_days) / span)


def _season_transition_score(
    category_name: str | None,
    season_boost: dict | None,
    explicit_value: float | None,
) -> float:
    """Sub-score [0, 20] for seasonal transition.

    If the caller passes ``explicit_value`` (precomputed elsewhere), use it.
    Otherwise, derive a coarse score from the category calendar :
    - in-season month  : 20
    - 1 month before/after season : 12
    - out of season     : 5
    Returns 10 (neutral) if no calendar configured.
    """
    if explicit_value is not None:
        return max(0.0, min(20.0, float(explicit_value)))
    if not season_boost or not season_boost.get("enabled"):
        return 10.0
    calendar = season_boost.get("category_calendar", {})
    if not category_name or category_name not in calendar:
        return 10.0
    months_in_season = set(calendar[category_name])
    now = datetime.now(timezone.utc)
    cur = now.month
    if cur in months_in_season:
        return 20.0
    nxt = cur % 12 + 1
    prv = (cur - 2) % 12 + 1
    if nxt in months_in_season or prv in months_in_season:
        return 12.0
    return 5.0


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
    config: dict | None = None,
    category_name: str | None = None,
    season_transition_score: float | None = None,
    fashion_watch_score: float | None = None,
) -> dict:
    """Compute product score (0-100) with sub-scores.

    Optional keyword arguments :

    - ``brand_score`` (P2-012) : precomputed brand sub-score (0-20).
    - ``photo_count`` + ``photo_avg_confidence`` (P2-011) : richer photo
      sub-score. When omitted, falls back to legacy binary 0/20.
    - ``config`` (L4) : DB-backed scoring config dict (see
      ``services/scoring_config.py``). When supplied, drives 8-component
      weighted total + age decay curve. When ``None``, falls back to v1
      hardcoded weights — regression-safe.
    - ``category_name`` (L4) : enables season_boost calendar lookup.
    - ``season_transition_score`` (L4) : explicit override for the new
      "transition saison" sub-score (0-20).
    - ``fashion_watch_score`` (L4) : explicit override for the new
      "fashion watch" sub-score (0-20).

    Existing call sites that don't pass the new arguments behave identically
    to v1 — confirmed by ``test_scoring_formula.py``.
    """

    weights = _resolve_weights(config)
    age_decay = (config or {}).get("age_decay") if config else None
    season_boost = (config or {}).get("season_boost") if config else None

    # Age score (configurable decay curve)
    if shelf_date:
        days_on_shelf = (datetime.now(timezone.utc) - shelf_date.replace(tzinfo=timezone.utc)).days
        if age_decay:
            score_age = _age_decay_score(days_on_shelf, age_decay)
        else:
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

    # Season transition (v2, default 0% if no config)
    score_season_transition = _season_transition_score(
        category_name, season_boost, season_transition_score
    )

    # Fashion watch (v2, default 10 = neutral if no signal)
    score_fashion_watch = (
        max(0.0, min(20.0, float(fashion_watch_score)))
        if fashion_watch_score is not None
        else 10.0
    )

    # Weighted total — uses configurable weights when present, else v1 defaults.
    total = (
        score_age * weights["age"]
        + score_prix * weights["price"]
        + score_condition * weights["condition"]
        + score_brand * weights["brand"]
        + score_category * weights["category"]
        + score_photos * weights["photos"]
        + score_season_transition * weights["season_transition"]
        + score_fashion_watch * weights["fashion_watch"]
    ) * 5  # scale to 100

    # Consignment threshold (v2) : if past max_days, force RETIRER regardless of score.
    consignment = (config or {}).get("consignment_threshold") if config else None
    consignment_forced = False
    days_on_shelf_val: int | None = None
    if shelf_date:
        days_on_shelf_val = (
            datetime.now(timezone.utc) - shelf_date.replace(tzinfo=timezone.utc)
        ).days
        if (
            consignment
            and consignment.get("enabled")
            and days_on_shelf_val >= int(consignment.get("max_days", 120))
        ):
            consignment_forced = True

    # Recommended action
    if consignment_forced:
        action_after = (consignment or {}).get("action_after", "RETURNED_TO_SORTING")
        action = f"RETIRER — seuil consignation atteint ({action_after})"
        action_color = "red"
    elif total < 30:
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

    return {
        "total_score": round(total, 1),
        "score_age": round(score_age, 1),
        "score_prix": round(score_prix, 1),
        "score_condition": round(score_condition, 1),
        "score_brand": round(score_brand, 1),
        "score_category": round(score_category, 1),
        "score_photos": round(score_photos, 1),
        "score_season_transition": round(score_season_transition, 1),
        "score_fashion_watch": round(score_fashion_watch, 1),
        "action": action,
        "action_color": action_color,
        "days_on_shelf": days_on_shelf_val,
        "consignment_forced": consignment_forced,
    }
