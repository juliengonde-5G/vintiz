#!/usr/bin/env python3
"""Restaure les pièces sorties par la « sortie automatique 6 semaines ».

Contexte : le cron/trigger ``thursday_six_weeks_exit`` (désactivé le
2026-07-18) a basculé en base des pièces ≥ 6 semaines de rayon vers le statut
``returned_to_sorting`` — SANS retrait physique. Ces pièces sont toujours sur
les portants mais invendables (statut terminal) : scans refusés en caisse
après encaissement CB = ventes orphelines.

Ce script remet en rayon les victimes : produits ENCORE au statut
``returned_to_sorting`` dont un mouvement porte le motif exact de la sortie
automatique. Restauration : statut → ``displayed`` + zone d'origine
(``from_zone_id`` du mouvement de sortie), mouvement historisé.

Le statut est réassigné directement (pas via ProductLifecycleService) :
``returned_to_sorting`` est terminal dans la FSM, il n'existe volontairement
aucune transition sortante — ce script EST le correctif d'exception, audité
via le mouvement + l'AuditLog du listener.

Les pièces déjà retraitées par l'équipe (statut passé à ``returned`` etc.)
ne sont PAS touchées.

Usage :
    # Aperçu (n'écrit rien)
    PYTHONPATH=apps/api python scripts/restore_six_weeks_exit.py --dry-run

    # Exécution réelle
    PYTHONPATH=apps/api python scripts/restore_six_weeks_exit.py --confirm

    # En prod
    docker exec -it vintiz-api python scripts/restore_six_weeks_exit.py --confirm
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
        "restore_six_weeks_exit: package `app` introuvable — vérifié "
        f"{_HERE.parents[1] / 'apps' / 'api'} et {_HERE.parents[1]}"
    )

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session  # noqa: E402
from app.models.product import Product, ProductStatus  # noqa: E402
from app.models.product_location import ProductLocationEvent  # noqa: E402
from app.models.store import StoreZone  # noqa: E402

# Motif exact écrit par run_thursday_six_weeks_exit (services/checklist.py).
AUTO_EXIT_REASON = "6 weeks on shelf — automatic Thursday exit"
RESTORE_REASON = (
    "Restauration — annulation de la sortie automatique 6 semaines "
    "(pièce restée physiquement en rayon)"
)


async def run(dry_run: bool) -> None:
    async with async_session() as db:
        # Dernier mouvement de sortie automatique par produit.
        events = (
            (
                await db.execute(
                    select(ProductLocationEvent)
                    .where(ProductLocationEvent.reason == AUTO_EXIT_REASON)
                    .order_by(ProductLocationEvent.occurred_at.asc())
                )
            )
            .scalars()
            .all()
        )
        if not events:
            print("Aucun mouvement « sortie automatique 6 semaines » trouvé.")
            return
        last_exit: dict = {}
        for ev in events:
            last_exit[ev.product_id] = ev  # ordre asc → le dernier gagne

        products = (
            (
                await db.execute(
                    select(Product).where(Product.id.in_(list(last_exit)))
                )
            )
            .scalars()
            .all()
        )
        victims = [p for p in products if p.status == ProductStatus.returned_to_sorting]
        already_handled = len(products) - len(victims)

        zone_names: dict = {}
        zone_ids = {last_exit[p.id].from_zone_id for p in victims if last_exit[p.id].from_zone_id}
        if zone_ids:
            for zid, zname in (
                await db.execute(
                    select(StoreZone.id, StoreZone.name).where(StoreZone.id.in_(zone_ids))
                )
            ).all():
                zone_names[zid] = zname

        print(
            f"{len(last_exit)} pièce(s) sortie(s) automatiquement · "
            f"{already_handled} déjà retraitée(s) par l'équipe (non touchées) · "
            f"{len(victims)} à restaurer :\n"
        )
        for p in victims:
            ev = last_exit[p.id]
            zone = zone_names.get(ev.from_zone_id, "— sans zone —")
            when = ev.occurred_at.strftime("%d/%m/%Y") if ev.occurred_at else "?"
            print(
                f"  - {p.barcode}  {p.name}  ({float(p.sale_price):.2f} €)  "
                f"sortie le {when} → retour en rayon, zone « {zone} »"
            )

        if not victims:
            print("Rien à restaurer.")
            return
        if dry_run:
            print("\n[DRY-RUN] Aucune écriture. Relancer avec --confirm pour appliquer.")
            return

        from app.services.stock_movement import record_move

        for p in victims:
            ev = last_exit[p.id]
            before_status, before_zone = p.status, p.zone_id
            p.status = ProductStatus.displayed
            p.zone_id = ev.from_zone_id
            await db.flush()
            await record_move(
                db,
                p,
                from_status=before_status,
                to_status=p.status,
                from_zone_id=before_zone,
                to_zone_id=p.zone_id,
                user_id=None,
                reason=RESTORE_REASON,
                source="script",
            )
        await db.commit()
        print(f"\nOK — {len(victims)} pièce(s) restaurée(s) en rayon (displayed).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restaure les pièces victimes de la sortie automatique 6 semaines"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Aperçu sans écriture")
    group.add_argument("--confirm", action="store_true", help="Exécute réellement")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
