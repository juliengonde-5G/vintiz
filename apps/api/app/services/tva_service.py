"""Calcul TVA en régime normal France (CGI art. 256 et suivants).

Vintiz applique le **régime normal** (pas le régime de la marge sur biens
d'occasion, CGI art. 297 A — décision actée 2026-05). Conséquences pour
ce module :

- la base imposable est le prix de vente HT
- le taux par défaut est 20 % (taux normal France)
- chaque ligne de transaction stocke son `tva_rate` propre, figé au
  moment de la vente (cf. `models/pos.py:TransactionItem.tva_rate`)
- les tickets et factures doivent afficher la ventilation HT / TVA / TTC
  (à brancher dans le générateur de ticket — voir audit conformité §2.3)

Les `unit_price` du modèle `Product` et des lignes `TransactionItem` sont
exprimés **TTC** (UX boutique : la cliente voit le prix qu'elle paie). La
fonction de calcul fait donc le HT depuis le TTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


# Taux de TVA reconnus en France (référentiel BOI-TVA-LIQ-30-10-10) :
# - 20.00 — taux normal (vêtements adultes, accessoires, etc.)
# - 10.00 — taux intermédiaire (peu pertinent pour Vintiz)
# - 5.50  — taux réduit (livres, chaussures bébé < certains seuils)
# -  2.10 — taux super-réduit (presse, médicaments — hors scope Vintiz)
# -  0.00 — exonéré (vente B2B intracommunautaire — pas le cas standard)
SUPPORTED_TVA_RATES: tuple[Decimal, ...] = (
    Decimal("0.00"),
    Decimal("2.10"),
    Decimal("5.50"),
    Decimal("10.00"),
    Decimal("20.00"),
)

DEFAULT_TVA_RATE: Decimal = Decimal("20.00")


@dataclass(frozen=True)
class LineTotals:
    """Totaux d'une ligne de transaction au régime normal de TVA.

    Tous les montants sont arrondis au centime (2 décimales, demi-haut)
    pour cohérence avec les colonnes ``Numeric(10, 2)`` côté ORM.
    """

    line_ht: Decimal
    line_tva: Decimal
    line_ttc: Decimal
    tva_rate: Decimal


def _round_eur(value: Decimal) -> Decimal:
    """Arrondi commercial au centime — strictement le même que celui que
    PostgreSQL applique sur ``Numeric(10, 2)`` (banker's rounding non).
    """
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def is_supported_rate(rate: Decimal | float | int | str) -> bool:
    """Vérifie qu'un taux fait partie du référentiel français autorisé.

    Permissif en entrée pour faciliter la validation depuis l'admin
    (formulaire web qui envoie une string, ou JSON qui envoie un float).
    """
    try:
        normalized = Decimal(str(rate)).quantize(Decimal("0.01"))
    except Exception:
        return False
    return normalized in SUPPORTED_TVA_RATES


def compute_line_totals(
    unit_price_ttc: Decimal | float | int | str,
    quantity: int,
    discount_percent: Decimal | float | int | str = 0,
    tva_rate: Decimal | float | int | str = DEFAULT_TVA_RATE,
) -> LineTotals:
    """Calcule HT / TVA / TTC d'une ligne en régime normal.

    Args:
        unit_price_ttc : prix unitaire TTC (Decimal ou compatible).
        quantity       : quantité vendue (int positif).
        discount_percent : remise en pourcentage (0 à 100).
        tva_rate       : taux de TVA applicable (Decimal ou compatible).

    Le HT est dérivé du TTC, pas l'inverse :
        line_ttc = unit_price_ttc * quantity * (1 - discount/100)
        line_ht  = line_ttc / (1 + tva_rate/100)
        line_tva = line_ttc - line_ht

    Tous les résultats sont arrondis au centime.

    Raises:
        ValueError si quantity ≤ 0, discount hors [0, 100], ou tva_rate
        négatif.
    """
    qty = int(quantity)
    if qty <= 0:
        raise ValueError(f"quantity must be > 0 (got {quantity})")
    price_ttc = Decimal(str(unit_price_ttc))
    if price_ttc < 0:
        raise ValueError("unit_price_ttc must be ≥ 0")
    discount = Decimal(str(discount_percent))
    if discount < 0 or discount > 100:
        raise ValueError(
            f"discount_percent must be in [0, 100] (got {discount_percent})"
        )
    rate = Decimal(str(tva_rate))
    if rate < 0:
        raise ValueError(f"tva_rate must be ≥ 0 (got {tva_rate})")

    discount_factor = Decimal("1") - discount / Decimal("100")
    line_ttc_raw = price_ttc * qty * discount_factor

    rate_factor = Decimal("1") + rate / Decimal("100")
    if rate_factor == 0:
        # Anomalie défensive — un taux de -100 % n'a aucun sens fiscal
        raise ValueError("tva_rate would yield a zero divisor")

    # On arrondit d'abord le TTC (montant payé par la cliente, source de
    # vérité comptable), puis on dérive HT du TTC arrondi, puis TVA par
    # soustraction. Cette séquence garantit l'invariant `TTC = HT + TVA`
    # à 2 décimales — un arrondi indépendant de chaque montant peut
    # créer un écart d'1 centime non-conforme à NF525.
    line_ttc = _round_eur(line_ttc_raw)
    line_ht = _round_eur(line_ttc / rate_factor)
    line_tva = line_ttc - line_ht

    return LineTotals(
        line_ht=line_ht,
        line_tva=line_tva,
        line_ttc=line_ttc,
        tva_rate=rate.quantize(Decimal("0.01")),
    )


def aggregate_totals(lines: list[LineTotals]) -> LineTotals:
    """Agrège plusieurs lignes en un total transaction (multi-taux safe).

    Les totaux finaux sont la somme des lignes individuelles arrondies,
    pas la somme arrondie — cohérent avec la façon dont PostgreSQL
    accumule les ``Numeric(10, 2)``.

    Le ``tva_rate`` retourné est celui du panier *si toutes les lignes
    ont le même taux*, sinon ``Decimal("0.00")`` comme sentinelle "mixte".
    """
    if not lines:
        return LineTotals(
            line_ht=Decimal("0.00"),
            line_tva=Decimal("0.00"),
            line_ttc=Decimal("0.00"),
            tva_rate=DEFAULT_TVA_RATE,
        )
    total_ht = sum((ln.line_ht for ln in lines), Decimal("0.00"))
    total_tva = sum((ln.line_tva for ln in lines), Decimal("0.00"))
    total_ttc = sum((ln.line_ttc for ln in lines), Decimal("0.00"))
    rates = {ln.tva_rate for ln in lines}
    headline_rate = next(iter(rates)) if len(rates) == 1 else Decimal("0.00")
    return LineTotals(
        line_ht=_round_eur(total_ht),
        line_tva=_round_eur(total_tva),
        line_ttc=_round_eur(total_ttc),
        tva_rate=headline_rate,
    )
