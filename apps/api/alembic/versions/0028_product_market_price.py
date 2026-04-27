"""Add market price estimate columns to products (v3 scoring).

Revision ID: 0028
Revises: 0027
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("market_price_estimate", sa.Float(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column(
            "market_price_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "market_price_updated_at")
    op.drop_column("products", "market_price_estimate")
