"""Accounting module — new tables + transaction columns

Revision ID: 0047
Revises: 0046
Create Date: 2026-05-25

Crée les trois tables du module comptable et ajoute deux colonnes sur
transactions. Idempotent : utilise IF NOT EXISTS partout pour survivre
au cas où create_all a déjà créé les tables au premier démarrage.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── enum export_status (IF NOT EXISTS via DO block) ───────────────────────
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE export_status AS ENUM ('pending','exported','failed','manual');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))

    # ── accounting_configs ────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS accounting_configs (
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            account_sales VARCHAR(20) NOT NULL DEFAULT '707100',
            account_tva VARCHAR(20) NOT NULL DEFAULT '44571',
            tva_rate NUMERIC(5,2) NOT NULL DEFAULT 20.00,
            account_cash VARCHAR(20) NOT NULL DEFAULT '531000',
            account_card VARCHAR(20) NOT NULL DEFAULT '512000',
            account_cheque VARCHAR(20) NOT NULL DEFAULT '511000',
            account_cheque_cdc VARCHAR(20) NOT NULL DEFAULT '511001',
            account_avoir VARCHAR(20) NOT NULL DEFAULT '419000',
            account_transfer VARCHAR(20) NOT NULL DEFAULT '512001',
            label_sales VARCHAR(100) NOT NULL DEFAULT 'Ventes marchandises',
            label_tva VARCHAR(100) NOT NULL DEFAULT 'TVA collectée 20%',
            label_cash VARCHAR(100) NOT NULL DEFAULT 'Caisse',
            label_card VARCHAR(100) NOT NULL DEFAULT 'CB SumUp',
            label_cheque VARCHAR(100) NOT NULL DEFAULT 'Chèques à encaisser',
            label_cheque_cdc VARCHAR(100) NOT NULL DEFAULT 'Club des Commerçants',
            label_avoir VARCHAR(100) NOT NULL DEFAULT 'Avoirs clients',
            label_transfer VARCHAR(100) NOT NULL DEFAULT 'Virement',
            pennylane_enabled BOOLEAN NOT NULL DEFAULT false,
            pennylane_api_key VARCHAR(512),
            pennylane_journal_code VARCHAR(20) NOT NULL DEFAULT 'VTE',
            pennylane_api_url VARCHAR(255) NOT NULL DEFAULT 'https://app.pennylane.com/api/external/v1',
            discrepancy_alert_threshold NUMERIC(10,2) NOT NULL DEFAULT 5.00,
            discrepancy_alert_email VARCHAR(255),
            daily_report_email VARCHAR(255) NOT NULL DEFAULT 'vernon@vintiz.fr',
            daily_report_enabled BOOLEAN NOT NULL DEFAULT true,
            fec_monthly_enabled BOOLEAN NOT NULL DEFAULT true
        )
    """))

    # ── accounting_exports ────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS accounting_exports (
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            z_report_id UUID NOT NULL REFERENCES z_reports(id) ON DELETE RESTRICT,
            export_date DATE NOT NULL,
            status export_status NOT NULL DEFAULT 'pending',
            pennylane_ledger_event_id VARCHAR(128),
            pennylane_exported_at TIMESTAMPTZ,
            pennylane_error TEXT,
            pennylane_attempts INTEGER NOT NULL DEFAULT 0,
            fec_content TEXT,
            fec_filename VARCHAR(255),
            fec_generated_at TIMESTAMPTZ,
            total_sales_ht NUMERIC(12,2) NOT NULL DEFAULT 0,
            total_tva NUMERIC(12,2) NOT NULL DEFAULT 0,
            total_sales_ttc NUMERIC(12,2) NOT NULL DEFAULT 0,
            total_refunds_ttc NUMERIC(12,2) NOT NULL DEFAULT 0,
            net_ttc NUMERIC(12,2) NOT NULL DEFAULT 0,
            transaction_count INTEGER NOT NULL DEFAULT 0,
            refund_count INTEGER NOT NULL DEFAULT 0,
            cash_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            card_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            cheque_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            cheque_cdc_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            avoir_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            transfer_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            cash_expected NUMERIC(12,2),
            cash_counted NUMERIC(12,2),
            cash_discrepancy NUMERIC(12,2),
            discrepancy_alert_sent BOOLEAN NOT NULL DEFAULT false,
            email_sent_at TIMESTAMPTZ,
            email_sent_to VARCHAR(255),
            exported_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            locked_at TIMESTAMPTZ,
            CONSTRAINT uq_accounting_exports_z_report UNIQUE (z_report_id)
        )
    """))

    # ── accounting_export_lines ───────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS accounting_export_lines (
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            export_id UUID NOT NULL REFERENCES accounting_exports(id) ON DELETE CASCADE,
            line_number INTEGER NOT NULL,
            account_number VARCHAR(20) NOT NULL,
            account_label VARCHAR(100) NOT NULL,
            debit NUMERIC(12,2) NOT NULL DEFAULT 0,
            credit NUMERIC(12,2) NOT NULL DEFAULT 0,
            label VARCHAR(255) NOT NULL,
            piece_reference VARCHAR(50),
            piece_date DATE
        )
    """))

    # ── transactions : colonnes comptables (ADD COLUMN IF NOT EXISTS) ─────────
    conn.execute(sa.text("""
        ALTER TABLE transactions
            ADD COLUMN IF NOT EXISTS accounting_locked BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS accounting_export_id UUID
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE transactions DROP COLUMN IF EXISTS accounting_export_id"))
    conn.execute(sa.text("ALTER TABLE transactions DROP COLUMN IF EXISTS accounting_locked"))
    conn.execute(sa.text("DROP TABLE IF EXISTS accounting_export_lines"))
    conn.execute(sa.text("DROP TABLE IF EXISTS accounting_exports"))
    conn.execute(sa.text("DROP TABLE IF EXISTS accounting_configs"))
    conn.execute(sa.text("DROP TYPE IF EXISTS export_status"))
