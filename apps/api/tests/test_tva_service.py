"""Tests pour le service TVA en régime normal France.

Vérifie :
- les taux supportés (référentiel BOI-TVA-LIQ-30-10-10)
- le calcul HT / TVA / TTC à partir d'un prix TTC unitaire
- la remise en pourcentage
- les multiplicités (quantity > 1)
- l'agrégation multi-lignes (mono-taux et mixte)
- les arrondis au centime
- les erreurs d'entrée (quantity ≤ 0, discount hors [0, 100], tva_rate < 0)
"""

from decimal import Decimal

import pytest

from app.services.tva_service import (
    DEFAULT_TVA_RATE,
    SUPPORTED_TVA_RATES,
    LineTotals,
    aggregate_totals,
    compute_line_totals,
    is_supported_rate,
)


# -- referentiel ----------------------------------------------------


def test_default_rate_is_20():
    assert DEFAULT_TVA_RATE == Decimal("20.00")


def test_supported_rates_contains_french_set():
    expected = {
        Decimal("0.00"),
        Decimal("2.10"),
        Decimal("5.50"),
        Decimal("10.00"),
        Decimal("20.00"),
    }
    assert set(SUPPORTED_TVA_RATES) == expected


@pytest.mark.parametrize("rate,expected", [
    (20, True),
    (20.0, True),
    ("20", True),
    ("20.00", True),
    (Decimal("5.5"), True),
    (Decimal("5.50"), True),
    (10, True),
    (2.1, True),
    (0, True),
    (15, False),
    (25, False),
    ("not a number", False),
    (None, False),
])
def test_is_supported_rate(rate, expected):
    assert is_supported_rate(rate) is expected


# -- compute_line_totals — basic ------------------------------------


def test_simple_20_percent_default_rate():
    """Robe à 100 € TTC, 1 unité, sans remise — TVA 20 % par défaut."""
    out = compute_line_totals(Decimal("100.00"), 1)
    assert out.line_ttc == Decimal("100.00")
    assert out.line_ht == Decimal("83.33")
    assert out.line_tva == Decimal("16.67")
    assert out.tva_rate == Decimal("20.00")


def test_quantity_multiplies_correctly():
    """3 articles à 50 € TTC chacun = 150 € TTC total."""
    out = compute_line_totals(Decimal("50.00"), 3)
    assert out.line_ttc == Decimal("150.00")
    assert out.line_ht == Decimal("125.00")
    assert out.line_tva == Decimal("25.00")


def test_discount_10_percent():
    """Robe 100 € TTC avec -10 % → 90 € TTC."""
    out = compute_line_totals(Decimal("100.00"), 1, discount_percent=10)
    assert out.line_ttc == Decimal("90.00")
    assert out.line_ht == Decimal("75.00")
    assert out.line_tva == Decimal("15.00")


def test_discount_zero_is_neutral():
    out = compute_line_totals(Decimal("100.00"), 1, discount_percent=0)
    assert out.line_ttc == Decimal("100.00")


def test_discount_100_yields_zero():
    """Article offert (-100 %) → tout à 0."""
    out = compute_line_totals(Decimal("100.00"), 1, discount_percent=100)
    assert out.line_ttc == Decimal("0.00")
    assert out.line_ht == Decimal("0.00")
    assert out.line_tva == Decimal("0.00")


# -- compute_line_totals — alternative rates ------------------------


def test_reduced_rate_5_5_books():
    """Livre à 21.10 € TTC, taux 5.5 %."""
    out = compute_line_totals(
        Decimal("21.10"), 1, tva_rate=Decimal("5.50")
    )
    assert out.line_ttc == Decimal("21.10")
    # 21.10 / 1.055 = 20.0000 → 20.00
    assert out.line_ht == Decimal("20.00")
    assert out.line_tva == Decimal("1.10")
    assert out.tva_rate == Decimal("5.50")


def test_intermediate_rate_10():
    out = compute_line_totals(Decimal("11.00"), 1, tva_rate=10)
    assert out.line_ttc == Decimal("11.00")
    assert out.line_ht == Decimal("10.00")
    assert out.line_tva == Decimal("1.00")


def test_zero_rate_b2b_intracom():
    """Vente B2B intracom — TVA 0 → HT == TTC."""
    out = compute_line_totals(Decimal("100.00"), 1, tva_rate=0)
    assert out.line_ttc == Decimal("100.00")
    assert out.line_ht == Decimal("100.00")
    assert out.line_tva == Decimal("0.00")


# -- arrondis --------------------------------------------------------


def test_rounding_half_up_preserves_invariant():
    """29.99 € TTC à 20 % → HT 24.99 + TVA 5.00 = TTC 29.99.

    Le calcul brut donnerait HT=24.9917 et TVA=4.9983. La soustraction
    `line_tva = line_ttc - line_ht` après arrondi HT garantit que
    HT + TVA = TTC à 2 décimales (cohérent avec NF525).
    """
    out = compute_line_totals(Decimal("29.99"), 1)
    assert out.line_ttc == Decimal("29.99")
    assert out.line_ht == Decimal("24.99")
    assert out.line_tva == Decimal("5.00")
    assert out.line_ht + out.line_tva == out.line_ttc


def test_rounding_9_99():
    """9.99 € TTC à 20 % → HT 8.33 + TVA 1.66 = TTC 9.99.

    Sans le fix de soustraction, on obtenait HT=8.33 + TVA=1.67 = 10.00
    (off by 0.01) — bug d'arrondi indépendant non-conforme.
    """
    out = compute_line_totals(Decimal("9.99"), 1)
    assert out.line_ttc == Decimal("9.99")
    assert out.line_ht == Decimal("8.33")
    assert out.line_tva == Decimal("1.66")
    assert out.line_ht + out.line_tva == out.line_ttc


def test_consistency_ttc_equals_ht_plus_tva():
    """Invariant comptable : TTC = HT + TVA arrondis."""
    cases = [
        (Decimal("9.99"), 1, 0, 20),
        (Decimal("33.33"), 2, 5, 20),
        (Decimal("100.00"), 1, 0, 5.5),
        (Decimal("17.50"), 4, 15, 10),
    ]
    for price, qty, disc, rate in cases:
        out = compute_line_totals(price, qty, disc, rate)
        assert out.line_ht + out.line_tva == out.line_ttc, (
            f"Invariant cassé : {out.line_ht} + {out.line_tva} ≠ {out.line_ttc}"
        )


# -- input validation ----------------------------------------------


def test_quantity_zero_raises():
    with pytest.raises(ValueError, match="quantity must be > 0"):
        compute_line_totals(Decimal("100.00"), 0)


def test_quantity_negative_raises():
    with pytest.raises(ValueError):
        compute_line_totals(Decimal("100.00"), -1)


def test_negative_price_raises():
    with pytest.raises(ValueError, match="unit_price_ttc"):
        compute_line_totals(Decimal("-1.00"), 1)


def test_discount_above_100_raises():
    with pytest.raises(ValueError, match="discount_percent"):
        compute_line_totals(Decimal("100.00"), 1, discount_percent=101)


def test_discount_negative_raises():
    with pytest.raises(ValueError, match="discount_percent"):
        compute_line_totals(Decimal("100.00"), 1, discount_percent=-1)


def test_negative_tva_rate_raises():
    with pytest.raises(ValueError, match="tva_rate"):
        compute_line_totals(Decimal("100.00"), 1, tva_rate=-1)


# -- aggregate_totals ----------------------------------------------


def test_aggregate_empty_returns_zeros():
    out = aggregate_totals([])
    assert out.line_ht == Decimal("0.00")
    assert out.line_tva == Decimal("0.00")
    assert out.line_ttc == Decimal("0.00")
    assert out.tva_rate == DEFAULT_TVA_RATE


def test_aggregate_single_rate_keeps_rate():
    """Toutes les lignes au taux normal → headline_rate = 20."""
    lines = [
        compute_line_totals(Decimal("100.00"), 1),
        compute_line_totals(Decimal("50.00"), 2),
    ]
    out = aggregate_totals(lines)
    assert out.line_ttc == Decimal("200.00")
    # Somme des HT par ligne (83.33 + 125.00) = 208.33 hors prix qty,
    # mais ici 100€ + 50*3=150€ → TTC 250 ; les 2 lignes ci-dessus :
    # 100 (HT 83.33 TVA 16.67) + 100 (HT 83.33 TVA 16.67 — qty=2 × 50) ;
    # somme HT = 166.66, TVA = 33.34, TTC = 200.
    assert out.line_ht == Decimal("166.66")
    assert out.line_tva == Decimal("33.34")
    assert out.tva_rate == Decimal("20.00")


def test_aggregate_mixed_rates_returns_zero_sentinel():
    """Multi-taux → tva_rate = 0.00 (sentinelle 'mixte')."""
    lines = [
        compute_line_totals(Decimal("100.00"), 1, tva_rate=20),
        compute_line_totals(Decimal("21.10"), 1, tva_rate=Decimal("5.50")),
    ]
    out = aggregate_totals(lines)
    assert out.line_ttc == Decimal("121.10")
    # Headline rate sentinelle
    assert out.tva_rate == Decimal("0.00")


def test_aggregate_preserves_invariant():
    lines = [
        compute_line_totals(Decimal("33.33"), 1),
        compute_line_totals(Decimal("19.99"), 2, discount_percent=5),
        compute_line_totals(Decimal("21.10"), 1, tva_rate=Decimal("5.50")),
    ]
    out = aggregate_totals(lines)
    # Le TTC global devrait être la somme des TTC ligne par ligne.
    expected_ttc = sum((ln.line_ttc for ln in lines), Decimal("0.00"))
    assert out.line_ttc == expected_ttc.quantize(Decimal("0.01"))
