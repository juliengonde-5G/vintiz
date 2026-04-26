"""add transactions.client_uuid for offline-replay idempotence (P1-005)

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-26

The POS UI buffers transactions in an IndexedDB queue when the network
drops. On reconnection it replays each one against POST /api/pos/transactions
— but a partially-applied replay (POST succeeds, browser dies before
removing the entry) would otherwise create a duplicate. The client
generates a UUID before the first attempt and the backend uses it to
short-circuit duplicates.

Idempotent like prior migrations.
"""

from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).fetchone() is not None


def upgrade() -> None:
    if not _column_exists("transactions", "client_uuid"):
        op.add_column(
            "transactions",
            sa.Column(
                "client_uuid",
                sa.dialects.postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_unique_constraint(
            "uq_transactions_client_uuid",
            "transactions",
            ["client_uuid"],
        )


def downgrade() -> None:
    if _column_exists("transactions", "client_uuid"):
        op.drop_constraint(
            "uq_transactions_client_uuid", "transactions", type_="unique"
        )
        op.drop_column("transactions", "client_uuid")
