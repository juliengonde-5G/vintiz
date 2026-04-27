"""Vintiz scoring engine — 5 criteria (v3, lundi MAJ).

Score (0-100) = weighted average × 5 of 5 sub-scores (each 0-20):

  1. Attractivity       (default 25 %) — vitesse de rotation 90j (catégorie + marque + condition)
  2. Saison              (default 20 %) — calendar par catégorie (en saison = 20, ±1 mois = 12, hors = 5)
  3. Ancienneté          (default 25 %) — décroissance hebdo sur 6 semaines (table éditable)
  4. Tendance            (default 15 %) — category_trends 4 dernières semaines + signal fashion-watch
  5. Positionnement prix (default 15 %) — ratio sale_price / market_price_estimate (Claude)

Action recommandée :
  total < 30  → RETIRER
  30..49      → RÉDUIRE PRIX
  50..69      → METTRE EN AVANT
  total ≥ 70  → MAINTENIR
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Default config — kept small so a missing/partial config still produces a
# deterministic score.
# ---------------------------------------------------------------------------

_DEFAULT_WEIGHTS = {
    "attractivity": 0.25,
    "season": 0.20,
    "age": 0.25,
    "trend": 0.15,
    "price": 0.15,
}

# Points by week on shelf. Index 0 = week 1, last index = week 6+ (sortie auto).
_DEFAULT_AGE_WEEKS_TABLE = [20.0, 17.0, 13.0, 10.0, 6.0, 2.0]

_DEFAULT_PRICE_THRESHOLDS = [0.7, 0.9, 1.1, 1.3]
_DEFAULT_PRICE_POINTS = [20.0, 16.0, 12.0, 8.0, 4.0]


# ---------------------------------------------------------------------------
# Sub-scores
# ---------------------------------------------------------------------------


def _resolve_weights(config: dict | None) -> dict[str, float]:
    if not config or "weights" not in config:
        return _DEFAULT_WEIGHTS
    w = config["weights"]
    return {k: float(w.get(k, _DEFAULT_WEIGHTS[k])) for k in _DEFAULT_WEIGHTS}


def _weeks_on_shelf(shelf_date: Optional[datetime]) -> int:
    if shelf_date is None:
        return 0
    if shelf_date.tzinfo is None:
        shelf_date = shelf_date.replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - shelf_date).days
    return max(0, days // 7)


def _age_score(weeks_on_shelf: int, weeks_table: list[float]) -> float:
    """Pick a point value from the editable weeks table.

    weeks_table[0] = week 1 (most recent), weeks_table[-1] = week 6+.
    """
    if not weeks_table:
        return 0.0
    last = weeks_table[-1]
    if weeks_on_shelf <= 0:
        # Just landed — bench-mark on week 1
        return float(weeks_table[0])
    idx = min(weeks_on_shelf - 1, len(weeks_table) - 1)
    if weeks_on_shelf >= len(weeks_table):
        return float(last)
    return float(weeks_table[idx])


def _season_score(
    category_name: str | None,
    season_calendar: dict | None,
    explicit_value: float | None,
) -> float:
    """Sub-score [0, 20] from the seasonal calendar.

    If ``explicit_value`` is provided, it wins (caller already computed it).
    Else: in-season month = 20, ±1 month = 12, out-of-season = 5,
    no calendar entry = 10 (neutral).
    """
    if explicit_value is not None:
        return max(0.0, min(20.0, float(explicit_value)))
    if not season_calendar or not category_name or category_name not in season_calendar:
        return 10.0
    months_in_season = set(season_calendar[category_name])
    if not months_in_season:
        return 10.0
    cur = datetime.now(timezone.utc).month
    if cur in months_in_season:
        return 20.0
    nxt = cur % 12 + 1
    prv = (cur - 2) % 12 + 1
    if nxt in months_in_season or prv in months_in_season:
        return 12.0
    return 5.0


def _trend_score(category_trend: float, fashion_watch_score: float | None) -> float:
    """Sub-score [0, 20]: blend of category trend (0..100) and fashion watch (0..20)."""
    cat_part = max(0.0, min(20.0, category_trend / 5.0))
    if fashion_watch_score is None:
        return cat_part
    fw = max(0.0, min(20.0, float(fashion_watch_score)))
    # Weighted 60/40 to keep category trend dominant — it reflects local sales.
    return 0.6 * cat_part + 0.4 * fw


def _price_position_score(
    sale_price: float,
    market_price_estimate: float | None,
    thresholds: list[float] | None = None,
    points: list[float] | None = None,
) -> float:
    """Sub-score [0, 20]: how cheap we are vs the estimated market median.

    Default thresholds (ratio = sale / market):
      ≤ 0.7 → 20, ≤ 0.9 → 16, ≤ 1.1 → 12, ≤ 1.3 → 8, > 1.3 → 4.
    """
    if not market_price_estimate or market_price_estimate <= 0:
        return 10.0  # neutral when unknown
    th = thresholds or _DEFAULT_PRICE_THRESHOLDS
    pts = points or _DEFAULT_PRICE_POINTS
    ratio = sale_price / market_price_estimate
    for cutoff, value in zip(th, pts):
        if ratio <= cutoff:
            return float(value)
    return float(pts[-1])


def _attractivity_score(
    category_avg_velocity: float | None,
    brand_score: float | None,
    condition: str | None,
) -> tuple[float, dict]:
    """Sub-score [0, 20] driven by 90j sales history of the shop.

    - ``category_avg_velocity`` : sales / week for the category over 90 days.
      We map [0, 5+] → [0, 12] (capped) — main driver.
    - ``brand_score``           : 0..20 from BrandTier (cap contribution to 5).
    - ``condition``             : excellent → 3, good → 2, fair → 1, else 0.

    Returns (score, breakdown) where breakdown documents each contribution
    so the admin UI can render the calculation step by step.
    """
    velocity = max(0.0, float(category_avg_velocity or 0.0))
    velocity_pts = min(12.0, velocity * 2.4)  # 5/week → 12 pts

    brand_pts = 0.0
    if brand_score is not None:
        brand_pts = min(5.0, max(0.0, float(brand_score)) / 4.0)

    cond = (condition or "").lower().replace(" ", "_")
    cond_map = {
        "neuf_etiquette": 3.0,
        "neuf": 3.0,
        "tres_bon": 2.0,
        "bon": 1.0,
        "correct": 0.0,
    }
    cond_pts = cond_map.get(cond, 1.0)

    score = min(20.0, velocity_pts + brand_pts + cond_pts)
    breakdown = {
        "category_velocity_per_week": round(velocity, 2),
        "velocity_points": round(velocity_pts, 2),
        "brand_points": round(brand_pts, 2),
        "condition_label": cond or "tres_bon",
        "condition_points": round(cond_pts, 2),
        "total": round(score, 2),
    }
    return score, breakdown


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_score(
    *,
    shelf_date: Optional[datetime],
    sale_price: float,
    market_price_estimate: float | None,
    category_name: str | None,
    category_trend: float = 50.0,
    category_avg_velocity: float | None = None,
    brand_score: float | None = None,
    condition: str | None = None,
    fashion_watch_score: float | None = None,
    season_score_override: float | None = None,
    config: dict | None = None,
) -> dict:
    """Compute the v3 score (5 criteria).

    Returns a dict ready for both the API response and the admin breakdown:
      {
        "total_score":     0..100,
        "score_attractivity": 0..20,
        "score_season":       0..20,
        "score_age":          0..20,
        "score_trend":        0..20,
        "score_price":        0..20,
        "weeks_on_shelf":     int,
        "action":          "...",
        "action_color":    "red|orange|yellow|green",
        "breakdown":       per-criterion details (UI),
      }
    """
    weights = _resolve_weights(config)
    age_table = (config or {}).get("age_weeks_table") or _DEFAULT_AGE_WEEKS_TABLE
    season_calendar = (config or {}).get("season_calendar") or {}
    price_thresholds = (config or {}).get("price_thresholds") or _DEFAULT_PRICE_THRESHOLDS
    price_points = (config or {}).get("price_points") or _DEFAULT_PRICE_POINTS
    max_weeks_on_shelf = int((config or {}).get("max_weeks_on_shelf", 6))

    weeks = _weeks_on_shelf(shelf_date)
    score_attractivity, attr_breakdown = _attractivity_score(
        category_avg_velocity=category_avg_velocity,
        brand_score=brand_score,
        condition=condition,
    )
    score_season = _season_score(category_name, season_calendar, season_score_override)
    score_age = _age_score(weeks, age_table)
    score_trend = _trend_score(category_trend, fashion_watch_score)
    score_price = _price_position_score(
        sale_price, market_price_estimate, price_thresholds, price_points
    )

    total = (
        score_attractivity * weights["attractivity"]
        + score_season * weights["season"]
        + score_age * weights["age"]
        + score_trend * weights["trend"]
        + score_price * weights["price"]
    ) * 5  # scale to 0..100

    # Hard rule: anything past max_weeks_on_shelf (= 6 weeks by default) is
    # forced out of the shop on Thursday — the score reflects that intent.
    sortie_forcee = weeks >= max_weeks_on_shelf

    if sortie_forcee:
        action = f"RETIRER — sortie automatique (semaine {weeks + 1})"
        action_color = "red"
    elif total < 30:
        action = "RETIRER — produit trop longtemps en rayon"
        action_color = "red"
    elif total < 50:
        action = "RÉDUIRE PRIX — repositionnement suggéré"
        action_color = "orange"
    elif total < 70:
        action = "METTRE EN AVANT — déplacer en vitrine ou zone Tendance"
        action_color = "yellow"
    else:
        action = "MAINTENIR — bon potentiel de vente"
        action_color = "green"

    return {
        "total_score": round(total, 1),
        "score_attractivity": round(score_attractivity, 1),
        "score_season": round(score_season, 1),
        "score_age": round(score_age, 1),
        "score_trend": round(score_trend, 1),
        "score_price": round(score_price, 1),
        "weeks_on_shelf": weeks,
        "action": action,
        "action_color": action_color,
        "sortie_forcee": sortie_forcee,
        "breakdown": {
            "attractivity": attr_breakdown,
            "season": {
                "category": category_name,
                "calendar_months": season_calendar.get(category_name) if category_name else None,
                "current_month": datetime.now(timezone.utc).month,
                "score": round(score_season, 2),
            },
            "age": {
                "weeks_on_shelf": weeks,
                "weeks_table": age_table,
                "score": round(score_age, 2),
            },
            "trend": {
                "category_trend_0_100": round(category_trend, 1),
                "fashion_watch_score": fashion_watch_score,
                "score": round(score_trend, 2),
            },
            "price": {
                "sale_price": float(sale_price),
                "market_price_estimate": market_price_estimate,
                "ratio": (
                    round(sale_price / market_price_estimate, 3)
                    if market_price_estimate
                    else None
                ),
                "thresholds": price_thresholds,
                "score": round(score_price, 2),
            },
        },
    }
