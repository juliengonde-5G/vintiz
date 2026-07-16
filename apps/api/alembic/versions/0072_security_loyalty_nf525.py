"""Security, loyalty and NF525 hardening.

Revision ID: 0072
Revises: 0071
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    statements = (
        "ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS foreign_transaction_id VARCHAR(120)",
        "CREATE INDEX IF NOT EXISTS ix_payment_attempts_foreign_transaction_id ON payment_attempts (foreign_transaction_id)",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS tendered_amount NUMERIC(10,2)",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS previous_hash VARCHAR(64)",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS fiscal_signature_version INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE transactions ALTER COLUMN fiscal_signature_version SET DEFAULT 2",
        "ALTER TABLE z_reports ADD COLUMN IF NOT EXISTS fiscal_signature_version INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE z_reports ALTER COLUMN fiscal_signature_version SET DEFAULT 2",
        "ALTER TABLE z_reports ADD COLUMN IF NOT EXISTS first_transaction_number INTEGER",
        "ALTER TABLE z_reports ADD COLUMN IF NOT EXISTS last_transaction_number INTEGER",
        "ALTER TABLE z_reports ADD COLUMN IF NOT EXISTS last_transaction_hash VARCHAR(64)",
        "ALTER TABLE z_reports ADD COLUMN IF NOT EXISTS payment_totals JSONB",
        "ALTER TABLE loyalty_transactions ADD COLUMN IF NOT EXISTS transaction_id UUID REFERENCES transactions(id)",
        "ALTER TABLE loyalty_transactions ADD COLUMN IF NOT EXISTS reversal_of_id UUID REFERENCES loyalty_transactions(id)",
        "CREATE INDEX IF NOT EXISTS ix_loyalty_transactions_transaction_id ON loyalty_transactions (transaction_id)",
        """
        INSERT INTO app_settings (id, key, value, description, created_at, updated_at)
        VALUES (gen_random_uuid(), 'loyalty_voucher_value_cents', '500',
                'Promesse boutique : chèque cadeau de 5 euros par palier de 100 points',
                now(), now())
        ON CONFLICT (key) DO UPDATE SET value = '500', updated_at = now()
        """,
        """
        UPDATE message_templates
        SET body_html = replace(body_html, '7 €', '5 €'),
            body_text = replace(body_text, '7 €', '5 €'),
            updated_at = now()
        WHERE key = 'welcome_subscription'
          AND (body_html LIKE '%7 €%' OR body_text LIKE '%7 €%')
        """,
        """
        CREATE TABLE IF NOT EXISTS fiscal_closures (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sequence_number INTEGER NOT NULL UNIQUE,
            closure_type VARCHAR(20) NOT NULL,
            period_start TIMESTAMPTZ NOT NULL,
            period_end TIMESTAMPTZ NOT NULL,
            software_version VARCHAR(32) NOT NULL,
            transaction_count INTEGER NOT NULL,
            first_transaction_number INTEGER,
            last_transaction_number INTEGER,
            last_transaction_hash VARCHAR(64),
            last_z_hash VARCHAR(64),
            previous_hash VARCHAR(64) NOT NULL,
            hash VARCHAR(64) NOT NULL,
            signature_version INTEGER NOT NULL DEFAULT 1,
            archive_sha256 VARCHAR(64) NOT NULL,
            archive_content BYTEA NOT NULL,
            manifest JSONB NOT NULL,
            closed_by_user_id UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_fiscal_closure_period UNIQUE (closure_type, period_start, period_end)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_fiscal_closures_period ON fiscal_closures (period_start, period_end)",
    )
    for statement in statements:
        conn.execute(sa.text(statement))

    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION vintiz_protect_signed_transaction()
        RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            IF COALESCE(OLD.hash_chain, '') <> '' THEN
              RAISE EXCEPTION 'NF525: suppression transaction signee interdite';
            END IF;
            RETURN OLD;
          END IF;
          IF COALESCE(OLD.hash_chain, '') <> '' AND (
            OLD.transaction_number IS DISTINCT FROM NEW.transaction_number OR
            OLD.transaction_type IS DISTINCT FROM NEW.transaction_type OR
            OLD.user_id IS DISTINCT FROM NEW.user_id OR
            OLD.cashier_id IS DISTINCT FROM NEW.cashier_id OR
            OLD.original_transaction_id IS DISTINCT FROM NEW.original_transaction_id OR
            OLD.refund_reason IS DISTINCT FROM NEW.refund_reason OR
            OLD.client_uuid IS DISTINCT FROM NEW.client_uuid OR
            OLD.total_ht IS DISTINCT FROM NEW.total_ht OR
            OLD.total_tva IS DISTINCT FROM NEW.total_tva OR
            OLD.total_ttc IS DISTINCT FROM NEW.total_ttc OR
            OLD.is_invoice IS DISTINCT FROM NEW.is_invoice OR
            OLD.invoice_number IS DISTINCT FROM NEW.invoice_number OR
            OLD.client_siret IS DISTINCT FROM NEW.client_siret OR
            OLD.client_company_name IS DISTINCT FROM NEW.client_company_name OR
            OLD.client_billing_address IS DISTINCT FROM NEW.client_billing_address OR
            OLD.template_id IS DISTINCT FROM NEW.template_id OR
            OLD.created_at IS DISTINCT FROM NEW.created_at OR
            OLD.previous_hash IS DISTINCT FROM NEW.previous_hash OR
            OLD.fiscal_signature_version IS DISTINCT FROM NEW.fiscal_signature_version OR
            OLD.hash_chain IS DISTINCT FROM NEW.hash_chain
          ) THEN
            RAISE EXCEPTION 'NF525: modification transaction signee interdite';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_protect_signed_transaction ON transactions;
        CREATE TRIGGER trg_protect_signed_transaction
        BEFORE UPDATE OR DELETE ON transactions
        FOR EACH ROW EXECUTE FUNCTION vintiz_protect_signed_transaction();
    """))

    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION vintiz_protect_fiscal_child()
        RETURNS trigger AS $$
        DECLARE tx_id UUID; tx_hash VARCHAR(64);
        BEGIN
          tx_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.transaction_id ELSE NEW.transaction_id END;
          SELECT hash_chain INTO tx_hash FROM transactions WHERE id = tx_id;
          IF COALESCE(tx_hash, '') <> '' THEN
            RAISE EXCEPTION 'NF525: lignes/paiements d une transaction signee immuables';
          END IF;
          RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_protect_transaction_items ON transaction_items;
        CREATE TRIGGER trg_protect_transaction_items
        BEFORE INSERT OR UPDATE OR DELETE ON transaction_items
        FOR EACH ROW EXECUTE FUNCTION vintiz_protect_fiscal_child();

        DROP TRIGGER IF EXISTS trg_protect_payments ON payments;
        CREATE TRIGGER trg_protect_payments
        BEFORE INSERT OR UPDATE OR DELETE ON payments
        FOR EACH ROW EXECUTE FUNCTION vintiz_protect_fiscal_child();
    """))

    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION vintiz_protect_z_report()
        RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'NF525: suppression Z interdite';
          END IF;
          IF (
            OLD.report_number IS DISTINCT FROM NEW.report_number OR
            OLD.user_id IS DISTINCT FROM NEW.user_id OR
            OLD.cashier_id IS DISTINCT FROM NEW.cashier_id OR
            OLD.cash_drawer_id IS DISTINCT FROM NEW.cash_drawer_id OR
            OLD.total_sales IS DISTINCT FROM NEW.total_sales OR
            OLD.total_refunds IS DISTINCT FROM NEW.total_refunds OR
            OLD.total_net IS DISTINCT FROM NEW.total_net OR
            OLD.transaction_count IS DISTINCT FROM NEW.transaction_count OR
            OLD.first_transaction_number IS DISTINCT FROM NEW.first_transaction_number OR
            OLD.last_transaction_number IS DISTINCT FROM NEW.last_transaction_number OR
            OLD.last_transaction_hash IS DISTINCT FROM NEW.last_transaction_hash OR
            OLD.payment_totals IS DISTINCT FROM NEW.payment_totals OR
            OLD.hash IS DISTINCT FROM NEW.hash OR
            OLD.previous_hash IS DISTINCT FROM NEW.previous_hash OR
            OLD.fiscal_signature_version IS DISTINCT FROM NEW.fiscal_signature_version OR
            OLD.is_regularization IS DISTINCT FROM NEW.is_regularization OR
            OLD.regularization_reason IS DISTINCT FROM NEW.regularization_reason OR
            OLD.created_at IS DISTINCT FROM NEW.created_at
          ) THEN
            RAISE EXCEPTION 'NF525: modification donnees scellees Z interdite';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        DROP TRIGGER IF EXISTS trg_protect_z_report ON z_reports;
        CREATE TRIGGER trg_protect_z_report
        BEFORE UPDATE OR DELETE ON z_reports
        FOR EACH ROW EXECUTE FUNCTION vintiz_protect_z_report();
    """))

    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION vintiz_protect_closed_drawer_period()
        RETURNS trigger AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM z_reports WHERE cash_drawer_id = OLD.id) AND (
            OLD.opened_at IS DISTINCT FROM NEW.opened_at OR
            OLD.closed_at IS DISTINCT FROM NEW.closed_at
          ) THEN
            RAISE EXCEPTION 'NF525: periode tiroir cloturee immuable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        DROP TRIGGER IF EXISTS trg_protect_closed_drawer_period ON cash_drawers;
        CREATE TRIGGER trg_protect_closed_drawer_period
        BEFORE UPDATE ON cash_drawers
        FOR EACH ROW EXECUTE FUNCTION vintiz_protect_closed_drawer_period();

        CREATE OR REPLACE FUNCTION vintiz_protect_fiscal_closure()
        RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'NF525: cloture fiscale immuable';
        END;
        $$ LANGUAGE plpgsql;
        DROP TRIGGER IF EXISTS trg_protect_fiscal_closure ON fiscal_closures;
        CREATE TRIGGER trg_protect_fiscal_closure
        BEFORE UPDATE OR DELETE ON fiscal_closures
        FOR EACH ROW EXECUTE FUNCTION vintiz_protect_fiscal_closure();
    """))


def downgrade() -> None:
    # This revision creates the fiscal evidence chain. Dropping its triggers,
    # signatures or archives would itself violate the immutability guarantees
    # the revision introduces. Recovery must therefore restore a pre-upgrade
    # database backup; an in-place Alembic downgrade is intentionally refused.
    raise RuntimeError(
        "Revision 0072 is an irreversible fiscal migration; restore a "
        "pre-upgrade backup instead of downgrading in place."
    )
