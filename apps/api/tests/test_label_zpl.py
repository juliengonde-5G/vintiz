"""Tests unitaires pour le générateur ZPL Vintiz (25×52 mm, deux étiquettes).

Étiquette 1 (info) : code-barres Code 128, réf, nom du produit, semaine.
Étiquette 2 (prix) : logo VINTIZ, prix de vente.

Les tests s'appuient sur des LabelData purs — aucune base de données.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.zebra_zpl import (
    LABEL_HEIGHT_DOTS,
    LABEL_WIDTH_DOTS,
    LabelData,
    build_info_label_zpl,
    build_label_set_zpl,
    build_label_zpl,
    build_price_label_zpl,
)

REF_SHELF = datetime(2026, 5, 14, tzinfo=timezone.utc)


def _veste() -> LabelData:
    return LabelData(
        product_name="Veste en jean délavée",
        category="Vestes",
        size="M",
        condition="Très bon état",
        sale_price=12.5,
        barcode="VTZ-2026-00142",
        shelf_date=REF_SHELF,
    )


def _jean() -> LabelData:
    return LabelData(
        product_name="Jean droit Levi's 501",
        category="Pantalons",
        size="L",
        condition="Bon état",
        sale_price=8.0,
        barcode="VTZ-2026-00211",
        shelf_date=REF_SHELF,
    )


# ---------------------------------------------------------------------------
# build_label_zpl / build_label_set_zpl — deux blocs
# ---------------------------------------------------------------------------


def test_build_label_zpl_contains_two_blocks():
    zpl = build_label_zpl(_veste())
    assert zpl.count("^XA") == 2
    assert zpl.count("^XZ") == 2


def test_build_label_set_zpl_is_alias():
    assert build_label_set_zpl(_veste()) == build_label_zpl(_veste())


def test_build_label_zpl_info_first_then_price():
    zpl = build_label_zpl(_veste())
    idx_info = zpl.index("VTZ-2026-00142")
    idx_price = zpl.index("12,50")
    assert idx_info < idx_price


# ---------------------------------------------------------------------------
# Étiquette 1 — Info
# ---------------------------------------------------------------------------


def test_info_label_structure():
    zpl = build_info_label_zpl(_veste())
    assert zpl.startswith("^XA")
    assert zpl.endswith("^XZ")
    assert "^CI28" in zpl
    assert f"^PW{LABEL_WIDTH_DOTS}" in zpl
    assert f"^LL{LABEL_HEIGHT_DOTS}" in zpl
    assert "^POI" in zpl


def test_info_label_contains_barcode_code128():
    assert "^BCR," in build_info_label_zpl(_veste())


def test_info_label_contains_reference():
    assert "VTZ-2026-00142" in build_info_label_zpl(_veste())


def test_info_label_contains_product_name():
    assert "Veste en jean" in build_info_label_zpl(_veste())


def test_info_label_does_not_contain_category():
    assert "Vestes" not in build_info_label_zpl(_veste())


def test_info_label_shows_week_from_shelf_date():
    zpl = build_info_label_zpl(_veste())
    week = REF_SHELF.isocalendar()[1]
    assert f"Semaine {week:02d}" in zpl


def test_info_label_explicit_week_takes_precedence():
    data = LabelData(
        product_name="Robe", category="Robes", size="S", condition="Bon état",
        sale_price=15.0, barcode="VTZ-2026-00999", shelf_date=REF_SHELF, week_number=3,
    )
    assert "Semaine 03" in build_info_label_zpl(data)


def test_info_label_no_week_fallback():
    data = LabelData(
        product_name="Pull", category="Pulls", size="M", condition=None,
        sale_price=10.0, barcode="VTZ-X", shelf_date=None,
    )
    assert "Semaine --" in build_info_label_zpl(data)


def test_info_label_copies_in_pq():
    assert "^PQ3" in build_info_label_zpl(_jean(), copies=3)


def test_info_label_copies_clamped():
    assert "^PQ1" in build_info_label_zpl(_veste(), copies=0)
    assert "^PQ1" in build_info_label_zpl(_veste(), copies=-2)


def test_info_label_zpl_chars_in_name_sanitized():
    data = LabelData(
        product_name="Robe ^XA ~test \\slash",
        category="Robes", size=None, condition=None,
        sale_price=20.0, barcode="VTZ-2026-00500", shelf_date=REF_SHELF,
    )
    zpl = build_info_label_zpl(data)
    assert zpl.count("^XA") == 1
    assert zpl.count("^XZ") == 1
    assert "Robe -XA -test /slash" in zpl


def test_info_label_name_clamped():
    data = LabelData(
        product_name="A" * 60, category="X", size=None, condition=None,
        sale_price=5.0, barcode="VTZ-Y", shelf_date=None,
    )
    zpl = build_info_label_zpl(data)
    assert "A" * 29 not in zpl
    assert "…" in zpl


# ---------------------------------------------------------------------------
# Étiquette 2 — Prix
# ---------------------------------------------------------------------------


def test_price_label_structure():
    zpl = build_price_label_zpl(_veste())
    assert zpl.startswith("^XA")
    assert zpl.endswith("^XZ")
    assert "^CI28" in zpl
    assert "^POI" in zpl


def test_price_label_contains_vintiz():
    assert "VINTIZ" in build_price_label_zpl(_veste())


def test_price_label_formats_price_french():
    zpl = build_price_label_zpl(_veste())
    assert "12,50" in zpl
    assert "€" in zpl


def test_price_label_zero_price():
    data = LabelData(
        product_name="Cadeau", category="Divers", size=None, condition=None,
        sale_price=0.0, barcode="VTZ-0", shelf_date=None,
    )
    assert "0,00" in build_price_label_zpl(data)


def test_price_label_copies_in_pq():
    assert "^PQ2" in build_price_label_zpl(_jean(), copies=2)


def test_price_label_has_separator():
    assert "^GB" in build_price_label_zpl(_veste())
