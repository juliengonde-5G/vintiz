"""Add error-triage fields to sumup_exchanges.

``is_error`` (indexed), ``error_type`` (indexed) and ``retry_count`` let the
back-office filter and analyse failed SumUp calls without scanning the whole
diagnostic log. Additive + nullable-safe : existing rows backfill to
``is_error = NOT ok`` and ``retry_count = 0``.

Revision ID: 0069
Revises: 0068
Create Date: 2026-07-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sumup_exchanges",
        sa.Column("is_error", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "sumup_exchanges",
        sa.Column("error_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "sumup_exchanges",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    # Backfill is_error from the existing ok flag so old rows filter correctly.
    op.execute("UPDATE sumup_exchanges SET is_error = NOT ok")
    op.create_index(
        op.f("ix_sumup_exchanges_is_error"),
        "sumup_exchanges",
        ["is_error"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sumup_exchanges_error_type"),
        "sumup_exchanges",
        ["error_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sumup_exchanges_error_type"), table_name="sumup_exchanges")
    op.drop_index(op.f("ix_sumup_exchanges_is_error"), table_name="sumup_exchanges")
    op.drop_column("sumup_exchanges", "retry_count")
    op.drop_column("sumup_exchanges", "error_type")
    op.drop_column("sumup_exchanges", "is_error")
