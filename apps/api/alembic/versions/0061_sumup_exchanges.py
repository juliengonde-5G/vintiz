"""create sumup_exchanges — SumUp API exchange diagnostic log

Revision ID: 0061
Revises: 0060
Create Date: 2026-06-11

Append-only ledger of every HTTP call the backend makes to SumUp
(create checkout, push to reader, poll status, cancel, terminate, refund,
ping…). Surfaced in ``/settings > Système`` so a CB sale that silently fell
through to payment-link mode (no reader resolved) — and therefore never rang
the Solo terminal — is finally visible from the back-office.

All free-text fields are redacted before persistence (no Bearer token, API
key, affiliate key, PAN or CVV stored). This is a rolling debug buffer, not a
fiscal record, so it is safe to prune/clear.

Idempotent: skips creation when the table is already present.
"""

from alembic import op
import sqlalchemy as sa


revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return sa.inspect(conn).has_table(table)


def upgrade() -> None:
    if _table_exists("sumup_exchanges"):
        return
    op.create_table(
        "sumup_exchanges",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
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
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(16), nullable=True),
        sa.Column("checkout_id", sa.String(120), nullable=True),
        sa.Column("reader_id", sa.String(100), nullable=True),
        sa.Column("foreign_transaction_id", sa.String(120), nullable=True),
        sa.Column("request_summary", sa.Text(), nullable=True),
        sa.Column("response_summary", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(20), nullable=True),
    )
    # The log is browsed newest-first and pruned by age → index created_at.
    op.create_index(
        "ix_sumup_exchanges_created_at", "sumup_exchanges", ["created_at"]
    )


def downgrade() -> None:
    if not _table_exists("sumup_exchanges"):
        return
    op.drop_index("ix_sumup_exchanges_created_at", table_name="sumup_exchanges")
    op.drop_table("sumup_exchanges")
