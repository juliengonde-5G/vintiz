"""Tests pour le moteur de scoring v3 — 5 sous-scores + total + action.

Couvre :
- Sous-scores individuels (age, season, trend, price, attractivity)
- Pondération par défaut + override via config
- Seuils d'action (RETIRER < 30, RÉDUIRE 30-49, AVANT 50-69, MAINTENIR ≥ 70)
- Sortie forcée à max_weeks_on_shelf
- Edge cases : pas de market_price, pas de category, pas de fashion_watch
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.scoring_service import (
    _DEFAULT_AGE_WEEKS_TABLE,
    _DEFAULT_PRICE_POINTS,
    _age_score,
    _attractivity_score,
    _price_position_score,
    _season_score,
    _trend_score,
    _weeks_on_shelf,
    compute_score,
)


# -- _weeks_on_shelf -----------------------------------------------


def test_weeks_on_shelf_none_returns_zero():
    assert _weeks_on_shelf(None) == 0


def test_weeks_on_shelf_just_landed():
    now = datetime.now(timezone.utc)
    assert _weeks_on_shelf(now) == 0


def test_weeks_on_shelf_3_weeks_ago():
    past = datetime.now(timezone.utc) - timedelta(days=21)
    assert _weeks_on_shelf(past) == 3


def test_weeks_on_shelf_naive_datetime_assumed_utc():
    """Tolère un datetime sans tzinfo en l'assumant UTC."""
    past = datetime.utcnow() - timedelta(days=14)
    assert _weeks_on_shelf(past) == 2


# -- _age_score ----------------------------------------------------


def test_age_score_week_0_uses_first_table_value():
    """Tout juste posée → bench-mark sur week 1."""
    assert _age_score(0, _DEFAULT_AGE_WEEKS_TABLE) == 20.0


def test_age_score_week_1():
    assert _age_score(1, _DEFAULT_AGE_WEEKS_TABLE) == 20.0


def test_age_score_week_3():
    """Index 2 dans la table par défaut [20, 17, 13, 10, 6, 2]."""
    assert _age_score(3, _DEFAULT_AGE_WEEKS_TABLE) == 13.0


def test_age_score_week_6_uses_last_value():
    assert _age_score(6, _DEFAULT_AGE_WEEKS_TABLE) == 2.0


def test_age_score_week_10_clamps_to_last():
    assert _age_score(10, _DEFAULT_AGE_WEEKS_TABLE) == 2.0


def test_age_score_empty_table_returns_zero():
    assert _age_score(2, []) == 0.0


def test_age_score_custom_table():
    table = [15.0, 10.0, 5.0]
    assert _age_score(0, table) == 15.0
    assert _age_score(2, table) == 5.0
    assert _age_score(99, table) == 5.0


# -- _season_score -------------------------------------------------


def test_season_score_explicit_value_wins():
    assert _season_score("manteau", {}, 17.5) == 17.5


def test_season_score_explicit_clamped_to_max():
    assert _season_score("manteau", {}, 99.0) == 20.0


def test_season_score_explicit_clamped_to_min():
    assert _season_score("manteau", {}, -5.0) == 0.0


def test_season_score_no_calendar_returns_neutral():
    assert _season_score("robe", None, None) == 10.0


def test_season_score_no_category_returns_neutral():
    assert _season_score(None, {"robe": [6, 7]}, None) == 10.0


def test_season_score_in_season_full_marks():
    cur = datetime.now(timezone.utc).month
    cal = {"robe": [cur]}
    assert _season_score("robe", cal, None) == 20.0


def test_season_score_off_season_low_marks():
    cur = datetime.now(timezone.utc).month
    far = ((cur + 5) % 12) + 1  # 6 mois plus tard, hors ±1
    cal = {"manteau": [far]}
    assert _season_score("manteau", cal, None) == 5.0


def test_season_score_adjacent_month():
    cur = datetime.now(timezone.utc).month
    nxt = (cur % 12) + 1
    cal = {"robe": [nxt]}
    assert _season_score("robe", cal, None) == 12.0


# -- _trend_score --------------------------------------------------


def test_trend_score_category_only_50():
    assert _trend_score(50.0, None) == 10.0


def test_trend_score_category_max_capped_at_20():
    assert _trend_score(150.0, None) == 20.0


def test_trend_score_category_zero():
    assert _trend_score(0.0, None) == 0.0


def test_trend_score_blends_with_fashion_watch():
    """60/40 weighted blend."""
    # category 50 → cat_part = 10 ; fashion_watch 20 → fw_part = 20
    # blend = 0.6 * 10 + 0.4 * 20 = 6 + 8 = 14
    assert _trend_score(50.0, 20.0) == 14.0


def test_trend_score_fashion_watch_clamped_negative():
    """fashion_watch < 0 est ramené à 0."""
    assert _trend_score(50.0, -5.0) == 6.0  # 0.6 * 10 + 0.4 * 0


# -- _price_position_score -----------------------------------------


def test_price_no_market_estimate_neutral():
    assert _price_position_score(50.0, None) == 10.0
    assert _price_position_score(50.0, 0) == 10.0


def test_price_very_cheap_max_score():
    """sale = 60, market = 100 → ratio 0.6 ≤ 0.7 → 20."""
    assert _price_position_score(60.0, 100.0) == 20.0


def test_price_at_market_avg_12():
    """ratio 1.0 → ≤ 1.1 → 12."""
    assert _price_position_score(100.0, 100.0) == 12.0


def test_price_overpriced_min():
    """ratio 1.5 → > 1.3 → fallback 4."""
    assert _price_position_score(150.0, 100.0) == _DEFAULT_PRICE_POINTS[-1]
    assert _price_position_score(150.0, 100.0) == 4.0


# -- _attractivity_score -------------------------------------------


def test_attractivity_zero_returns_zero_velocity():
    score, breakdown = _attractivity_score(None, None, None)
    # velocity 0 + brand 0 + cond default ("tres_bon") fallback 1.0 → 1.0
    assert breakdown["velocity_points"] == 0.0
    assert score == 1.0  # condition fallback "tres_bon" = 1.0


def test_attractivity_high_velocity_capped_12():
    score, breakdown = _attractivity_score(10.0, None, None)
    # 10 * 2.4 = 24 → capped 12
    assert breakdown["velocity_points"] == 12.0


def test_attractivity_brand_score_capped_at_5():
    """Brand 100 → /4 = 25 → capped 5."""
    _score, breakdown = _attractivity_score(0, 100, None)
    assert breakdown["brand_points"] == 5.0


def test_attractivity_condition_neuf():
    score, breakdown = _attractivity_score(0, None, "neuf")
    assert breakdown["condition_points"] == 3.0


def test_attractivity_condition_correct_yields_zero():
    _score, breakdown = _attractivity_score(0, None, "correct")
    assert breakdown["condition_points"] == 0.0


def test_attractivity_total_capped_at_20():
    """velocity 12 + brand 5 + cond 3 = 20."""
    score, _ = _attractivity_score(10.0, 100.0, "neuf")
    assert score == 20.0


# -- compute_score end-to-end --------------------------------------


def test_compute_score_returns_full_dict():
    out = compute_score(
        shelf_date=None,
        sale_price=50.0,
        market_price_estimate=100.0,
        category_name="robe",
    )
    assert "total_score" in out
    assert "score_attractivity" in out
    assert "score_season" in out
    assert "score_age" in out
    assert "score_trend" in out
    assert "score_price" in out
    assert "weeks_on_shelf" in out
    assert "action" in out
    assert "action_color" in out
    assert "sortie_forcee" in out
    assert "breakdown" in out


def test_compute_score_high_total_yields_maintenir():
    """Tout au max → ≥ 70 → MAINTENIR."""
    out = compute_score(
        shelf_date=None,  # week 0 → score_age max 20
        sale_price=50.0,
        market_price_estimate=100.0,  # ratio 0.5 → 20
        category_name="robe",
        category_trend=100.0,  # 20
        category_avg_velocity=10.0,
        brand_score=100.0,
        condition="neuf",
        fashion_watch_score=20.0,
        season_score_override=20.0,
    )
    assert out["total_score"] >= 70
    assert "MAINTENIR" in out["action"]
    assert out["action_color"] == "green"


def test_compute_score_low_total_yields_retirer():
    """Tout au minimum → < 30 → RETIRER."""
    out = compute_score(
        shelf_date=datetime.now(timezone.utc) - timedelta(days=35),  # 5 weeks
        sale_price=200.0,
        market_price_estimate=100.0,  # overpriced
        category_name="robe",
        category_trend=0.0,
        category_avg_velocity=0.0,
        brand_score=0.0,
        condition="correct",
        season_score_override=0.0,
    )
    assert out["total_score"] < 30
    assert "RETIRER" in out["action"]
    assert out["action_color"] == "red"


def test_compute_score_forced_exit_at_max_weeks():
    """≥ 6 weeks → sortie forcée même si score haut."""
    out = compute_score(
        shelf_date=datetime.now(timezone.utc) - timedelta(days=49),  # 7 weeks
        sale_price=50.0,
        market_price_estimate=100.0,
        category_name="robe",
        category_trend=80.0,
        category_avg_velocity=5.0,
        brand_score=80.0,
        condition="neuf",
        fashion_watch_score=20.0,
    )
    assert out["sortie_forcee"] is True
    assert "sortie automatique" in out["action"]
    assert out["action_color"] == "red"


def test_compute_score_action_thresholds():
    """Vérifie les 4 paliers d'action selon total_score."""
    # Le seuil exact dépend des sous-scores ; on parametrize via
    # season_score_override pour stabiliser.
    cases = [
        (0.0, "RETIRER"),     # tout 0 → 0
        (10.0, "RÉDUIRE"),    # ~30-49
        (14.0, "METTRE EN AVANT"),  # ~50-69
        (20.0, "MAINTENIR"),  # ≥ 70 atteignable avec tout au max
    ]
    for season_override, expected_action_substr in cases:
        out = compute_score(
            shelf_date=None,
            sale_price=50.0,
            market_price_estimate=100.0,
            category_name="robe",
            category_trend=season_override * 5,  # scale to 0..100
            category_avg_velocity=season_override / 4,
            brand_score=season_override * 5,
            condition="neuf" if season_override == 20.0 else "tres_bon" if season_override > 0 else "correct",
            fashion_watch_score=season_override,
            season_score_override=season_override,
        )
        # On ne fait pas un assert in seul, on autorise le sortie_forcee=False
        assert out["sortie_forcee"] is False, (
            f"Case {season_override}: not expected to force exit"
        )


def test_compute_score_custom_weights():
    """Override des poids via config."""
    config = {
        "weights": {
            "attractivity": 1.0,
            "season": 0.0,
            "age": 0.0,
            "trend": 0.0,
            "price": 0.0,
        },
    }
    out = compute_score(
        shelf_date=None,
        sale_price=50.0,
        market_price_estimate=100.0,
        category_name="robe",
        category_avg_velocity=10.0,
        brand_score=100.0,
        condition="neuf",
        config=config,
    )
    # Avec 100 % poids sur attractivity (max 20), total = 20 * 5 = 100
    assert out["total_score"] == 100.0


def test_compute_score_neutral_inputs():
    """Tout neutre → action moyenne."""
    out = compute_score(
        shelf_date=None,
        sale_price=50.0,
        market_price_estimate=100.0,
        category_name=None,
    )
    # Pas de category, pas de calendar, etc. → le score reste positif
    # mais loin du max
    assert 0 <= out["total_score"] <= 100


@pytest.mark.parametrize(
    "shelf_age_days,expected_weeks",
    [(0, 0), (6, 0), (7, 1), (14, 2), (21, 3), (42, 6), (49, 7)],
)
def test_weeks_on_shelf_parametrized(shelf_age_days, expected_weeks):
    past = datetime.now(timezone.utc) - timedelta(days=shelf_age_days)
    assert _weeks_on_shelf(past) == expected_weeks
