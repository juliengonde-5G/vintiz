"""add markdown_rules table (P3-001)

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-26

Idempotent like prior migrations.
"""

from alembic import op
import sqlalchemy as sa


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
    ).fetchone() is not None


def upgrade() -> None:
    if _table_exists("markdown_rules"):
        return
    op.create_table(
        "markdown_rules",
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
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
        sa.Column("conditions", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("action", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_markdown_rules_active_priority",
        "markdown_rules",
        ["active", "priority"],
    )


def downgrade() -> None:
    if _table_exists("markdown_rules"):
        op.drop_index("ix_markdown_rules_active_priority", table_name="markdown_rules")
        op.drop_table("markdown_rules")
