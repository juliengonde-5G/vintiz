"""fix shelf_date column to TIMESTAMP WITH TIME ZONE

Revision ID: 0045
Revises: 0044
Create Date: 2026-05-25

The shelf_date column was created as TIMESTAMP WITHOUT TIME ZONE while the
application assigns timezone-aware datetimes (datetime.now(timezone.utc)).
asyncpg raises a DataError on every mise-en-rayon operation.

Fix: convert to TIMESTAMP WITH TIME ZONE, preserving existing values by
treating them as UTC.
"""

from alembic import op
import sqlalchemy as sa

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN shelf_date TYPE TIMESTAMP WITH TIME ZONE "
        "USING shelf_date AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN shelf_date TYPE TIMESTAMP WITHOUT TIME ZONE "
        "USING shelf_date AT TIME ZONE 'UTC'"
    )
