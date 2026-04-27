"""store_zones 2D layout columns (moved from runtime migrations)

Revision ID: 0024
Revises: 0023
Create Date: 2026-04-27

Idempotent — uses IF NOT EXISTS so it is safe to apply on an already-updated
production database.
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("pos_x",                   "INTEGER NOT NULL DEFAULT 10"),
    ("pos_y",                   "INTEGER NOT NULL DEFAULT 10"),
    ("width",                   "INTEGER NOT NULL DEFAULT 20"),
    ("height",                  "INTEGER NOT NULL DEFAULT 20"),
    ("shape",                   "VARCHAR(20) NOT NULL DEFAULT 'rounded'"),
    ("icon",                    "VARCHAR(50)"),
    ("photo_url",               "VARCHAR(500)"),
    ("sales_target_monthly",    "NUMERIC(10, 2)"),
    ("display_order",           "INTEGER NOT NULL DEFAULT 0"),
]


def upgrade() -> None:
    for col, definition in _COLUMNS:
        op.execute(
            sa.text(
                f"ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS {col} {definition}"
            )
        )


def downgrade() -> None:
    for col, _ in reversed(_COLUMNS):
        op.execute(
            sa.text(f"ALTER TABLE store_zones DROP COLUMN IF EXISTS {col}")
        )
