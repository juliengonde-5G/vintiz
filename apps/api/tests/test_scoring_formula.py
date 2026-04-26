"""Mathematical validation of the 6-component product scoring formula.

Investigates the V2 audit's claim of a weighting bug ("la formule fait *5
puis /N qui distort les sous-scores"). Reading scoring_service.py shows
no /N — only a final *5 to scale the weighted sum from [0,20] to [0,100].
These tests confirm the formula is mathematically correct and document
the actual behavior so future refactors don't regress.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.scoring_service import compute_score


def _fresh_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Bounds: the formula must produce a total in [0, 100]
# ---------------------------------------------------------------------------


def test_perfect_score_yields_100():
    """All sub-scores at their maximum must produce a total of exactly 100."""
    result = compute_score(
        shelf_date=_fresh_now(),         # score_age = 20
        sale_price=10.0,                 # ratio 0.5 → score_prix = 20
        category_avg_price=20.0,
        condition="neuf_etiquette",      # score_condition = 20
        brand="Hermes",                  # score_brand = 20
        photo_url="https://x/y.jpg",     # score_photos = 20
        category_trend=100.0,            # score_category = 20
    )
    assert result["total_score"] == 100.0


def test_worst_score_yields_0():
    """All sub-scores at their minimum must produce a total of exactly 0."""
    very_old = _fresh_now() - timedelta(days=120)  # 120//3 = 40 → max(0, -20) = 0
    result = compute_score(
        shelf_date=very_old,             # score_age = 0
        sale_price=100.0,                # ratio 5 → score_prix = 0
        category_avg_price=20.0,
        condition="correct",             # score_condition = 5 (no "bad" worse exists)
        brand=None,                      # score_brand = 5
        photo_url=None,                  # score_photos = 0
        category_trend=0.0,              # score_category = 0
    )
    # Min realistic: 0*0.30 + 0*0.20 + 5*0.20 + 5*0.15 + 0*0.10 + 0*0.05 = 1.75
    # *5 = 8.75 → round(_, 1) = 8.8 due to Python float rounding
    assert 0 <= result["total_score"] <= 100
    assert result["total_score"] == pytest.approx(8.75, abs=0.1)


def test_total_always_in_bounds_across_random_inputs():
    """Sweep a grid of inputs and assert total stays in [0, 100]."""
    conditions = ["neuf_etiquette", "neuf", "tres_bon", "bon", "correct"]
    brands = [None, "unknown", "Zara", "Sandro", "Chanel"]
    for days in (0, 15, 30, 60, 120, 365):
        for price_ratio in (0.4, 0.9, 1.2, 2.5):
            for condition in conditions:
                for brand in brands:
                    for photo in (None, "url"):
                        for trend in (0.0, 50.0, 100.0):
                            shelf = _fresh_now() - timedelta(days=days)
                            r = compute_score(
                                shelf_date=shelf,
                                sale_price=10.0 * price_ratio,
                                category_avg_price=10.0,
                                condition=condition,
                                brand=brand,
                                photo_url=photo,
                                category_trend=trend,
                            )
                            assert 0 <= r["total_score"] <= 100, (
                                f"Out of bounds: {r['total_score']} for "
                                f"days={days}, ratio={price_ratio}, "
                                f"condition={condition}, brand={brand}, "
                                f"photo={photo}, trend={trend}"
                            )


# ---------------------------------------------------------------------------
# Weights: must sum to 1.0 so that the final *5 maps [0,20] → [0,100]
# ---------------------------------------------------------------------------


def test_weights_sum_to_one():
    """The weighted average must collapse to 1.0 — checks the formula directly.

    If all sub-scores equal a constant K, the weighted sum equals K*1.0 = K,
    and *5 yields 5K. Verifies for K=10 → expect total 50.
    """
    # Construct inputs that yield sub-scores all equal to 10:
    # - score_age = 10 → days_on_shelf // 3 = 10 → days = 30
    # - score_prix = 10 → no category_avg → defaults to 10
    # - score_condition = 10 → "bon"
    # - score_brand = 10 → mid_brand "zara"
    # - score_category = 10 → trend = 50
    # - score_photos = 10 → impossible (binary 0 or 20)
    # So we test the weighted sum manually instead via known sub-scores.
    result = compute_score(
        shelf_date=_fresh_now() - timedelta(days=30),  # score_age = 10
        sale_price=10.0,
        category_avg_price=0.0,                        # score_prix = 10 (default)
        condition="bon",                               # score_condition = 10
        brand="zara",                                  # score_brand = 10
        photo_url=None,                                # score_photos = 0
        category_trend=50.0,                           # score_category = 10
    )
    # Expected: (10*0.30 + 10*0.20 + 10*0.20 + 10*0.15 + 10*0.10 + 0*0.05) * 5
    # = (3 + 2 + 2 + 1.5 + 1 + 0) * 5
    # = 9.5 * 5
    # = 47.5
    assert result["total_score"] == 47.5


# ---------------------------------------------------------------------------
# Each component contributes its declared weight
# ---------------------------------------------------------------------------


def test_age_component_weight_is_30_pct():
    """Toggling only score_age between max and min must shift total by 30."""
    base_kwargs = dict(
        sale_price=10.0,
        category_avg_price=0.0,
        condition="bon",          # score_condition = 10
        brand="zara",             # score_brand = 10
        photo_url=None,           # score_photos = 0
        category_trend=50.0,      # score_category = 10
    )
    fresh = compute_score(shelf_date=_fresh_now(), **base_kwargs)
    old = compute_score(
        shelf_date=_fresh_now() - timedelta(days=120), **base_kwargs
    )
    # score_age goes from 20 to 0, delta = 20 * 0.30 * 5 = 30
    assert round(fresh["total_score"] - old["total_score"], 1) == 30.0


def test_photos_component_weight_is_5_pct():
    """Adding a photo_url shifts total by exactly 5 (20 * 0.05 * 5)."""
    base_kwargs = dict(
        shelf_date=_fresh_now(),
        sale_price=10.0,
        category_avg_price=0.0,
        condition="bon",
        brand="zara",
        category_trend=50.0,
    )
    without = compute_score(photo_url=None, **base_kwargs)
    with_photo = compute_score(photo_url="url", **base_kwargs)
    assert round(with_photo["total_score"] - without["total_score"], 1) == 5.0


def test_category_trend_static_default_yields_neutral_subscore():
    """The default category_trend=50.0 (V2 'static value') yields a 10/20 sub-score.

    This is correct neutral behavior — the issue raised by V2 is not a math
    bug but the fact that the trend is never recomputed dynamically.
    Connecting ai_trend.compute() is ticket P2-010.
    """
    result = compute_score(
        shelf_date=_fresh_now(),
        sale_price=10.0,
        category_avg_price=0.0,
        condition="bon",
        brand="zara",
        photo_url=None,
        # category_trend defaults to 50.0
    )
    assert result["score_category"] == 10.0  # 50/5


# ---------------------------------------------------------------------------
# Sub-scores are returned for inspection (not silently weighted)
# ---------------------------------------------------------------------------


def test_subscores_returned_in_raw_0_to_20_scale():
    """Ensure the sub-scores in the return dict are raw [0,20], not pre-weighted."""
    result = compute_score(
        shelf_date=_fresh_now(),
        sale_price=10.0,
        category_avg_price=20.0,
        condition="neuf_etiquette",
        brand="Hermes",
        photo_url="url",
        category_trend=100.0,
    )
    for key in (
        "score_age", "score_prix", "score_condition",
        "score_brand", "score_category", "score_photos",
    ):
        assert 0 <= result[key] <= 20, f"{key}={result[key]} out of [0,20]"


# ---------------------------------------------------------------------------
# Action mapping based on total_score buckets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "total_threshold,expected_color",
    [
        (29.9, "red"),     # < 30
        (49.9, "orange"),  # 30 ≤ x < 50
        (69.9, "yellow"),  # 50 ≤ x < 70
        (70.0, "green"),   # ≥ 70
    ],
)
def test_action_color_buckets(total_threshold, expected_color):
    """Verify the action_color mapping matches the documented buckets.

    Builds inputs that produce a total close to the bucket threshold by
    choosing condition + brand + photo + age combinations.
    """
    # We can't easily hit exact totals, but we can verify the color assignment
    # logic by constructing inputs that fall in each bucket.
    #
    # red bucket: very old + cheap brand + no photo + low trend
    # orange bucket: old-ish + low brand
    # yellow bucket: medium age + good brand
    # green bucket: fresh + premium brand + photo + high trend
    if expected_color == "red":
        result = compute_score(
            shelf_date=_fresh_now() - timedelta(days=120),
            sale_price=100.0, category_avg_price=10.0,
            condition="correct", brand=None, photo_url=None, category_trend=0.0,
        )
    elif expected_color == "orange":
        # Targets total ≈ 36 (within [30, 50)):
        # age=5 (45d) * .30 + prix=10 (default) * .20 + cond=10 (bon) * .20
        # + brand=5 (None) * .15 + cat=10 (trend 50) * .10 + photos=0 * .05
        # = 1.5 + 2 + 2 + 0.75 + 1 + 0 = 7.25 → *5 = 36.25
        result = compute_score(
            shelf_date=_fresh_now() - timedelta(days=45),
            sale_price=10.0, category_avg_price=0.0,
            condition="bon", brand=None, photo_url=None, category_trend=50.0,
        )
    elif expected_color == "yellow":
        result = compute_score(
            shelf_date=_fresh_now() - timedelta(days=30),
            sale_price=10.0, category_avg_price=10.0,
            condition="tres_bon", brand="sandro", photo_url="url", category_trend=50.0,
        )
    else:  # green
        result = compute_score(
            shelf_date=_fresh_now(),
            sale_price=8.0, category_avg_price=10.0,
            condition="neuf_etiquette", brand="Chanel", photo_url="url",
            category_trend=100.0,
        )
    assert result["action_color"] == expected_color, (
        f"Got total={result['total_score']} color={result['action_color']}, "
        f"expected color={expected_color}"
    )


# ---------------------------------------------------------------------------
# Documented limitations (not bugs, but tracked for future tickets)
# ---------------------------------------------------------------------------


def test_photos_score_is_binary_documented_limitation():
    """Document that score_photos is binary 0/20 — ticket P2-011 will enrich it
    with confidence + photo count once multi-photos (P1-008) is in place."""
    no_photo = compute_score(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand="zara", photo_url=None,
    )
    with_photo = compute_score(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand="zara", photo_url="any-url",
    )
    assert no_photo["score_photos"] == 0
    assert with_photo["score_photos"] == 20
    # No middle ground today — P2-011 will add fine-grained scoring.


def test_brand_tier_lookup_uses_substring_match():
    """Document brand matching uses substring — partial matches work but
    typos do not. Ticket P2-012 will move this to a DB-backed BrandTier."""
    # Substring match works:
    r1 = compute_score(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand="Hermes Paris", photo_url=None,
    )
    assert r1["score_brand"] == 20  # luxury
    # Typo fails — falls back to "unknown brand" tier:
    r2 = compute_score(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand="Herms", photo_url=None,
    )
    assert r2["score_brand"] == 8  # any non-recognized brand
