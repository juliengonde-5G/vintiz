"""custom_reports — saved « Rapports sur-mesure » definitions

Revision ID: 0065
Revises: 0064
Create Date: 2026-06-21

A report is a named page with a JSON ``layout`` of widget specs (chart type,
dataset, measure, dimension, grain, range, filters). Only the definition is
stored; the data is computed live by the reporting engine.

Idempotent: skips creation when the table already exists.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return sa.inspect(conn).has_table(table)


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    if _table_exists("custom_reports"):
        return
    op.create_table(
        "custom_reports",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("layout", _json_type(), nullable=False),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    if not _table_exists("custom_reports"):
        return
    op.drop_table("custom_reports")
