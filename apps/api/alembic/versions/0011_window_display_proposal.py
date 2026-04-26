"""add window_display_proposals table (P2-007)

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-26

Idempotent like prior migrations.
"""

from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
    ).fetchone() is not None


def upgrade() -> None:
    if _table_exists("window_display_proposals"):
        return
    op.create_table(
        "window_display_proposals",
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
        sa.Column("iso_week", sa.String(length=8), nullable=False, unique=True),
        sa.Column(
            "proposal",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "used_llm",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "accepted_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    if _table_exists("window_display_proposals"):
        op.drop_table("window_display_proposals")
