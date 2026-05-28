"""Database backup manager — backups ledger + singleton config

Revision ID: 0049
Revises: 0048
Create Date: 2026-05-28

Tables du gestionnaire de base de données (admin) : ``database_backups``
(une ligne par dump, listable + téléchargeable) et ``database_backup_configs``
(singleton : rétention, email d'alerte, activation du cron nocturne).
Idempotent (IF NOT EXISTS).
"""

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS database_backups (
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            filename VARCHAR(255) NOT NULL,
            path TEXT NOT NULL,
            size_bytes INTEGER,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            trigger VARCHAR(20) NOT NULL DEFAULT 'manual',
            db_engine VARCHAR(20),
            error TEXT,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            duration_ms INTEGER
        );
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_database_backups_created_at "
        "ON database_backups (created_at DESC);"
    ))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS database_backup_configs (
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            retention_days INTEGER NOT NULL DEFAULT 30,
            alert_email VARCHAR(255),
            enabled BOOLEAN NOT NULL DEFAULT true
        );
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS database_backups;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS database_backup_configs;"))
