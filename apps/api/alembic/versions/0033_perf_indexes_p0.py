"""Sprint 1 P0 perf indexes — products hot-path filters + loyalty idempotency.

The audit pinpointed seq scans on the most-filtered Product columns
(status, created_at, sold_at, displayed_at, zone_id, category_id) — these
are touched by inventory.search, merchandising, embeddings, retail KPIs,
dashboard, ESS reporting and the return-to-sorting cron. At ~5k+ SKU the
seq scans cost &gt;200ms each.

Adds:
- ix_products_status                       (status filter on every listing)
- ix_products_status_created_at            (composite for ORDER BY recency)
- ix_products_sold_at                      (daily_recap, ESS, period KPIs)
- ix_products_displayed_at                 (return-to-sorting cron)
- ix_products_zone_id                      (zone occupancy aggregations)
- ix_products_category_id                  (category joins / breakdowns)
- ix_loyalty_tx_account_desc               (replay idempotency lookup —
                                            backs the new earn-once guard
                                            in PosService._credit_loyalty)

All creations are idempotent (skip if already present) so the migration
can replay safely against any environment.

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {idx["name"] for idx in inspector.get_indexes(table)}


def _create(name: str, table: str, cols: list[str]) -> None:
    if name not in _index_names(table):
        op.create_index(name, table, cols)


def _drop(name: str, table: str) -> None:
    if name in _index_names(table):
        op.drop_index(name, table_name=table)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "products" in tables:
        _create("ix_products_status", "products", ["status"])
        _create("ix_products_status_created_at", "products", ["status", "created_at"])
        _create("ix_products_sold_at", "products", ["sold_at"])
        _create("ix_products_displayed_at", "products", ["displayed_at"])
        _create("ix_products_zone_id", "products", ["zone_id"])
        _create("ix_products_category_id", "products", ["category_id"])

    if "loyalty_transactions" in tables:
        _create(
            "ix_loyalty_tx_account_desc",
            "loyalty_transactions",
            ["account_id", "description"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "loyalty_transactions" in tables:
        _drop("ix_loyalty_tx_account_desc", "loyalty_transactions")

    if "products" in tables:
        _drop("ix_products_category_id", "products")
        _drop("ix_products_zone_id", "products")
        _drop("ix_products_displayed_at", "products")
        _drop("ix_products_sold_at", "products")
        _drop("ix_products_status_created_at", "products")
        _drop("ix_products_status", "products")
