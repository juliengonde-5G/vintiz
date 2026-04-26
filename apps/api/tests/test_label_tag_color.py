"""Tests for the life-cycle tag colour on product labels (P3-002)."""

from datetime import datetime, timedelta, timezone

from app.services.label import (
    GREEN_AGE_THRESHOLD_DAYS,
    RED_AGE_THRESHOLD_DAYS,
    TAG_COLOR_GREEN,
    TAG_COLOR_GREY,
    TAG_COLOR_ORANGE,
    TAG_COLOR_RED,
    TAG_COLOR_YELLOW,
    generate_label,
    life_cycle_tag_color,
)


def test_discounted_status_yields_yellow():
    assert life_cycle_tag_color(status="discounted", displayed_at=None) == TAG_COLOR_YELLOW


def test_deep_discounted_status_yields_orange():
    assert life_cycle_tag_color(status="deep_discounted", displayed_at=None) == TAG_COLOR_ORANGE


def test_sold_or_returned_yields_grey():
    assert life_cycle_tag_color(status="sold", displayed_at=None) == TAG_COLOR_GREY
    assert life_cycle_tag_color(status="returned_to_sorting", displayed_at=None) == TAG_COLOR_GREY


def test_fresh_displayed_product_yields_green():
    now = datetime.now(timezone.utc)
    recent = now - timedelta(days=GREEN_AGE_THRESHOLD_DAYS - 5)
    assert life_cycle_tag_color(status="displayed", displayed_at=recent) == TAG_COLOR_GREEN


def test_aged_displayed_product_yields_red():
    now = datetime.now(timezone.utc)
    long_ago = now - timedelta(days=RED_AGE_THRESHOLD_DAYS + 5)
    assert life_cycle_tag_color(status="displayed", displayed_at=long_ago) == TAG_COLOR_RED


def test_mid_age_yields_yellow():
    now = datetime.now(timezone.utc)
    mid = now - timedelta(days=(GREEN_AGE_THRESHOLD_DAYS + RED_AGE_THRESHOLD_DAYS) // 2)
    assert life_cycle_tag_color(status="displayed", displayed_at=mid) == TAG_COLOR_YELLOW


def test_legacy_display_alias_works():
    """The legacy 'display' (vs the explicit 'displayed') still resolves
    via the same age rules."""
    now = datetime.now(timezone.utc)
    fresh = now - timedelta(days=5)
    assert life_cycle_tag_color(status="display", displayed_at=fresh) == TAG_COLOR_GREEN


def test_displayed_without_anchor_falls_back_to_green():
    """A product on the floor with no displayed_at anchor is treated as
    just-arrived rather than 'unknown', so the manager spots it as
    fresh on the floor."""
    assert life_cycle_tag_color(status="displayed", displayed_at=None) == TAG_COLOR_GREEN


def test_pre_floor_statuses_yield_grey():
    assert life_cycle_tag_color(status="received", displayed_at=None) == TAG_COLOR_GREY
    assert life_cycle_tag_color(status="tagged", displayed_at=None) == TAG_COLOR_GREY


# ---------------------------------------------------------------------------
# generate_label() integration — the tag is rendered when the colour is set
# ---------------------------------------------------------------------------


def test_generate_label_with_tag_includes_corner_pixel():
    """The triangle starts at (0,0); when a colour is supplied, that pixel
    must be the colour, not white."""
    from PIL import Image
    import io

    png_with_tag = generate_label(
        product_name="Robe noire",
        category="Robes",
        barcode_data="ABC123",
        price="49.00 €",
        week=18,
        tag_color=TAG_COLOR_RED,
    )
    img = Image.open(io.BytesIO(png_with_tag)).convert("RGB")
    # PIL gives (R,G,B); compare to our hex.
    assert img.getpixel((1, 1)) != (255, 255, 255)


def test_generate_label_tag_color_actually_paints_corner():
    """Two labels — one without a tag, one red — must differ in the
    top-left triangle area. The header band is teal anyway, so we
    just check that the colour changes."""
    from PIL import Image
    import io

    png_no_tag = generate_label(
        product_name="Robe noire",
        category="Robes",
        barcode_data="ABC123",
        price="49.00 €",
        week=18,
    )
    png_red = generate_label(
        product_name="Robe noire",
        category="Robes",
        barcode_data="ABC123",
        price="49.00 €",
        week=18,
        tag_color=TAG_COLOR_RED,
    )
    img_no_tag = Image.open(io.BytesIO(png_no_tag)).convert("RGB")
    img_red = Image.open(io.BytesIO(png_red)).convert("RGB")
    # Sample a pixel well inside the triangle (size 38), but off the
    # outer black border at (0,0).
    assert img_no_tag.getpixel((5, 5)) != img_red.getpixel((5, 5))
