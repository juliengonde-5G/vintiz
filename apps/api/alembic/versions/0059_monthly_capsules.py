"""Capsule du mois — page éditoriale mensuelle

Revision ID: 0059
Revises: 0058
Create Date: 2026-06-04

Une seule ligne par ISO-month, payload libre dans ``proposal``. Le cron
mensuel upsert la ligne ; idempotent via la contrainte ``unique(iso_month)``.
"""
import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    if is_pg:
        conn.execute(sa.text(
            """
            CREATE TABLE IF NOT EXISTS monthly_capsules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                iso_month VARCHAR(7) NOT NULL UNIQUE,
                proposal JSONB NOT NULL,
                used_llm BOOLEAN NOT NULL DEFAULT FALSE,
                accepted_at TIMESTAMPTZ,
                accepted_by_user_id UUID REFERENCES users(id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        ))
    else:
        op.create_table(
            "monthly_capsules",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("iso_month", sa.String(7), nullable=False, unique=True),
            sa.Column("proposal", sa.JSON(), nullable=False),
            sa.Column(
                "used_llm", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "accepted_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )


def downgrade() -> None:
    op.drop_table("monthly_capsules")
