"""add SumUp tracking fields to payments + transactions

Revision ID: 0037
Revises: 0036
Create Date: 2026-05-14

Persists the SumUp side of a CB payment so we can :
- refund through ``POST /v1.0/merchants/{m}/payments/{id}/refunds`` (needs
  ``sumup_transaction_id``),
- show the card brand + last 4 digits on the receipt (SAV reference),
- reconcile our books against SumUp payouts (``transaction_code`` is the
  one printed on the SumUp app and on bank statements),
- replay an idempotent checkout request (``foreign_transaction_id``) so a
  network retry doesn't create a duplicate charge.

All columns are NULL-able : existing rows pre-migration are kept intact.

Idempotent : skips the ALTER when the column is already present (this
project deploys with ``alembic upgrade head`` on every release; running
twice in a row must be a no-op).
"""

from alembic import op
import sqlalchemy as sa


revision = "0037"
down_revision = "0036"
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


PAYMENT_COLUMNS = [
    ("sumup_checkout_id", sa.String(64)),
    ("sumup_transaction_id", sa.String(64)),
    ("sumup_transaction_code", sa.String(32)),
    ("sumup_auth_code", sa.String(16)),
    ("sumup_card_brand", sa.String(32)),
    ("sumup_card_last4", sa.String(4)),
    ("sumup_refunded_amount", sa.Numeric(10, 2)),
    # "production" or "sandbox" — captured at checkout time so we can
    # filter test transactions out of accounting exports.
    ("sumup_environment", sa.String(16)),
]


def upgrade() -> None:
    for name, type_ in PAYMENT_COLUMNS:
        if not _column_exists("payments", name):
            op.add_column("payments", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in PAYMENT_COLUMNS:
        if _column_exists("payments", name):
            op.drop_column("payments", name)
