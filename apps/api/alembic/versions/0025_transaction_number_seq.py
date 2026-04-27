"""transaction_number_seq — replace MAX+1 with a PostgreSQL sequence (NF525)

Revision ID: 0025
Revises: 0024
Create Date: 2026-04-27

Creates a SEQUENCE whose current value starts at the highest existing
transaction_number so no gap is introduced in the audit chain.
The sequence is idempotent: IF NOT EXISTS guards both creation and the
ALTER TABLE.
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create the sequence starting just above the current max (or at 1).
    conn.execute(sa.text(
        "CREATE SEQUENCE IF NOT EXISTS transaction_number_seq"
    ))
    max_row = conn.execute(
        sa.text("SELECT COALESCE(MAX(transaction_number), 0) FROM transactions")
    ).fetchone()
    current_max = int(max_row[0]) if max_row else 0
    conn.execute(sa.text(
        f"SELECT setval('transaction_number_seq', GREATEST(:m, 1), false)"
    ), {"m": current_max + 1})

    # Wire the sequence as the column default so INSERT without an explicit
    # value picks the next sequence value automatically.
    conn.execute(sa.text(
        "ALTER TABLE transactions "
        "ALTER COLUMN transaction_number "
        "SET DEFAULT nextval('transaction_number_seq')"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE transactions "
        "ALTER COLUMN transaction_number DROP DEFAULT"
    ))
    conn.execute(sa.text("DROP SEQUENCE IF EXISTS transaction_number_seq"))
