"""communication_logs.body_html — store the rendered email sent

Revision ID: 0066
Revises: 0065
Create Date: 2026-06-21

Stores the HTML actually sent for the rich client emails (trend alert, personal
shopper…) so the manager can re-open the exact message from the client fiche.

Idempotent: adds the column only when missing.
"""

from alembic import op
import sqlalchemy as sa


revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    cols = [c["name"] for c in sa.inspect(conn).get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _has_column("communication_logs", "body_html"):
        op.add_column("communication_logs", sa.Column("body_html", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("communication_logs", "body_html"):
        op.drop_column("communication_logs", "body_html")
