"""Unit tests for the Zebra ZPL label generator (25×52 mm standard tag).

The 25×52 boutique tag prints only four things — barcode, its reference,
product name and intake week. These tests run against pure ``LabelData``
payloads so no database is needed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.zebra_zpl import (
    LABEL_HEIGHT_DOTS,
    LABEL_WIDTH_DOTS,
    LabelData,
    build_label_zpl,
)


REF_SHELF = datetime(2026, 5, 14, tzinfo=timezone.utc)


def _veste_femme_m() -> LabelData:
    return LabelData(
        product_name="Veste en jean délavée",
        category="Vestes",
        size="M",
        condition="Très bon état",
        sale_price=12.0,
        barcode="VTZ-2026-00142",
        shelf_date=REF_SHELF,
    )


def _jean_homme_l() -> LabelData:
    return LabelData(
        product_name="Jean droit Levi's 501",
        category="Pantalons",
        size="L",
        condition="Bon état",
        sale_price=8.0,
        barcode="VTZ-2026-00211",
        shelf_date=REF_SHELF,
    )


def test_label_starts_and_ends_with_zpl_markers():
    zpl = build_label_zpl(_veste_femme_m())
    assert zpl.startswith("^XA"), "ZPL job must start with ^XA"
    assert zpl.endswith("^XZ"), "ZPL job must end with ^XZ"


def test_label_declares_utf8_and_25x52_dimensions():
    zpl = build_label_zpl(_veste_femme_m())
    assert "^CI28" in zpl, "UTF-8 must be enabled for accents"
    assert LABEL_WIDTH_DOTS == 200 and LABEL_HEIGHT_DOTS == 416
    assert f"^PW{LABEL_WIDTH_DOTS}" in zpl
    assert f"^LL{LABEL_HEIGHT_DOTS}" in zpl


def test_label_renders_product_name():
    zpl = build_label_zpl(_veste_femme_m())
    assert "Veste en jean délavée" in zpl


def test_label_contains_rotated_code128_barcode_and_ref():
    zpl = build_label_zpl(_veste_femme_m())
    # Rotated Code 128 so the long reference fits on a 25 mm-wide label.
    assert "^BCR," in zpl
    assert "^FDVTZ-2026-00142^FS" in zpl


def test_label_shows_intake_week_derived_from_shelf_date():
    zpl = build_label_zpl(_veste_femme_m())
    week = REF_SHELF.isocalendar()[1]
    assert f"Semaine {week:02d}" in zpl


def test_explicit_week_number_takes_precedence():
    data = LabelData(
        product_name="Robe",
        category="Robes",
        size="S",
        condition="Bon état",
        sale_price=15.0,
        barcode="VTZ-2026-00999",
        shelf_date=REF_SHELF,
        week_number=3,
    )
    assert "Semaine 03" in build_label_zpl(data)


def test_compact_tag_omits_price_category_and_condition():
    """The 25×52 tag drops the old price/category/état/markdown block."""
    zpl = build_label_zpl(_veste_femme_m())
    assert "€" not in zpl
    assert "12,00" not in zpl
    assert "Vestes" not in zpl
    assert "Très bon état" not in zpl
    assert "Démarque" not in zpl


def test_copies_propagate_to_pq_command():
    zpl = build_label_zpl(_jean_homme_l(), copies=3)
    assert "^PQ3" in zpl


def test_zero_or_negative_copies_clamped_to_one():
    assert "^PQ1" in build_label_zpl(_veste_femme_m(), copies=0)
    assert "^PQ1" in build_label_zpl(_veste_femme_m(), copies=-5)


def test_zpl_control_characters_in_name_are_neutralised():
    data = LabelData(
        product_name="Robe ^XA ~tilde \\back",
        category="Robes",
        size=None,
        condition="Bon état",
        sale_price=20.0,
        barcode="VTZ-2026-00500",
        shelf_date=REF_SHELF,
    )
    zpl = build_label_zpl(data)
    assert zpl.count("^XA") == 1
    assert zpl.count("^XZ") == 1
    assert "Robe -XA -tilde /back" in zpl


def test_product_name_clamped_to_40_chars():
    data = LabelData(
        product_name="x" * 60,
        category="Robes",
        size=None,
        condition="Bon état",
        sale_price=20.0,
        barcode="VTZ-2026-00600",
        shelf_date=REF_SHELF,
    )
    zpl = build_label_zpl(data)
    # 39 chars + ellipsis = 40 visible characters max for the name field.
    assert "x" * 40 not in zpl
    assert "…" in zpl
