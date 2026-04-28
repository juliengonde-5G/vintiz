"""PR2: trend_alerts consent purpose + clients.last_trend_alert_at.

- Adds ``trend_alerts`` to the ``consent_purpose`` enum (PostgreSQL).
- Adds ``clients.last_trend_alert_at`` (DateTime) for frequency capping.

Revision ID: 0032
Revises: 0031
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Extend consent_purpose enum on PostgreSQL (no-op on SQLite — type is plain text).
    if is_pg:
        op.execute(
            "ALTER TYPE consent_purpose ADD VALUE IF NOT EXISTS 'trend_alerts'"
        )

    # 2. clients.last_trend_alert_at (frequency cap for trend_alerts cron).
    if "clients" in existing_tables:
        client_cols = {c["name"] for c in inspector.get_columns("clients")}
        if "last_trend_alert_at" not in client_cols:
            op.add_column(
                "clients",
                sa.Column(
                    "last_trend_alert_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "clients" in existing_tables:
        client_cols = {c["name"] for c in inspector.get_columns("clients")}
        if "last_trend_alert_at" in client_cols:
            op.drop_column("clients", "last_trend_alert_at")

    # Postgres enums can't drop a value cleanly without rewriting the type;
    # leave the value in place. New rows just won't reference it.
