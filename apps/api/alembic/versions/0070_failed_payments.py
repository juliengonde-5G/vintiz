"""Create failed_payments queue (offline-mode groundwork).

Persists CB checkouts that failed *recoverably* so they can be re-attempted
later (cron or manual retry) instead of losing the sale. Decoupled from the
NF525 chain — a row here is not a sale.

Revision ID: 0070
Revises: 0069
Create Date: 2026-07-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # On Postgres, the ENUM type is created implicitly by ``create_table`` from
    # the ``sa.Enum`` column (a single CREATE TYPE — no separate .create() call,
    # which would emit it twice). On SQLite (tests build the schema from the
    # models, not from migrations — this branch is defensive) the enum degrades
    # to a plain VARCHAR. UUID columns use the portable ``postgresql.UUID`` the
    # models already rely on cross-dialect.
    status_col = (
        sa.Enum(
            "pending", "succeeded", "exhausted", "abandoned",
            name="failed_payment_status",
        )
        if is_pg
        else sa.String(length=20)
    )

    op.create_table(
        "failed_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("checkout_reference", sa.String(length=100), nullable=False),
        sa.Column("foreign_transaction_id", sa.String(length=120), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("status", status_col, nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_checkout_id", sa.String(length=120), nullable=True),
        sa.Column(
            "is_recoverable", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("reader_id", sa.String(length=100), nullable=True),
        sa.Column("cashier_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_failed_payments_status"), "failed_payments", ["status"]
    )
    op.create_index(
        op.f("ix_failed_payments_next_retry_at"),
        "failed_payments",
        ["next_retry_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index(op.f("ix_failed_payments_next_retry_at"), table_name="failed_payments")
    op.drop_index(op.f("ix_failed_payments_status"), table_name="failed_payments")
    op.drop_table("failed_payments")
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS failed_payment_status")
