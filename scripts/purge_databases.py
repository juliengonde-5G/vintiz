"""One-shot data purge for Vintiz — single source of truth.

Wipes operational data (clients / products / transactions and their
satellites) while preserving structural rows: users, categories, price grids,
store zones, brand tiers, app settings.

This is the **only** way to purge — the in-app endpoint
``POST /api/admin/data/purge`` and its UI panel were removed (2026-05) after
they silently drifted from the actual schema (wrong table name
``cash_drawer_sessions`` + 4 missing tables). Keeping the wipe list in one
place removes that drift surface.

Usage:
    PYTHONPATH=apps/api python scripts/purge_databases.py --dry-run
    PYTHONPATH=apps/api python scripts/purge_databases.py --confirm

In production (Docker):
    docker exec -it vintiz-api python scripts/purge_databases.py --dry-run
    docker exec -it vintiz-api python scripts/purge_databases.py --confirm

The script refuses to run without --confirm. It prints the row count for each
table before and after the purge so the operator can audit what happened.

Tables wiped (in dependency order):
  - Sales chain: payments, transaction_items, transactions, receipts, z_reports,
    cash_drawer_sessions
  - Loyalty / avoir: avoir_transactions, loyalty_transactions, loyalty_accounts
  - Coupons: coupons
  - Clients: consents, customer_taste_profiles, clients, magic_link_tokens
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

# Make ``import app.core.database`` work in both the dev and Docker layouts:
# - Dev (repo root):     <ROOT>/apps/api/app/core/database.py
# - Docker (api image):  /app/app/core/database.py  (WORKDIR is /app, scripts at /app/scripts)
# Add the first directory that contains ``app/core/database.py``.
_HERE = Path(__file__).resolve()
for _candidate in (
    _HERE.parents[1] / "apps" / "api",   # dev layout
    _HERE.parents[1],                    # Docker prod (/app)
):
    if (_candidate / "app" / "core" / "database.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    raise SystemExit(
        "purge_databases: cannot locate the api `app` package — checked "
        f"{_HERE.parents[1] / 'apps' / 'api'} and {_HERE.parents[1]}"
    )

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine


# Wipe order matters: foreign keys are cleared from leaves to roots.
#
# Drift fix (2026-05): the previous list referenced ``cash_drawer_sessions``
# (the table is actually ``cash_drawers``) and missed ``offers``,
# ``weekly_tasks``, ``window_decors``, ``local_events``. Symptom in prod:
# purge silently skipped these tables (or aborted on the wrong table name).
TABLES_TO_WIPE: list[str] = [
    # Offers — wipe before transactions/clients so coupon/avoir refs clear
    "offers",
    # Sales
    "payments",
    "transaction_items",
    "receipts",
    "z_reports",
    "cash_drawers",
    "transactions",
    # Loyalty / avoir
    "avoir_transactions",
    "loyalty_transactions",
    "loyalty_accounts",
    # Coupons
    "coupons",
    # Clients chain
    "magic_link_tokens",
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
    "window_decors",
    "store_arrangements",
    "ai_recommendations",
    "trend_analyses",
    "zone_products",
    # Weekly checklist
    "weekly_tasks",
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
    # NB: ``markdown_rules`` was dropped by migration 0027 and
    # ``app_settings`` is a file (data/app_config.json), not a DB table.
    # Both used to be listed here and produced confusing
    # ``(skipped: ProgrammingError)`` lines on every run.
)


async def _existing_tables() -> set[str]:
    """Return all real tables in the connected database in one round-trip.

    Replaces the previous ``_table_exists`` per-call check that wrongly fed
    an ``AsyncSession`` to ``inspect()``. ``run_sync`` on a *connection*
    yields the underlying sync connection, which ``inspect()`` accepts;
    ``run_sync`` on a session does not. Caching the names also drops 40+
    extra round-trips.
    """
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )


async def _count(db: AsyncSession, table: str) -> int:
    result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return int(result.scalar_one())


async def _truncate_cascade(db: AsyncSession, tables: list[str]) -> None:
    """PostgreSQL bulk wipe — atomic + handles FK chains automatically.

    Without CASCADE the previous DELETE-loop hit
    ``ForeignKeyViolationError: events_log_product_id_fkey`` because
    ``events_log`` (which references ``products`` via FK) was wiped
    *after* ``products``. Reordering the list manually is fragile —
    every new FK on a Vintiz table would re-introduce the bug.

    ``TRUNCATE … CASCADE``:
    - Wipes all listed tables in a single statement.
    - CASCADE auto-extends to any referencing table — but only the ones
      we already listed (FKs in Vintiz only point downward into wipe-list
      tables, never up to ``users`` / ``categories`` / etc.).
    - ``RESTART IDENTITY`` resets sequences (e.g. ``transaction_number_seq``
      back to 1) so a re-opened boutique starts clean.
    - Atomic: either all tables are emptied or none — no partial state.
    """
    if not tables:
        return
    quoted = ", ".join(f'"{t}"' for t in tables)
    await db.execute(
        text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
    )


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

    # Single round-trip introspection — replaces the per-table inspect()
    # call that previously failed on AsyncSession.
    existing_tables = await _existing_tables()

    async with AsyncSession(engine) as db:
        print("\n--- Preserved tables (counts unchanged) ---")
        for t in PRESERVED_TABLES:
            if t not in existing_tables:
                print(f"  {t:30s}  (table absent — skipped)")
                continue
            try:
                c = await _count(db, t)
                print(f"  {t:30s}  {c:>10,d} rows kept")
            except Exception as exc:  # missing table is acceptable
                print(f"  {t:30s}  (skipped: {exc.__class__.__name__})")

        print("\n--- Wiping operational tables ---")
        # Phase 1: count what we're about to wipe (per-table report).
        total_before = 0
        wipe_targets: list[str] = []
        for table in TABLES_TO_WIPE:
            if table not in existing_tables:
                print(f"  {table:30s}  (table absent — skipped)")
                continue
            before = await _count(db, table)
            total_before += before
            wipe_targets.append(table)
            verb = "would delete" if dry_run else "queued    "
            print(f"  {table:30s}  {verb} {before:>10,d} rows")

        if dry_run:
            print(f"\nDRY-RUN: would delete {total_before:,d} rows total")
            return 0

        # Phase 2: single atomic TRUNCATE … CASCADE on PostgreSQL ;
        # per-table DELETE fallback for SQLite (dev tests). PG is the
        # only target the prod ops actually use.
        dialect = engine.dialect.name
        if dialect == "postgresql":
            await _truncate_cascade(db, wipe_targets)
            wiped_table_count = len(wipe_targets)
        else:
            wiped_table_count = 0
            for table in wipe_targets:
                await db.execute(text(f"DELETE FROM {table}"))
                wiped_table_count += 1

        await db.commit()

        # Phase 3: verify everything reached zero.
        total_after = 0
        for table in wipe_targets:
            total_after += await _count(db, table)

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
