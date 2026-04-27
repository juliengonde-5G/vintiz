"""Unit tests for the v3 scoring formula (5 criteria)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.scoring_config import DEFAULT_CONFIG, WEIGHT_KEYS
from app.services.scoring_service import compute_score


@pytest.fixture
def perfect_inputs():
    """Inputs that should max every sub-score → total = 100."""
    return dict(
        shelf_date=datetime.now(timezone.utc),  # week 1 → max age points
        sale_price=10.0,
        market_price_estimate=20.0,             # ratio 0.5 ≤ 0.7 → 20
        category_name="Robe",
        category_trend=100.0,                   # 100/5 = 20
        category_avg_velocity=10.0,             # ≥ 5/week → cap at 12 + brand 5 + cond 3 = 20
        brand_score=20.0,
        condition="neuf",
        fashion_watch_score=20.0,
        season_score_override=20.0,             # bypass calendar so we control the season
    )


def test_default_weights_sum_to_one():
    total = sum(DEFAULT_CONFIG["weights"][k] for k in WEIGHT_KEYS)
    assert abs(total - 1.0) < 1e-9


def test_perfect_inputs_yield_score_100(perfect_inputs):
    out = compute_score(**perfect_inputs)
    assert out["total_score"] == pytest.approx(100.0, abs=0.5)
    assert out["action_color"] == "green"
    assert out["weeks_on_shelf"] == 0
    for key in (
        "score_attractivity", "score_season", "score_age", "score_trend", "score_price"
    ):
        assert out[key] <= 20.0


def test_age_table_decreases_score(perfect_inputs):
    """Pushing the shelf_date back to week 6 must drop age sub-score to last value."""
    inp = dict(perfect_inputs)
    inp["shelf_date"] = datetime.now(timezone.utc) - timedelta(weeks=5, days=2)
    out = compute_score(**inp)
    # week 6 in default table = 2.0
    assert out["score_age"] == pytest.approx(2.0, abs=0.1)
    assert out["weeks_on_shelf"] >= 5


def test_age_table_custom_override():
    """Supplying a custom weeks table is honoured."""
    config = {**DEFAULT_CONFIG, "age_weeks_table": [10, 8, 6, 4, 2, 0]}
    out = compute_score(
        shelf_date=datetime.now(timezone.utc),
        sale_price=10.0,
        market_price_estimate=10.0,
        category_name="Robe",
        config=config,
    )
    # week 1 with custom table → 10 (not 20)
    assert out["score_age"] == pytest.approx(10.0)


def test_max_weeks_on_shelf_forces_retirer(perfect_inputs):
    """A product past max_weeks_on_shelf (= 6) is forced to RETIRER."""
    inp = dict(perfect_inputs)
    inp["shelf_date"] = datetime.now(timezone.utc) - timedelta(weeks=7)
    out = compute_score(**inp)
    assert "RETIRER" in out["action"]
    assert out["sortie_forcee"] is True


def test_price_ratio_thresholds():
    """Verify the 5 price buckets."""
    base = dict(
        shelf_date=datetime.now(timezone.utc),
        category_name=None,
        category_trend=50.0,
        category_avg_velocity=2.0,
        brand_score=10.0,
        condition="bon",
        sale_price=10.0,
    )
    cases = [(5.0, 20.0), (8.5, 16.0), (10.0, 12.0), (12.5, 8.0), (20.0, 4.0)]
    for market, expected_pts in cases:
        out = compute_score(market_price_estimate=market, **base)
        assert out["score_price"] == pytest.approx(expected_pts, abs=0.1), (
            f"market={market} expected {expected_pts}, got {out['score_price']}"
        )


def test_unknown_market_price_is_neutral():
    """No market estimate → neutral 10/20 (won't penalise the product)."""
    out = compute_score(
        shelf_date=datetime.now(timezone.utc),
        sale_price=15.0,
        market_price_estimate=None,
        category_name="Robe",
    )
    assert out["score_price"] == 10.0


def test_breakdown_documents_each_criterion(perfect_inputs):
    out = compute_score(**perfect_inputs)
    bd = out["breakdown"]
    for key in ("attractivity", "season", "age", "trend", "price"):
        assert key in bd
    assert bd["age"]["weeks_table"] == [20, 17, 13, 10, 6, 2]
    assert bd["age"]["weeks_on_shelf"] == 0
    assert bd["price"]["sale_price"] == 10.0


def test_low_signals_yield_red_action():
    """All signals near zero → score < 30 → RETIRER."""
    out = compute_score(
        shelf_date=datetime.now(timezone.utc) - timedelta(weeks=2),
        sale_price=20.0,
        market_price_estimate=10.0,   # ratio 2.0 → 4 pts
        category_name=None,
        category_trend=0.0,
        category_avg_velocity=0.0,
        brand_score=0.0,
        condition="correct",
        season_score_override=5.0,
    )
    assert out["total_score"] < 50
    assert out["action_color"] in ("red", "orange")


def test_season_override_bypasses_calendar():
    out = compute_score(
        shelf_date=datetime.now(timezone.utc),
        sale_price=10.0,
        market_price_estimate=10.0,
        category_name="Robe",
        season_score_override=2.0,
    )
    assert out["score_season"] == 2.0
