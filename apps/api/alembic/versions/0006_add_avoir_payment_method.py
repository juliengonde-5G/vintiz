"""add 'avoir' to payment_method enum (P1-016 closing UI work)

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-26

Allows POS checkouts to settle part or all of a sale using the client's
store credit (avoir). The PosService is updated separately to debit the
client's avoir balance and write an AvoirTransaction(debit) ledger entry.

Idempotent: skips if the value already exists in the enum.
"""

from alembic import op


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: ALTER TYPE ... ADD VALUE IF NOT EXISTS landed in PG 9.6;
    # safe to run on every restart.
    op.execute("ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'avoir'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values without a recreate;
    # leaving the value in place is harmless.
    pass
