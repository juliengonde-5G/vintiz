"""add 'cheque_cdc' to payment_method enum

Revision ID: 0043
Revises: 0042
Create Date: 2026-05-25

Adds the "Chèque CDC" payment method (chèque cadeau « Le Club des
Commerçants »). It settles like a regular cheque at the till but is tracked
as a distinct method so the Z report, the fiscal export and the receipts can
separate it from an ordinary cheque (needed to reconcile the vouchers with
the association for reimbursement).

Idempotent: skips if the value already exists in the enum.
"""

from alembic import op


revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: ALTER TYPE ... ADD VALUE IF NOT EXISTS landed in PG 9.6;
    # safe to run on every restart. The PaymentAttempt table shares the same
    # ``payment_method`` enum type, so this single ALTER covers both tables.
    op.execute("ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'cheque_cdc'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values without a recreate;
    # leaving the value in place is harmless.
    pass
