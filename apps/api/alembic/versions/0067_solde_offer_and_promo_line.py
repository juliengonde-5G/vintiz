"""Add 'solde' to offer_type enum + promotional flag on transaction_items.

Revision ID: 0067
Revises: 0066
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Extend offer_type enum with the new 'solde' operation (Postgres only —
    # SQLite stores enums as text / CHECK rebuilt from the model).
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE offer_type ADD VALUE IF NOT EXISTS 'solde'")

    # promotional flag on transaction items — drives the "no loyalty points on
    # promo/operation articles" rule. Idempotent guard for environments where
    # create_all already added the column on first boot.
    cols = {c["name"] for c in sa.inspect(bind).get_columns("transaction_items")}
    if "promotional" not in cols:
        op.add_column(
            "transaction_items",
            sa.Column(
                "promotional",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("transaction_items")}
    if "promotional" in cols:
        op.drop_column("transaction_items", "promotional")
    # Note: Postgres cannot easily DROP an enum value; 'solde' is left in place.
