"""Go-live reset — vidage des données opérationnelles AVANT l'ouverture 1.0.

À utiliser **une seule fois**, juste avant la mise en production officielle
(03/06/2026 — 10h00), pour repartir d'une base saine : on efface tout
l'historique de test/démo (ventes, clients, fidélité, clôtures de caisse,
exports fiscaux) **tout en conservant l'inventaire** (produits, photos,
embeddings, lots, catégories, zones, marques, fournisseurs).

⚠️  DIFFÉRENT de l'ancien ``purge_databases.py`` (supprimé) qui rasait AUSSI
le catalogue. Ici l'inventaire est **strictement préservé** — un garde-fou
vérifie en fin de transaction que le nombre de produits / catégories / zones
n'a pas bougé, et annule tout (ROLLBACK) sinon.

Données EFFACÉES :
  - Ventes        : payments, payment_attempts, transaction_items, receipts,
                    transactions
  - Caisse        : cash_movements, z_reports, cash_drawers
  - Fiscal (FEC)  : accounting_export_lines, accounting_exports
                    (la config comptable ``accounting_configs`` est conservée)
  - Fidélité/avoir: avoir_transactions, loyalty_transactions, loyalty_accounts
  - Bons/coupons  : coupons (bons cadeau d'ouverture, anniversaires, win-back…)
  - Clients       : magic_link_tokens, consents, customer_taste_profiles,
                    communication_logs, clients
  - Newsletter    : newsletter_subscribers
  - Analytique    : events_log (toutes les traces de test)

Données CONSERVÉES (inventaire + structure + config) :
  - Inventaire    : products, product_photos, product_embeddings,
                    intake_batches, zone_products
  - Structure     : categories, store_zones, zone_tags, furniture_items,
                    brand_tiers, price_grids, suppliers, orders, order_items
  - Config        : accounting_configs, message_templates, users
  - Réglages app  : data/app_config.json + data/hardware.json (fichiers)

Usage (en local) :
    PYTHONPATH=apps/api python scripts/go_live_reset.py --dry-run
    PYTHONPATH=apps/api python scripts/go_live_reset.py --confirm

En production (Docker) :
    docker exec -it vintiz-api python scripts/go_live_reset.py --dry-run
    docker exec -it vintiz-api python scripts/go_live_reset.py --confirm

Sans ``--confirm`` le script ne touche à rien. ``--dry-run`` imprime le plan.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Rendre ``import app.core.database`` fonctionnel en dev ET en Docker.
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
        "go_live_reset: impossible de localiser le package `app` — vérifié "
        f"{_HERE.parents[1] / 'apps' / 'api'} et {_HERE.parents[1]}"
    )

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine


# Ordre indicatif (feuilles → racines). Sur PostgreSQL on utilise
# ``TRUNCATE … CASCADE`` qui gère les FK automatiquement ; sur SQLite (tests)
# on retombe sur des ``DELETE`` ordonnés.
TABLES_TO_WIPE: list[str] = [
    # Fiscal (FEC généré) — avant z_reports (FK z_report_id)
    "accounting_export_lines",
    "accounting_exports",
    # Ventes
    "payments",
    "payment_attempts",
    "transaction_items",
    "receipts",
    "transactions",
    # Caisse + clôtures Z
    "cash_movements",
    "z_reports",
    "cash_drawers",
    # Fidélité / avoir
    "avoir_transactions",
    "loyalty_transactions",
    "loyalty_accounts",
    # Bons / coupons (tous nominatifs client)
    "coupons",
    # Clients + satellites
    "magic_link_tokens",
    "consents",
    "customer_taste_profiles",
    "communication_logs",
    "clients",
    # Contacts newsletter
    "newsletter_subscribers",
    # Analytique (traces de test ; entrelacée avec clients/transactions)
    "events_log",
]

# Tables INVENTAIRE / structure : un garde-fou vérifie qu'elles ne bougent pas.
INVENTORY_GUARD_TABLES: tuple[str, ...] = (
    "products",
    "product_photos",
    "product_embeddings",
    "intake_batches",
    "zone_products",
    "categories",
    "store_zones",
    "brand_tiers",
    "suppliers",
)


async def _existing_tables() -> set[str]:
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )


async def _count(db: AsyncSession, table: str) -> int:
    result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return int(result.scalar_one())


async def main(confirm: bool, dry_run: bool) -> int:
    if not confirm and not dry_run:
        print(
            "Refus de tourner sans --confirm. Relancez avec `--confirm` pour "
            "vider réellement, ou `--dry-run` pour n'imprimer que le plan."
        )
        return 2

    print("=" * 72)
    print(f"Vintiz GO-LIVE reset — mode: {'DRY-RUN' if dry_run else 'LIVE'}")
    print("  (efface l'historique opérationnel, CONSERVE l'inventaire)")
    print("=" * 72)

    existing = await _existing_tables()

    async with AsyncSession(engine) as db:
        # 1) Empreinte inventaire AVANT (garde-fou).
        inv_before: dict[str, int] = {}
        print("\n--- Inventaire & structure (doivent rester INCHANGÉS) ---")
        for t in INVENTORY_GUARD_TABLES:
            if t not in existing:
                print(f"  {t:28s}  (table absente — ignorée)")
                continue
            inv_before[t] = await _count(db, t)
            print(f"  {t:28s}  {inv_before[t]:>10,d} lignes conservées")

        # 2) Compter ce qu'on s'apprête à vider.
        print("\n--- Données opérationnelles à effacer ---")
        total_before = 0
        wipe_targets: list[str] = []
        for table in TABLES_TO_WIPE:
            if table not in existing:
                print(f"  {table:28s}  (table absente — ignorée)")
                continue
            before = await _count(db, table)
            total_before += before
            wipe_targets.append(table)
            verb = "à supprimer" if dry_run else "en file    "
            print(f"  {table:28s}  {verb} {before:>10,d} lignes")

        if dry_run:
            print(f"\nDRY-RUN : {total_before:,d} lignes seraient supprimées.")
            print("Inventaire préservé :", ", ".join(inv_before) or "(aucune table)")
            return 0

        # 3) Vidage atomique. PG : TRUNCATE … CASCADE ; SQLite : DELETE ordonné.
        dialect = engine.dialect.name
        if dialect == "postgresql":
            quoted = ", ".join(f'"{t}"' for t in wipe_targets)
            await db.execute(
                text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
            )
        else:
            for table in reversed(wipe_targets):
                await db.execute(text(f"DELETE FROM {table}"))

        # 4) GARDE-FOU : l'inventaire n'a pas bougé ? Sinon ROLLBACK + abort.
        inv_changed: list[str] = []
        for t, before in inv_before.items():
            after = await _count(db, t)
            if after != before:
                inv_changed.append(f"{t} ({before:,d} → {after:,d})")
        if inv_changed:
            await db.rollback()
            print("\n" + "!" * 72)
            print("ABANDON : l'inventaire a été impacté — ROLLBACK effectué.")
            for line in inv_changed:
                print(f"  ⚠ {line}")
            print("Aucune donnée n'a été supprimée. Vérifiez les FK CASCADE.")
            print("!" * 72)
            return 1

        await db.commit()

        # 5) Vérifier que tout est bien à zéro.
        total_after = 0
        for t in wipe_targets:
            total_after += await _count(db, t)

    print("\n" + "=" * 72)
    print(
        f"Reset terminé : {total_before:,d} lignes supprimées sur "
        f"{len(wipe_targets)} tables ({total_after:,d} restantes — doit être 0)."
    )
    print("Inventaire intact ✓  — la boutique peut ouvrir en 1.0.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Vidage one-shot pré-ouverture (conserve l'inventaire)."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Supprime réellement. Sans ce flag, le script ne fait rien.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Imprime le plan sans rien modifier.",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(confirm=args.confirm, dry_run=args.dry_run)))
