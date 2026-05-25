"""Accounting module — new tables + transaction columns

Revision ID: 0047
Revises: 0046
Create Date: 2026-05-25

Crée les trois tables du module comptable (accounting_configs,
accounting_exports, accounting_export_lines) et ajoute deux colonnes
sur la table transactions existante (accounting_locked, accounting_export_id).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── accounting_configs ────────────────────────────────────────────────────
    op.create_table(
        "accounting_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("account_sales", sa.String(20), nullable=False, server_default="707100"),
        sa.Column("account_tva", sa.String(20), nullable=False, server_default="44571"),
        sa.Column("tva_rate", sa.Numeric(5, 2), nullable=False, server_default="20.00"),
        sa.Column("account_cash", sa.String(20), nullable=False, server_default="531000"),
        sa.Column("account_card", sa.String(20), nullable=False, server_default="512000"),
        sa.Column("account_cheque", sa.String(20), nullable=False, server_default="511000"),
        sa.Column("account_cheque_cdc", sa.String(20), nullable=False, server_default="511001"),
        sa.Column("account_avoir", sa.String(20), nullable=False, server_default="419000"),
        sa.Column("account_transfer", sa.String(20), nullable=False, server_default="512001"),
        sa.Column("label_sales", sa.String(100), nullable=False, server_default="Ventes marchandises"),
        sa.Column("label_tva", sa.String(100), nullable=False, server_default="TVA collectée 20%"),
        sa.Column("label_cash", sa.String(100), nullable=False, server_default="Caisse"),
        sa.Column("label_card", sa.String(100), nullable=False, server_default="CB SumUp"),
        sa.Column("label_cheque", sa.String(100), nullable=False, server_default="Chèques à encaisser"),
        sa.Column("label_cheque_cdc", sa.String(100), nullable=False, server_default="Club des Commerçants"),
        sa.Column("label_avoir", sa.String(100), nullable=False, server_default="Avoirs clients"),
        sa.Column("label_transfer", sa.String(100), nullable=False, server_default="Virement"),
        sa.Column("pennylane_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("pennylane_api_key", sa.String(512), nullable=True),
        sa.Column("pennylane_journal_code", sa.String(20), nullable=False, server_default="VTE"),
        sa.Column("pennylane_api_url", sa.String(255), nullable=False,
                  server_default="https://app.pennylane.com/api/external/v1"),
        sa.Column("discrepancy_alert_threshold", sa.Numeric(10, 2), nullable=False, server_default="5.00"),
        sa.Column("discrepancy_alert_email", sa.String(255), nullable=True),
        sa.Column("daily_report_email", sa.String(255), nullable=False, server_default="vernon@vintiz.fr"),
        sa.Column("daily_report_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("fec_monthly_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── export_status enum ───────────────────────────────────────────────────
    op.execute("CREATE TYPE export_status AS ENUM ('pending','exported','failed','manual')")

    # ── accounting_exports ────────────────────────────────────────────────────
    op.create_table(
        "accounting_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("z_report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("export_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Enum("pending", "exported", "failed", "manual", name="export_status"),
                  nullable=False, server_default="pending"),
        sa.Column("pennylane_ledger_event_id", sa.String(128), nullable=True),
        sa.Column("pennylane_exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pennylane_error", sa.Text(), nullable=True),
        sa.Column("pennylane_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fec_content", sa.Text(), nullable=True),
        sa.Column("fec_filename", sa.String(255), nullable=True),
        sa.Column("fec_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_sales_ht", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_tva", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_sales_ttc", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_refunds_ttc", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_ttc", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refund_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cash_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("card_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cheque_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cheque_cdc_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("avoir_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("transfer_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cash_expected", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_counted", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_discrepancy", sa.Numeric(12, 2), nullable=True),
        sa.Column("discrepancy_alert_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_sent_to", sa.String(255), nullable=True),
        sa.Column("exported_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["z_report_id"], ["z_reports.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["exported_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("z_report_id"),
    )

    # ── accounting_export_lines ───────────────────────────────────────────────
    op.create_table(
        "accounting_export_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("export_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("account_number", sa.String(20), nullable=False),
        sa.Column("account_label", sa.String(100), nullable=False),
        sa.Column("debit", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("piece_reference", sa.String(50), nullable=True),
        sa.Column("piece_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["export_id"], ["accounting_exports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── transactions — 2 nouvelles colonnes ──────────────────────────────────
    op.add_column(
        "transactions",
        sa.Column("accounting_locked", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "transactions",
        sa.Column("accounting_export_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "accounting_export_id")
    op.drop_column("transactions", "accounting_locked")
    op.drop_table("accounting_export_lines")
    op.drop_table("accounting_exports")
    op.drop_table("accounting_configs")
    op.execute("DROP TYPE IF EXISTS export_status")
