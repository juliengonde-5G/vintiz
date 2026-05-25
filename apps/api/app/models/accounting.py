"""Accounting models — plan de comptes, exports Pennylane, journal interne."""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ExportStatus(str, enum.Enum):
    pending = "pending"
    exported = "exported"
    failed = "failed"
    manual = "manual"   # exported via file download, no Pennylane push


class AccountingConfig(Base):
    """Paramétrage comptable boutique — singleton (un seul enregistrement).

    Stocke le plan de comptes PCG + credentials Pennylane. Les valeurs sont
    proposées vides à l'installation et renseignées depuis
    /settings/comptabilite.
    """

    __tablename__ = "accounting_configs"

    # ── Comptes de recettes ──────────────────────────────────────────────────
    account_sales: Mapped[str] = mapped_column(String(20), nullable=False, default="707100")
    account_tva: Mapped[str] = mapped_column(String(20), nullable=False, default="44571")
    tva_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=20.00)

    # ── Comptes d'encaissement par mode de paiement ──────────────────────────
    account_cash: Mapped[str] = mapped_column(String(20), nullable=False, default="531000")
    account_card: Mapped[str] = mapped_column(String(20), nullable=False, default="512000")
    account_cheque: Mapped[str] = mapped_column(String(20), nullable=False, default="511000")
    account_cheque_cdc: Mapped[str] = mapped_column(String(20), nullable=False, default="511001")
    account_avoir: Mapped[str] = mapped_column(String(20), nullable=False, default="419000")
    account_transfer: Mapped[str] = mapped_column(String(20), nullable=False, default="512001")

    # ── Libellés des comptes ─────────────────────────────────────────────────
    label_sales: Mapped[str] = mapped_column(String(100), nullable=False, default="Ventes marchandises")
    label_tva: Mapped[str] = mapped_column(String(100), nullable=False, default="TVA collectée 20%")
    label_cash: Mapped[str] = mapped_column(String(100), nullable=False, default="Caisse")
    label_card: Mapped[str] = mapped_column(String(100), nullable=False, default="CB SumUp")
    label_cheque: Mapped[str] = mapped_column(String(100), nullable=False, default="Chèques à encaisser")
    label_cheque_cdc: Mapped[str] = mapped_column(String(100), nullable=False, default="Club des Commerçants")
    label_avoir: Mapped[str] = mapped_column(String(100), nullable=False, default="Avoirs clients")
    label_transfer: Mapped[str] = mapped_column(String(100), nullable=False, default="Virement")

    # ── Pennylane ────────────────────────────────────────────────────────────
    pennylane_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pennylane_api_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pennylane_journal_code: Mapped[str] = mapped_column(String(20), nullable=False, default="VTE")
    pennylane_api_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="https://app.pennylane.com/api/external/v1",
    )

    # ── Alertes ──────────────────────────────────────────────────────────────
    discrepancy_alert_threshold: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=5.00
    )
    discrepancy_alert_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Email rapport quotidien ───────────────────────────────────────────────
    daily_report_email: Mapped[str] = mapped_column(
        String(255), nullable=False, default="vernon@vintiz.fr"
    )
    daily_report_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── FEC mensuel ──────────────────────────────────────────────────────────
    fec_monthly_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AccountingExport(Base):
    """Un export comptable = une clôture Z-report."""

    __tablename__ = "accounting_exports"

    z_report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("z_reports.id"), nullable=False, unique=True
    )
    export_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ExportStatus] = mapped_column(
        Enum(ExportStatus, name="export_status"),
        nullable=False,
        default=ExportStatus.pending,
    )

    # ── Pennylane ────────────────────────────────────────────────────────────
    pennylane_ledger_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pennylane_exported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pennylane_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    pennylane_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── FEC daily file (stocké en BDD pour re-téléchargement) ───────────────
    fec_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    fec_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fec_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Totaux consolidés ────────────────────────────────────────────────────
    total_sales_ht: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total_tva: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total_sales_ttc: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total_refunds_ttc: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    net_ttc: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    transaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refund_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Par méthode de paiement ─────────────────────────────────────────────
    cash_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    card_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    cheque_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    cheque_cdc_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    avoir_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    transfer_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    # ── Contrôle de caisse ───────────────────────────────────────────────────
    cash_expected: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    cash_counted: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    cash_discrepancy: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    discrepancy_alert_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Email rapport ────────────────────────────────────────────────────────
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_sent_to: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Traçabilité ──────────────────────────────────────────────────────────
    exported_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["AccountingExportLine"]] = relationship(
        "AccountingExportLine", back_populates="export", lazy="selectin"
    )


class AccountingExportLine(Base):
    """Ligne d'écriture comptable (journal interne)."""

    __tablename__ = "accounting_export_lines"

    export_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_exports.id"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_label: Mapped[str] = mapped_column(String(100), nullable=False)
    debit: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    credit: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    piece_reference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    piece_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    export: Mapped["AccountingExport"] = relationship(
        "AccountingExport", back_populates="lines"
    )
