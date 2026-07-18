#!/usr/bin/env python3
"""One-shot : passe tous les produits « En stock » (status=stock) en
« En magasin » (status=displayed, label UI « En rayon »).

Le changement passe par ProductLifecycleService.transition() — la même voie
que l'UI — pour que chaque produit garde un cycle de vie propre :
  - validation FSM (stock → displayed est une transition autorisée),
  - tampon ``displayed_at`` posé à la 1ʳᵉ mise en rayon,
  - ligne d'historique dans ``product_location_events``,
  - AuditLog automatique via le listener.

Usage :
    # Aperçu (n'écrit rien)
    PYTHONPATH=apps/api python scripts/move_stock_to_display.py --dry-run

    # Exécution réelle
    PYTHONPATH=apps/api python scripts/move_stock_to_display.py --confirm

    # En prod (conteneur Docker)
    docker exec -it vintiz-api python scripts/move_stock_to_display.py --confirm
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
        "move_stock_to_display: package `app` introuvable — vérifié "
        f"{_HERE.parents[1] / 'apps' / 'api'} et {_HERE.parents[1]}"
    )

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session  # noqa: E402
from app.models.product import Product, ProductStatus  # noqa: E402
from app.services.product_lifecycle import ProductLifecycleService  # noqa: E402


async def run(dry_run: bool) -> None:
    async with async_session() as db:
        products = (
            (
                await db.execute(
                    select(Product)
                    .where(Product.status == ProductStatus.stock)
                    .order_by(Product.created_at)
                )
            )
            .scalars()
            .all()
        )

        if not products:
            print("Aucun produit avec le statut 'stock' — rien à faire.")
            return

        print(f"{len(products)} produit(s) 'En stock' → 'En magasin' (displayed)")
        for p in products:
            print(f"  - {p.barcode}  {p.name}")

        if dry_run:
            print("\n[DRY-RUN] Aucune écriture. Relancer avec --confirm pour appliquer.")
            return

        lifecycle = ProductLifecycleService(db)
        for p in products:
            await lifecycle.transition(
                p,
                ProductStatus.displayed,
                reason="Passage en masse stock → magasin (script move_stock_to_display)",
                move_source="script",
            )
        await db.commit()
        print(f"\nOK — {len(products)} produit(s) passé(s) au statut 'displayed'.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Passe tous les produits 'stock' au statut 'displayed' (En magasin)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Aperçu sans écriture")
    group.add_argument("--confirm", action="store_true", help="Exécute réellement")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
