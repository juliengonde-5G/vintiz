#!/usr/bin/env python3
"""Retrouve les pièces encore EN RAYON dont le prix mène à un montant donné.

Cas d'usage : un encaissement CB orphelin (paiement pris, vente non validée)
n'a laissé aucun ``transaction_item`` — le seul chiffre fiable est le montant
payé. L'article n'ayant jamais été marqué ``sold``, il est TOUJOURS en rayon.
Ce script liste les candidats dont ``sale_price`` retombe sur le montant, soit
directement, soit après une remise standard :
  - chips manuelles POS : 5, 10, 15, 20, 30 %
  - Solde (solde_engine)  : -30 % (paire) ou -50 % (paquet de 6)

Read-only. Ne modifie rien.

Usage :
    PYTHONPATH=apps/api python scripts/find_price_candidates.py --amount 11.20
    docker exec -it vintiz-api python scripts/find_price_candidates.py --amount 11.20
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Rendre ``import app.core...`` fonctionnel en dev ET en Docker (/app).
_HERE = Path(__file__).resolve()
for _candidate in (
    _HERE.parents[1] / "apps" / "api",   # layout dev (repo)
    _HERE.parents[1],                    # layout Docker prod (/app)
):
    if (_candidate / "app" / "core" / "database.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    raise SystemExit(
        "find_price_candidates: package `app` introuvable — vérifié "
        f"{_HERE.parents[1] / 'apps' / 'api'} et {_HERE.parents[1]}"
    )

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.database import async_session  # noqa: E402
from app.models.product import Product, ProductStatus  # noqa: E402

# Statuts « encore en rayon » (l'article orphelin n'a jamais été vendu).
FLOOR_STATUSES = [
    ProductStatus.display,
    ProductStatus.displayed,
    ProductStatus.discounted,
    ProductStatus.deep_discounted,
    ProductStatus.stock,   # inclus au cas où la pièce n'a pas encore été mise en rayon
    ProductStatus.tagged,
]

# Remises standard testées (label, taux %). 0 = prix plein.
DISCOUNT_RATES: list[tuple[str, float]] = [
    ("prix plein", 0.0),
    ("chip -5 %", 5.0),
    ("chip -10 %", 10.0),
    ("chip -15 %", 15.0),
    ("chip -20 %", 20.0),
    ("chip -30 % / Solde paire", 30.0),
    ("Solde -50 % (paquet de 6)", 50.0),
]

TOL = 0.01  # tolérance de 1 centime


async def run(amount: float) -> None:
    print(f"Recherche des pièces en rayon menant à {amount:.2f} €\n")

    async with async_session() as db:
        products = (
            (
                await db.execute(
                    select(Product)
                    .options(selectinload(Product.category))
                    .where(Product.status.in_(FLOOR_STATUSES))
                    .order_by(Product.sale_price)
                )
            )
            .scalars()
            .all()
        )

    matches: list[tuple[Product, str, float]] = []
    for p in products:
        price = float(p.sale_price)
        for label, rate in DISCOUNT_RATES:
            discounted = round(price * (1 - rate / 100.0), 2)
            if abs(discounted - amount) <= TOL:
                matches.append((p, label, discounted))
                break  # un seul motif par pièce suffit

    if not matches:
        print(
            f"Aucune pièce en rayon ne retombe sur {amount:.2f} € "
            "(prix direct ou remise standard)."
            "\n→ Le panier était peut-être multi-articles, ou l'article a un "
            "prix atypique. Recoupez avec les logs d'accès (by-barcode)."
        )
        return

    print(f"{len(matches)} candidat(s) :\n")
    print(f"{'CODE-BARRES':<20} {'PRIX':>7} {'→ PAYÉ':>8}  {'STATUT':<14} MOTIF / NOM")
    print("─" * 100)
    for p, label, discounted in matches:
        cat = p.category.name if p.category else "?"
        disp = p.displayed_at.strftime("%d/%m %H:%M") if p.displayed_at else "—"
        print(
            f"{p.barcode:<20} {float(p.sale_price):>7.2f} {discounted:>8.2f}  "
            f"{p.status.value:<14} {label}"
        )
        print(
            f"{'':<20} {'':>7} {'':>8}  {'':<14} "
            f"« {p.name} » · {cat}"
            + (f" · {p.brand}" if p.brand else "")
            + (f" · T.{p.size}" if p.size else "")
            + f" · en rayon depuis {disp}"
        )
    print("─" * 100)
    print(
        "\nRappel : l'article de la vente orpheline est celui de cette liste "
        "qui n'aurait PAS dû rester en rayon (la caissière / la cliente "
        "Cécile Groult peut confirmer). Croisez avec les scans by-barcode des "
        "logs d'accès autour de 09:30 UTC pour lever toute ambiguïté."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Liste les pièces en rayon menant à un montant payé (read-only)"
    )
    parser.add_argument(
        "--amount", type=float, default=11.20,
        help="Montant payé à retrouver (défaut : 11.20)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.amount))


if __name__ == "__main__":
    main()
