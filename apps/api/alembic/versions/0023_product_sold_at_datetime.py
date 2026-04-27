"""Convert products.sold_at from VARCHAR(255) to TIMESTAMP WITH TIME ZONE

Revision ID: 0023
Revises: 0022
Create Date: 2026-04-27

The column previously stored ISO-8601 strings set via datetime.isoformat().
The USING clause casts existing values to timestamptz; rows that cannot be
parsed (malformed strings or NULL) are silently set to NULL.
"""

from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "products",
        "sold_at",
        existing_type=sa.String(255),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        nullable=True,
        postgresql_using="CASE WHEN sold_at IS NULL THEN NULL "
                         "ELSE sold_at::timestamp with time zone END",
    )


def downgrade() -> None:
    op.alter_column(
        "products",
        "sold_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.String(255),
        existing_nullable=True,
        nullable=True,
        postgresql_using="CASE WHEN sold_at IS NULL THEN NULL "
                         "ELSE to_char(sold_at, 'YYYY-MM-DD\"T\"HH24:MI:SS.US+00') END",
    )
