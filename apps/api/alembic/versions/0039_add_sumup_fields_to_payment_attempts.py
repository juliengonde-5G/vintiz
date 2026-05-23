"""add SumUp Solo call/return fields to payment_attempts

Revision ID: 0039
Revises: 0038
Create Date: 2026-05-23

Completes the CB attempts backlog: every Solo call now records its return
(transaction reference, auth code, masked card) on the PaymentAttempt — not
only on the committed Payment. A declined or cancelled attempt that never
produced an NF525 Transaction therefore still carries the terminal outcome,
which the merged /admin/transactions view surfaces.

All columns are NULL-able: existing rows pre-migration are kept intact.

Idempotent: skips the ALTER when the column is already present.
"""

from alembic import op
import sqlalchemy as sa


revision = "0039"
down_revision = "0038"
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


ATTEMPT_COLUMNS = [
    ("sumup_transaction_id", sa.String(64)),
    ("sumup_transaction_code", sa.String(32)),
    ("sumup_auth_code", sa.String(16)),
    ("sumup_card_brand", sa.String(32)),
    ("sumup_card_last4", sa.String(4)),
]


def upgrade() -> None:
    for name, type_ in ATTEMPT_COLUMNS:
        if not _column_exists("payment_attempts", name):
            op.add_column("payment_attempts", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in ATTEMPT_COLUMNS:
        if _column_exists("payment_attempts", name):
            op.drop_column("payment_attempts", name)
