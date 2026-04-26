"""extend product_status enum + add received_at/displayed_at/markdown_history (P1-006)

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-26

Backward-compatible: keeps the legacy values (stock/display/sold/returned)
and adds the explicit life-cycle states from the V1 audit §2.2.6.

Idempotent like prior migrations.
"""

from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).fetchone() is not None


_NEW_STATUS_VALUES = (
    "received",
    "sorted",
    "tagged",
    "displayed",
    "discounted",
    "deep_discounted",
    "donated",
    "returned_to_sorting",
)


def upgrade() -> None:
    # Add new enum values; ALTER TYPE ... ADD VALUE IF NOT EXISTS is safe
    # to re-run from PG 9.6 onwards.
    for value in _NEW_STATUS_VALUES:
        op.execute(
            f"ALTER TYPE product_status ADD VALUE IF NOT EXISTS '{value}'"
        )

    if not _column_exists("products", "received_at"):
        op.add_column(
            "products",
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists("products", "displayed_at"):
        op.add_column(
            "products",
            sa.Column("displayed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists("products", "markdown_history"):
        op.add_column(
            "products",
            sa.Column(
                "markdown_history",
                sa.dialects.postgresql.JSONB(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    # PG doesn't support removing enum values without recreating the type.
    # Leave them in place; dropping columns is enough.
    if _column_exists("products", "markdown_history"):
        op.drop_column("products", "markdown_history")
    if _column_exists("products", "displayed_at"):
        op.drop_column("products", "displayed_at")
    if _column_exists("products", "received_at"):
        op.drop_column("products", "received_at")
