"""Add reconciliation columns to accounting_exports

Revision ID: 0048
Revises: 0047
Create Date: 2026-05-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE accounting_exports
            ADD COLUMN IF NOT EXISTS reconciliation_ran BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS reconciliation_delta NUMERIC(12,2),
            ADD COLUMN IF NOT EXISTS reconciliation_matched INTEGER,
            ADD COLUMN IF NOT EXISTS reconciliation_unmatched_vintiz INTEGER,
            ADD COLUMN IF NOT EXISTS reconciliation_unmatched_sumup INTEGER
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE accounting_exports
            DROP COLUMN IF EXISTS reconciliation_ran,
            DROP COLUMN IF EXISTS reconciliation_delta,
            DROP COLUMN IF EXISTS reconciliation_matched,
            DROP COLUMN IF EXISTS reconciliation_unmatched_vintiz,
            DROP COLUMN IF EXISTS reconciliation_unmatched_sumup
    """))
