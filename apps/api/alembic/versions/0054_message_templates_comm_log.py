"""Message templates + communication log

Revision ID: 0054
Revises: 0053
Create Date: 2026-05-30

Deux tables additives pour la personnalisation des communications client :
- message_templates : objets/corps éditables en admin pour les messages
  automatiques (anniversaire, nouveautés, alerte tendance, confirmation
  consentement). Repli code si absent/inactif → non bloquant.
- communication_logs : journal des emails/SMS envoyés à un client, affiché
  sur la fiche client.

Idempotent (IF NOT EXISTS). Aucune donnée existante touchée.
"""

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        """
        CREATE TABLE IF NOT EXISTS message_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key VARCHAR(64) NOT NULL UNIQUE,
            channel VARCHAR(10) NOT NULL DEFAULT 'email',
            label VARCHAR(120) NOT NULL,
            description TEXT,
            subject TEXT,
            body_html TEXT,
            body_text TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    ))
    conn.execute(sa.text(
        """
        CREATE TABLE IF NOT EXISTS communication_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id UUID REFERENCES clients(id),
            channel VARCHAR(10) NOT NULL,
            kind VARCHAR(40) NOT NULL,
            to_address VARCHAR(255),
            subject TEXT,
            status VARCHAR(12) NOT NULL,
            backend VARCHAR(20),
            detail TEXT,
            template_key VARCHAR(64),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_communication_logs_client_id "
        "ON communication_logs (client_id);"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS communication_logs;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS message_templates;"))
