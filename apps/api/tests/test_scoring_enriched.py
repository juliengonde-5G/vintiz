"""Tests for the enriched scoring inputs (P2-011 + P2-012).

These cover the new keyword arguments on ``compute_score``:
- ``brand_score`` overrides the legacy hardcoded brand sets (P2-012).
- ``photo_count`` + ``photo_avg_confidence`` produce a richer photo
  sub-score that rewards multi-photo intake (P2-011).

The legacy behaviour is verified separately in ``test_scoring_formula``;
this file focuses on what the new path adds.
"""

from datetime import datetime, timezone

from app.services.scoring_service import (
    _legacy_brand_score,
    _photo_subscore,
    compute_score,
)


def _fresh_now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# brand_score override (P2-012)
# ---------------------------------------------------------------------------


def test_brand_score_override_replaces_legacy_lookup():
    """A caller-supplied brand_score wins, even when the brand string
    would have matched a legacy tier."""
    legacy = compute_score(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand="zara", photo_url=None,  # legacy = mid → 10
    )
    overridden = compute_score(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand="zara", photo_url=None,
        brand_score=20.0,  # override → luxury-tier value
    )
    assert overridden["score_brand"] == 20.0
    assert overridden["score_brand"] > legacy["score_brand"]


def test_brand_score_override_clamped_to_0_20():
    """Defensive clamp: an out-of-range override doesn't poison the total."""
    too_low = compute_score(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand=None, photo_url=None, brand_score=-50.0,
    )
    too_high = compute_score(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand=None, photo_url=None, brand_score=999.0,
    )
    assert too_low["score_brand"] == 0.0
    assert too_high["score_brand"] == 20.0


def test_legacy_brand_score_helper_matches_old_behaviour():
    """The extracted helper preserves the original tier ladder."""
    assert _legacy_brand_score("Hermes Paris") == 20.0
    assert _legacy_brand_score("Sandro") == 15.0
    assert _legacy_brand_score("zara") == 10.0
    assert _legacy_brand_score("Unknown Co.") == 8.0
    assert _legacy_brand_score(None) == 5.0


def test_no_brand_score_falls_back_to_legacy():
    """Callers that don't pass brand_score keep the original behaviour."""
    result = compute_score(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand="Hermes", photo_url=None,
    )
    assert result["score_brand"] == 20.0  # luxury via legacy match


# ---------------------------------------------------------------------------
# photo_count + photo_avg_confidence (P2-011)
# ---------------------------------------------------------------------------


def test_photo_subscore_legacy_when_count_omitted():
    """No count → binary 0 or 20 (the V1 behaviour)."""
    assert _photo_subscore(None, None, None) == 0.0
    assert _photo_subscore("https://x", None, None) == 20.0


def test_photo_subscore_zero_photos_yields_zero():
    assert _photo_subscore(None, 0, 0.5) == 0.0


def test_photo_subscore_scales_with_count():
    """Count adds 5 points per photo capped at 15 (3 photos = 15)."""
    assert _photo_subscore("u", 1, 0.0) == 5.0
    assert _photo_subscore("u", 2, 0.0) == 10.0
    assert _photo_subscore("u", 3, 0.0) == 15.0
    # Cap holds even at high counts.
    assert _photo_subscore("u", 10, 0.0) == 15.0


def test_photo_subscore_adds_confidence_bonus():
    """Confidence adds up to 5 points on top of the count base.

    0 photos always yields 0 — there's no base to add to. This is by
    design: a high-confidence prediction with no actual photo on file
    shouldn't reward the score.
    """
    assert _photo_subscore("u", 0, 1.0) == 0.0
    # 1 photo + perfect confidence → 5 (count) + 5 (bonus) = 10
    assert _photo_subscore("u", 1, 1.0) == 10.0
    # 3 photos + perfect confidence → 15 + 5 = 20 (cap)
    assert _photo_subscore("u", 3, 1.0) == 20.0


def test_photo_subscore_clamps_confidence():
    """Bad confidence values (negative, > 1) are clamped."""
    assert _photo_subscore("u", 1, -0.5) == 5.0  # confidence forced to 0
    assert _photo_subscore("u", 1, 2.0) == 10.0   # confidence forced to 1


def test_compute_score_uses_photo_subscore_in_total():
    """A product with 3 high-confidence photos beats one with a single
    photo on the new scoring path."""
    base = dict(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand=None, photo_url="u",
    )
    one_photo = compute_score(**base, photo_count=1, photo_avg_confidence=0.5)
    rich = compute_score(**base, photo_count=3, photo_avg_confidence=0.9)
    assert rich["total_score"] > one_photo["total_score"]
    # 3 photos cap base at 15, +confidence bonus 0.9*5=4.5 → 19.5.
    assert rich["score_photos"] == 19.5
    # 4+ photos with full confidence saturate the cap at 20.
    saturated = compute_score(**base, photo_count=4, photo_avg_confidence=1.0)
    assert saturated["score_photos"] == 20.0


def test_compute_score_photo_legacy_path_unchanged():
    """If the caller doesn't pass photo_count, the binary score stays
    in place — guarantees zero regression for old code."""
    legacy_with_photo = compute_score(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand=None, photo_url="https://x",
    )
    legacy_no_photo = compute_score(
        shelf_date=_fresh_now(), sale_price=10.0, category_avg_price=10.0,
        condition="bon", brand=None, photo_url=None,
    )
    assert legacy_with_photo["score_photos"] == 20.0
    assert legacy_no_photo["score_photos"] == 0.0
