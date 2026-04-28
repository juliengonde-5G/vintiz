"""Operational data purge — used by both the CLI script and the admin endpoint.

Wipes operational rows (clients / products / transactions and their satellites)
while preserving structural rows: users, categories, price grids, store zones,
brand tiers, app settings, suppliers.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession


# Wipe order matters: foreign keys are cleared from leaves to roots.
TABLES_TO_WIPE: list[str] = [
    # Offers (Lot 3) — wipe before transactions so references to coupons clear cleanly
    "offers",
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
    "window_decors",
    "store_arrangements",
    "ai_recommendations",
    "trend_analyses",
    "zone_products",
    # Weekly checklist (Lot 4)
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
    "app_settings",
)


async def _table_exists(db: AsyncSession, name: str) -> bool:
    def _check(sync_conn) -> bool:
        return inspect(sync_conn).has_table(name)

    return await db.run_sync(_check)


async def _count(db: AsyncSession, table: str) -> int:
    result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return int(result.scalar_one())


async def purge_operational_data(db: AsyncSession) -> dict:
    """Wipe operational tables. Caller is responsible for the surrounding
    transaction (commit/rollback).

    Returns a per-table summary ``{table: rows_deleted}`` for audit / UI.
    """
    summary: dict[str, int] = {}
    total_before = 0

    for table in TABLES_TO_WIPE:
        try:
            exists = await _table_exists(db, table)
        except Exception:
            continue
        if not exists:
            continue
        before = await _count(db, table)
        if before == 0:
            summary[table] = 0
            continue
        await db.execute(text(f"DELETE FROM {table}"))
        summary[table] = before
        total_before += before

    return {"total_deleted": total_before, "per_table": summary}
