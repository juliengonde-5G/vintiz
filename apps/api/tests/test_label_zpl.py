"""Unit tests for the Zebra ZPL label generator (25×52 mm standard tag).

The boutique tag is laid out landscape and prints four stacked rows —
Semaine, Type produit (catégorie), code-barres (Code 128) and réf produit.
These tests run against pure ``LabelData`` payloads so no database is needed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.zebra_zpl import (
    LABEL_HEIGHT_DOTS,
    LABEL_WIDTH_DOTS,
    LabelData,
    build_label_set_zpl,
    build_label_zpl,
    build_price_label_zpl,
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


def test_label_renders_product_type():
    zpl = build_label_zpl(_veste_femme_m())
    # Landscape tag shows the product TYPE (category), not the full name.
    assert "Vestes" in zpl
    assert "Veste en jean délavée" not in zpl


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


def test_compact_tag_omits_price_and_condition():
    """The landscape tag drops the price / état / markdown block.

    It keeps Semaine, Type produit (catégorie), code-barres et réf produit.
    """
    zpl = build_label_zpl(_veste_femme_m())
    assert "€" not in zpl
    assert "12,00" not in zpl
    assert "Très bon état" not in zpl
    assert "Démarque" not in zpl


def test_copies_propagate_to_pq_command():
    zpl = build_label_zpl(_jean_homme_l(), copies=3)
    assert "^PQ3" in zpl


def test_zero_or_negative_copies_clamped_to_one():
    assert "^PQ1" in build_label_zpl(_veste_femme_m(), copies=0)
    assert "^PQ1" in build_label_zpl(_veste_femme_m(), copies=-5)


def test_zpl_control_characters_in_type_are_neutralised():
    # The rendered field is now the product type (category); ZPL control
    # prefixes in it must be neutralised so they can't break the print job.
    data = LabelData(
        product_name="Robe",
        category="Robe ^XA ~tilde \\back",
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


def test_product_type_clamped_to_22_chars():
    data = LabelData(
        product_name="Robe",
        category="x" * 60,
        size=None,
        condition="Bon état",
        sale_price=20.0,
        barcode="VTZ-2026-00600",
        shelf_date=REF_SHELF,
    )
    zpl = build_label_zpl(data)
    # 21 chars + ellipsis = 22 visible characters max for the type field.
    assert "x" * 22 not in zpl
    assert "…" in zpl


def test_price_label_renders_brand_and_price():
    zpl = build_price_label_zpl(_veste_femme_m())
    assert zpl.startswith("^XA") and zpl.endswith("^XZ")
    assert "VINTIZ" in zpl, "le tag prix porte le logo/lettrage VINTIZ"
    assert "12,00 €" in zpl, "prix de vente au format FR"


def test_price_label_uses_same_25x52_media():
    zpl = build_price_label_zpl(_veste_femme_m())
    assert f"^PW{LABEL_WIDTH_DOTS}" in zpl
    assert f"^LL{LABEL_HEIGHT_DOTS}" in zpl


def test_label_set_emits_product_then_price_label():
    zpl = build_label_set_zpl(_veste_femme_m())
    # Deux jobs ZPL = deux étiquettes physiques imprimées à la suite.
    assert zpl.count("^XA") == 2
    assert zpl.count("^XZ") == 2
    # Tag produit (code-barres/réf) + tag prix (logo + prix).
    assert "^FDVTZ-2026-00142^FS" in zpl
    assert "VINTIZ" in zpl
    assert "12,00 €" in zpl
