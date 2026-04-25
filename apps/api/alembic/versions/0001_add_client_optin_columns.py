"""add email_optin and sms_optin to clients

Revision ID: 0001
Revises:
Create Date: 2026-04-13

These columns were added to the Client model but may be missing from existing
production databases that were created before the columns were introduced.
The migration is idempotent: if the columns already exist it does nothing.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError


revision = "0001"
down_revision = None
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


def upgrade() -> None:
    if not _column_exists("clients", "email_optin"):
        op.add_column(
            "clients",
            sa.Column("email_optin", sa.Boolean(), nullable=False, server_default="false"),
        )
    if not _column_exists("clients", "sms_optin"):
        op.add_column(
            "clients",
            sa.Column("sms_optin", sa.Boolean(), nullable=False, server_default="false"),
        )


def downgrade() -> None:
    op.drop_column("clients", "sms_optin")
    op.drop_column("clients", "email_optin")
