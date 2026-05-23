"""add sms_body to receipt_templates

Revision ID: 0042
Revises: 0041
Create Date: 2026-05-23

Lets the ticket resend SMS wording be configured from the studio (same
template system as the email + printed ticket). NULL-able, idempotent.
"""

from alembic import op
import sqlalchemy as sa


revision = "0042"
down_revision = "0041"
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
    if not _column_exists("receipt_templates", "sms_body"):
        op.add_column(
            "receipt_templates", sa.Column("sms_body", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    if _column_exists("receipt_templates", "sms_body"):
        op.drop_column("receipt_templates", "sms_body")
