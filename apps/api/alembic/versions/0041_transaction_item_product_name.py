"""add product_name snapshot to transaction_items

Revision ID: 0041
Revises: 0040
Create Date: 2026-05-23

Manual lines (reusable bag, custom article) have no product_id, so their label
was lost at sale time and tickets/receipts/invoices printed "Article". This
column freezes the item label at sale time — required for manual lines and a
stable fallback for catalog items whose Product is later edited/deleted.

NULL-able: existing rows keep working (renderers fall back to the linked
Product name then "Article"). Idempotent.
"""

from alembic import op
import sqlalchemy as sa


revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if not _column_exists("transaction_items", "product_name"):
        op.add_column(
            "transaction_items",
            sa.Column("product_name", sa.String(255), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("transaction_items", "product_name"):
        op.drop_column("transaction_items", "product_name")
