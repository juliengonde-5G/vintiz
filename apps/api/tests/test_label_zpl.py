"""Unit tests for the Zebra ZPL label generator.

Covers the 3 reference products the brief lists:
- Veste femme M 12 €
- Jean homme L 8 €
- Sac accessoire 5 €

The tests run against pure ``LabelData`` payloads so no database is needed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


def _sac_accessoire() -> LabelData:
    return LabelData(
        product_name="Sac à main cuir",
        category="Accessoires",
        size=None,
        condition="Excellent état",
        sale_price=5.0,
        barcode="VTZ-2026-00305",
        shelf_date=REF_SHELF,
    )


def test_label_starts_and_ends_with_zpl_markers():
    zpl = build_label_zpl(_veste_femme_m())
    assert zpl.startswith("^XA"), "ZPL job must start with ^XA"
    assert zpl.endswith("^XZ"), "ZPL job must end with ^XZ"


def test_label_declares_utf8_and_label_dimensions():
    zpl = build_label_zpl(_veste_femme_m())
    assert "^CI28" in zpl, "UTF-8 must be enabled for accents"
    assert f"^PW{LABEL_WIDTH_DOTS}" in zpl
    assert f"^LL{LABEL_HEIGHT_DOTS}" in zpl


def test_veste_femme_m_renders_name_category_size_price():
    zpl = build_label_zpl(_veste_femme_m())
    assert "Veste en jean délavée" in zpl
    assert "Vestes • T.M" in zpl
    assert "Très bon état" in zpl
    # Price formatted FR-style with comma + euro
    assert "12,00 €" in zpl


def test_jean_homme_l_renders_name_category_size_price():
    zpl = build_label_zpl(_jean_homme_l())
    assert "Jean droit Levi's 501" in zpl
    assert "Pantalons • T.L" in zpl
    assert "8,00 €" in zpl


def test_sac_accessoire_omits_size_segment_when_absent():
    zpl = build_label_zpl(_sac_accessoire())
    assert "Sac à main cuir" in zpl
    # No size → category alone, no " • T."
    assert "Accessoires" in zpl
    assert "• T." not in zpl
    assert "5,00 €" in zpl


def test_label_contains_code128_barcode_field():
    zpl = build_label_zpl(_veste_femme_m())
    # ^BCN = Code 128 normal orientation
    assert "^BCN," in zpl
    # The barcode data appears after the ^BC command
    assert "^FDVTZ-2026-00142^FS" in zpl


def test_label_prints_shelf_and_markdown_dates():
    zpl = build_label_zpl(_veste_femme_m())
    assert "Rayon depuis : 14/05/2026" in zpl
    expected_markdown = (REF_SHELF + timedelta(days=30)).strftime("%d/%m/%Y")
    assert f"Démarque le : {expected_markdown}" in zpl


def test_label_falls_back_when_dates_missing():
    data = LabelData(
        product_name="Article sans date",
        category="Divers",
        size=None,
        condition=None,
        sale_price=3.0,
        barcode="VTZ-NODATE",
        shelf_date=None,
    )
    zpl = build_label_zpl(data)
    assert "Rayon depuis : —" in zpl
    assert "Démarque le : —" in zpl


def test_copies_propagate_to_pq_command():
    zpl = build_label_zpl(_veste_femme_m(), copies=3)
    assert "^PQ3" in zpl


def test_zero_or_negative_copies_clamped_to_one():
    assert "^PQ1" in build_label_zpl(_veste_femme_m(), copies=0)
    assert "^PQ1" in build_label_zpl(_veste_femme_m(), copies=-5)


def test_zpl_control_characters_in_name_are_neutralised():
    data = LabelData(
        product_name="Robe ^XA ~tilde \\back",
        category="Robes",
        size="S",
        condition="Bon",
        sale_price=15.0,
        barcode="VTZ-INJECT",
        shelf_date=REF_SHELF,
    )
    zpl = build_label_zpl(data)
    # Only the two structural markers ^XA / ^XZ should be present.
    assert zpl.count("^XA") == 1
    assert zpl.count("^XZ") == 1
    assert "Robe -XA -tilde /back" in zpl


def test_product_name_clamped_to_30_chars():
    data = LabelData(
        product_name="X" * 80,
        category="Long",
        size="M",
        condition="Bon",
        sale_price=4.0,
        barcode="VTZ-LONG",
        shelf_date=REF_SHELF,
    )
    zpl = build_label_zpl(data)
    # 29 X's + ellipsis
    assert "X" * 29 + "…" in zpl
    assert "X" * 31 not in zpl
