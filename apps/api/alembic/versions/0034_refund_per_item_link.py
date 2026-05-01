"""Sprint 2 — refund items track their original line.

Adds ``transaction_items.original_transaction_item_id`` so a refund row
points back at the exact original sale line. Without it, the
``RefundService._already_refunded_qty`` aggregator could only match by
``product_id`` — two distinct lines of the same product on the same
sale wrongly shared their refund quota.

Existing refund rows keep ``NULL`` on the new column; the service falls
back to the legacy product_id match for them, so this migration is
zero-downtime and doesn't require a backfill.

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table)}


def _index_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "transaction_items" not in set(inspector.get_table_names()):
        return

    if not _column_exists("transaction_items", "original_transaction_item_id"):
        op.add_column(
            "transaction_items",
            sa.Column(
                "original_transaction_item_id",
                sa.dialects.postgresql.UUID(as_uuid=True)
                if bind.dialect.name == "postgresql"
                else sa.String(length=36),
                nullable=True,
            ),
        )
        # Self-FK on PostgreSQL only — SQLite can skip the explicit constraint
        # since the column is plain text and tests don't enforce referential
        # integrity here.
        if bind.dialect.name == "postgresql":
            op.create_foreign_key(
                "fk_tx_items_original_item",
                "transaction_items",
                "transaction_items",
                ["original_transaction_item_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if not _index_exists("transaction_items", "ix_tx_items_original_item"):
        op.create_index(
            "ix_tx_items_original_item",
            "transaction_items",
            ["original_transaction_item_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "transaction_items" not in set(inspector.get_table_names()):
        return

    if _index_exists("transaction_items", "ix_tx_items_original_item"):
        op.drop_index("ix_tx_items_original_item", table_name="transaction_items")

    if bind.dialect.name == "postgresql":
        try:
            op.drop_constraint(
                "fk_tx_items_original_item",
                "transaction_items",
                type_="foreignkey",
            )
        except Exception:  # noqa: BLE001 — constraint may have been dropped already
            pass

    if _column_exists("transaction_items", "original_transaction_item_id"):
        op.drop_column("transaction_items", "original_transaction_item_id")
