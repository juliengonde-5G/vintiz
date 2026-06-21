"""price reference grid — floor price per category × brand bucket

Revision ID: 0063
Revises: 0062
Create Date: 2026-06-21

Reference pricing grid ("grille tarifaire de référence") : one row per category
holding a ``standard`` floor (mid/basic/unknown brands) and a ``premium`` floor
"à partir de" (premium/luxury brands). Advisory — drives the "prix sous la
grille" notification at product creation/reprice.

Idempotent: skips creation when the table already exists (dev create_all may
have made it first).
"""

from alembic import op
import sqlalchemy as sa


revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return sa.inspect(conn).has_table(table)


def upgrade() -> None:
    if _table_exists("price_references"):
        return
    op.create_table(
        "price_references",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "category_id", sa.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False, unique=True,
        ),
        sa.Column("standard_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("premium_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_price_references_category_id", "price_references", ["category_id"]
    )


def downgrade() -> None:
    if not _table_exists("price_references"):
        return
    op.drop_index("ix_price_references_category_id", table_name="price_references")
    op.drop_table("price_references")
