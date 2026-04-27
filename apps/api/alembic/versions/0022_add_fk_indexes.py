"""Add missing indexes on FK columns for payments, transaction_items, transactions

Revision ID: 0022
Revises: 0021
Create Date: 2026-04-27

Idempotent: uses IF NOT EXISTS via op.create_index with unique=False.
Each index is checked via information_schema before creation to support
re-entrant runs.
"""

from alembic import op
import sqlalchemy as sa


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :n"
        ),
        {"n": name},
    ).fetchone() is not None


def upgrade() -> None:
    # payments.transaction_id — used in every JOIN payments → transactions
    if not _index_exists("ix_payments_transaction_id"):
        op.create_index("ix_payments_transaction_id", "payments", ["transaction_id"])

    # transaction_items.transaction_id — used in every JOIN items → transactions
    if not _index_exists("ix_transaction_items_transaction_id"):
        op.create_index(
            "ix_transaction_items_transaction_id",
            "transaction_items",
            ["transaction_id"],
        )

    # transaction_items.product_id — used in refund service and product_insights
    if not _index_exists("ix_transaction_items_product_id"):
        op.create_index(
            "ix_transaction_items_product_id",
            "transaction_items",
            ["product_id"],
        )

    # transactions.client_id — used in CRM history and anniversary queries
    if not _index_exists("ix_transactions_client_id"):
        op.create_index("ix_transactions_client_id", "transactions", ["client_id"])

    # transactions.cashier_id — used in Z-report cashier attribution
    if not _index_exists("ix_transactions_cashier_id"):
        op.create_index("ix_transactions_cashier_id", "transactions", ["cashier_id"])

    # transactions.original_transaction_id — used in refund chain queries
    if not _index_exists("ix_transactions_original_transaction_id"):
        op.create_index(
            "ix_transactions_original_transaction_id",
            "transactions",
            ["original_transaction_id"],
        )


def downgrade() -> None:
    for idx, tbl in [
        ("ix_transactions_original_transaction_id", "transactions"),
        ("ix_transactions_cashier_id", "transactions"),
        ("ix_transactions_client_id", "transactions"),
        ("ix_transaction_items_product_id", "transaction_items"),
        ("ix_transaction_items_transaction_id", "transaction_items"),
        ("ix_payments_transaction_id", "payments"),
    ]:
        if _index_exists(idx):
            op.drop_index(idx, table_name=tbl)
