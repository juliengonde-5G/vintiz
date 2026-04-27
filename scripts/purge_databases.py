"""One-shot data purge for Vintiz.

Wipes operational data (clients / products / transactions and their
satellites) while preserving structural rows: users, categories, price grids,
store zones, brand tiers, app settings.

Usage:
    PYTHONPATH=apps/api python scripts/purge_databases.py --confirm

The script refuses to run without --confirm. It prints the row count for each
table before and after the purge so the operator can audit what happened.

Tables wiped (in dependency order):
  - Sales chain: payments, transaction_items, transactions, receipts, z_reports,
    cash_drawer_sessions
  - Loyalty / avoir: avoir_transactions, loyalty_transactions, loyalty_accounts
  - Coupons: coupons
  - Reservations: reservations (table dropped in a later migration; harmless if absent)
  - Clients: consents, customer_taste_profiles, clients
  - Products: product_embeddings, product_photos, products, intake_batches
  - Inventory orders: order_items, orders
  - Audit / logs / events / ai_tasks: audit_logs, events_log, ai_tasks,
    daily_reports, commercial_actions, action_results
  - Newsletter: newsletter_subscribers
  - Visibility: social_posts, social_mentions, google_reviews, seo_snapshots
  - Merchandising: window_display_proposals, store_arrangements, ai_recommendations,
    trend_analyses, zone_products
  - Calendar: cahier_day_archives, commercial_operations, local_events

Tables preserved:
  - users (manager + collaborateurs gardés)
  - categories, price_grids
  - store_zones, zone_tags, furniture_items
  - brand_tiers
  - markdown_rules (purgé dans une étape ultérieure du plan)
  - app_settings
  - suppliers
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow `python scripts/purge_databases.py` from repo root by extending sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine


# Wipe order matters: foreign keys are cleared from leaves to roots.
TABLES_TO_WIPE: list[str] = [
    # Sales
    "payments",
    "transaction_items",
    "receipts",
    "z_reports",
    "cash_drawer_sessions",
    "transactions",
    # Loyalty / avoir
    "avoir_transactions",
    "loyalty_transactions",
    "loyalty_accounts",
    # Coupons
    "coupons",
    # Reservations (may already be dropped in a later migration)
    "reservations",
    # Clients chain
    "consents",
    "customer_taste_profiles",
    "clients",
    # Products chain
    "product_embeddings",
    "product_photos",
    "products",
    "intake_batches",
    # Inventory orders
    "order_items",
    "orders",
    # Audit / logs / ai
    "ai_tasks",
    "audit_logs",
    "events_log",
    # Reporting
    "action_results",
    "commercial_actions",
    "daily_reports",
    # Newsletter
    "newsletter_subscribers",
    # Visibility
    "social_posts",
    "social_mentions",
    "google_reviews",
    "seo_snapshots",
    # Merchandising side-effects
    "window_display_proposals",
    "store_arrangements",
    "ai_recommendations",
    "trend_analyses",
    "zone_products",
    # Local calendar
    "cahier_day_archives",
    "commercial_operations",
    "local_events",
]

PRESERVED_TABLES = (
    "users",
    "categories",
    "price_grids",
    "suppliers",
    "store_zones",
    "zone_tags",
    "furniture_items",
    "brand_tiers",
    "markdown_rules",
    "app_settings",
)


async def _table_exists(db: AsyncSession, name: str) -> bool:
    def _check(sync_conn) -> bool:
        return inspect(sync_conn).has_table(name)

    return await db.run_sync(_check)


async def _count(db: AsyncSession, table: str) -> int:
    result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return int(result.scalar_one())


async def _wipe(db: AsyncSession, table: str) -> int:
    """DELETE all rows. Returns rows deleted."""
    before = await _count(db, table)
    if before == 0:
        return 0
    await db.execute(text(f"DELETE FROM {table}"))
    return before


async def main(confirm: bool, dry_run: bool) -> int:
    if not confirm and not dry_run:
        print(
            "Refusing to run without --confirm. Re-run with `--confirm` to actually "
            "wipe data, or `--dry-run` to print the plan only."
        )
        return 2

    print("=" * 70)
    print(f"Vintiz data purge — mode: {'DRY-RUN' if dry_run else 'LIVE'}")
    print("=" * 70)

    async with AsyncSession(engine) as db:
        print("\n--- Preserved tables (counts unchanged) ---")
        for t in PRESERVED_TABLES:
            try:
                c = await _count(db, t)
                print(f"  {t:30s}  {c:>10,d} rows kept")
            except Exception as exc:  # missing table is acceptable
                print(f"  {t:30s}  (skipped: {exc.__class__.__name__})")

        print("\n--- Wiping operational tables ---")
        total_before = 0
        total_after = 0
        wiped_table_count = 0

        for table in TABLES_TO_WIPE:
            try:
                exists = await _table_exists(db, table)
            except Exception as exc:
                print(f"  {table:30s}  inspect failed: {exc}")
                continue
            if not exists:
                print(f"  {table:30s}  (table absent — skipped)")
                continue

            before = await _count(db, table)
            total_before += before

            if dry_run:
                print(f"  {table:30s}  would delete {before:>10,d} rows")
                continue

            deleted = await _wipe(db, table)
            wiped_table_count += 1 if deleted else 0
            after = await _count(db, table)
            total_after += after
            print(
                f"  {table:30s}  deleted {deleted:>10,d}  remaining {after:>4,d}"
            )

        if dry_run:
            print(f"\nDRY-RUN: would delete {total_before:,d} rows total")
            return 0

        await db.commit()

    print("\n" + "=" * 70)
    print(
        f"Purge complete: {total_before:,d} rows deleted across "
        f"{wiped_table_count} tables ({total_after:,d} remaining — should be 0)"
    )
    print("=" * 70)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete rows. Without this flag the script does nothing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan (rows that would be deleted) without modifying the DB.",
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(main(confirm=args.confirm, dry_run=args.dry_run)))
