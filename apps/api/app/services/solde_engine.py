"""Moteur Solde — remise multi-articles automatique appliquée en caisse.

Règle métier (validée boutique) :

- On raisonne sur le nombre d'**articles** du panier (pièces d'inventaire,
  chaque pièce de seconde main est unique → quantité 1).
- On découpe le panier en **paquets de 6** : dans chaque paquet, les **3 pièces
  les moins chères** sont remisées à **-50 %**.
- Le **reste** (< 6) est découpé en **paires** : dans chaque paire, la pièce la
  moins chère est remisée à **-30 %**.
- Une pièce orpheline (panier impair, hors paire) n'est pas remisée.

La remise vise toujours les pièces **les moins chères**, et le meilleur taux
(-50 %) va aux pièces les moins chères en premier.

Exemples :
  2 articles → 1 moins chère à -30 %
  3 articles → 1 moins chère à -30 % (la 3ᵉ pleine)
  4 articles → 2 moins chères à -30 %
  6 articles → 3 moins chères à -50 %
  8 articles → 3 moins chères à -50 % + 1 à -30 %
  12 articles → 6 moins chères à -50 %

Le moteur ne mute jamais les produits : il renvoie un taux de remise opération
par article (0.0 / 0.30 / 0.50). Le POS l'applique à la ligne de vente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.offer import Offer, OfferType


# Taux par défaut — surchargeables via Offer.config (clés ``pair_pct`` / ``six_pct``).
DEFAULT_PAIR_PCT = 30.0   # paire → la moins chère à -30 %
DEFAULT_SIX_PCT = 50.0    # paquet de 6 → les 3 moins chères à -50 %


@dataclass
class SoldeConfig:
    pair_pct: float = DEFAULT_PAIR_PCT
    six_pct: float = DEFAULT_SIX_PCT


def solde_config_from_offer(offer: Offer | None) -> SoldeConfig:
    cfg = (offer.config or {}) if offer is not None else {}
    try:
        pair = float(cfg.get("pair_pct", DEFAULT_PAIR_PCT))
    except (TypeError, ValueError):
        pair = DEFAULT_PAIR_PCT
    try:
        six = float(cfg.get("six_pct", DEFAULT_SIX_PCT))
    except (TypeError, ValueError):
        six = DEFAULT_SIX_PCT
    # Garde-fous : remise dans [0, 100].
    pair = min(100.0, max(0.0, pair))
    six = min(100.0, max(0.0, six))
    return SoldeConfig(pair_pct=pair, six_pct=six)


def compute_solde_rates(
    unit_prices: list[float], config: SoldeConfig | None = None
) -> list[float]:
    """Taux de remise Solde (en %) par article, indexé comme ``unit_prices``.

    Chaque entrée de ``unit_prices`` est le prix d'**une** pièce (après remise
    manuelle éventuelle). Retourne une liste de même longueur : 0.0, ``pair_pct``
    ou ``six_pct`` selon que la pièce tombe dans un paquet de 6 ou une paire.
    """
    cfg = config or SoldeConfig()
    n = len(unit_prices)
    rates = [0.0] * n
    if n < 2:
        return rates

    # Nombre de pièces remisées : 3 par paquet de 6, +1 par paire restante.
    six_count = (n // 6) * 3
    remainder = n % 6
    pair_count = remainder // 2

    # Les pièces les moins chères d'abord ; le meilleur taux (-50 %) va aux
    # toutes premières.
    order = sorted(range(n), key=lambda i: unit_prices[i])
    for i in order[:six_count]:
        rates[i] = cfg.six_pct
    for i in order[six_count:six_count + pair_count]:
        rates[i] = cfg.pair_pct
    return rates


async def get_active_solde(
    db: AsyncSession, now: datetime | None = None
) -> Offer | None:
    """Retourne l'opération Solde active (dans sa fenêtre de dates), ou None.

    En cas de plusieurs soldes actives, on prend la plus prioritaire
    (``priority`` la plus basse).
    """
    now = now or datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(Offer)
            .where(Offer.active.is_(True), Offer.type == OfferType.solde)
            .order_by(Offer.priority.asc())
        )
    ).scalars().all()
    for offer in rows:
        vf = offer.valid_from
        vu = offer.valid_until
        if vf is not None and vf.tzinfo is None:
            vf = vf.replace(tzinfo=timezone.utc)
        if vu is not None and vu.tzinfo is None:
            vu = vu.replace(tzinfo=timezone.utc)
        if vf is not None and vf > now:
            continue
        if vu is not None and vu < now:
            continue
        return offer
    return None


@dataclass
class SoldeLine:
    index: int
    unit_price: float           # prix unitaire après remise manuelle
    solde_pct: float            # remise opération en % (0 / 30 / 50)
    line_total: float           # total ligne après remise opération
    discounted: bool


@dataclass
class SoldeEvaluation:
    active: bool
    name: str
    valid_from: str | None
    valid_until: str | None
    lines: list[SoldeLine]
    total_before: float         # total après remises manuelles, avant solde
    total_discount: float       # remise solde totale
    total_after: float          # total à encaisser


def evaluate_lines(
    unit_prices: list[float], offer: Offer | None
) -> SoldeEvaluation:
    """Évalue la remise Solde sur une liste de prix unitaires (1 pièce chacun).

    ``unit_prices`` = prix unitaires après remise manuelle. Utilisé à la fois
    par l'aperçu POS et par la création de vente — source unique de vérité.
    """
    cfg = solde_config_from_offer(offer)
    rates = compute_solde_rates(unit_prices, cfg)
    lines: list[SoldeLine] = []
    total_before = 0.0
    total_after = 0.0
    for idx, price in enumerate(unit_prices):
        rate = rates[idx]
        line_total = round(price * (1.0 - rate / 100.0), 2)
        total_before += round(price, 2)
        total_after += line_total
        lines.append(
            SoldeLine(
                index=idx,
                unit_price=round(price, 2),
                solde_pct=rate,
                line_total=line_total,
                discounted=rate > 0,
            )
        )
    total_before = round(total_before, 2)
    total_after = round(total_after, 2)
    return SoldeEvaluation(
        active=offer is not None,
        name=(offer.name if offer is not None else ""),
        valid_from=(
            offer.valid_from.isoformat()
            if offer is not None and offer.valid_from else None
        ),
        valid_until=(
            offer.valid_until.isoformat()
            if offer is not None and offer.valid_until else None
        ),
        lines=lines,
        total_before=total_before,
        total_discount=round(total_before - total_after, 2),
        total_after=total_after,
    )
