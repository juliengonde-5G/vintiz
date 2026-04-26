"""add clients.rfm_segment (P4-007)

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-26

Idempotent like prior migrations.
"""

from alembic import op
import sqlalchemy as sa


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).fetchone() is not None


def upgrade() -> None:
    if not _column_exists("clients", "rfm_segment"):
        op.add_column(
            "clients",
            sa.Column("rfm_segment", sa.String(length=20), nullable=True),
        )
        op.create_index(
            "ix_clients_rfm_segment",
            "clients",
            ["rfm_segment"],
        )


def downgrade() -> None:
    if _column_exists("clients", "rfm_segment"):
        op.drop_index("ix_clients_rfm_segment", table_name="clients")
        op.drop_column("clients", "rfm_segment")
