"""add refund/avoir columns and avoir_transactions table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-26

Tickets P1-010 (refund flow) + P1-016 (avoir_credit on Client).

- clients.avoir_credit: store-credit balance, NOT NULL DEFAULT 0
- transactions.original_transaction_id: link a refund to its origin sale
- transactions.refund_reason: TEXT, optional human-readable reason
- avoir_transactions: append-only ledger (credit/debit/adjust)

Idempotent like 0001 / 0002.
"""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
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


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
        ),
        {"t": table},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if not _column_exists("clients", "avoir_credit"):
        op.add_column(
            "clients",
            sa.Column(
                "avoir_credit",
                sa.Numeric(10, 2),
                nullable=False,
                server_default="0",
            ),
        )

    if not _column_exists("transactions", "original_transaction_id"):
        op.add_column(
            "transactions",
            sa.Column(
                "original_transaction_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_foreign_key(
            "fk_transactions_original_transaction",
            "transactions",
            "transactions",
            ["original_transaction_id"],
            ["id"],
        )

    if not _column_exists("transactions", "refund_reason"):
        op.add_column(
            "transactions",
            sa.Column("refund_reason", sa.Text(), nullable=True),
        )

    if not _table_exists("avoir_transactions"):
        # Create the enum idempotently. PG has no CREATE TYPE IF NOT EXISTS
        # so we wrap in a DO/EXCEPTION block. The lifespan's
        # Base.metadata.create_all may have already created it on a prior
        # boot, so this is the safe form.
        op.execute(
            """
            DO $$ BEGIN
                CREATE TYPE avoir_tx_type AS ENUM ('credit', 'debit', 'adjust');
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
        # ``create_type=False`` so create_table() doesn't try to recreate
        # the type implicitly (which would crash on the second run).
        avoir_tx_type = sa.dialects.postgresql.ENUM(
            "credit", "debit", "adjust",
            name="avoir_tx_type",
            create_type=False,
        )
        op.create_table(
            "avoir_transactions",
            sa.Column(
                "id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                primary_key=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "client_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("clients.id"),
                nullable=False,
            ),
            sa.Column(
                "transaction_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("transactions.id"),
                nullable=True,
            ),
            sa.Column("tx_type", avoir_tx_type, nullable=False),
            sa.Column("amount", sa.Numeric(10, 2), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if _table_exists("avoir_transactions"):
        op.drop_table("avoir_transactions")
        op.execute("DROP TYPE IF EXISTS avoir_tx_type")
    if _column_exists("transactions", "refund_reason"):
        op.drop_column("transactions", "refund_reason")
    if _column_exists("transactions", "original_transaction_id"):
        op.drop_constraint(
            "fk_transactions_original_transaction",
            "transactions",
            type_="foreignkey",
        )
        op.drop_column("transactions", "original_transaction_id")
    if _column_exists("clients", "avoir_credit"):
        op.drop_column("clients", "avoir_credit")
