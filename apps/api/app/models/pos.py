import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.types import JSONType


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    card = "card"
    cheque = "cheque"
    transfer = "transfer"
    avoir = "avoir"  # Settled from the client's store-credit balance


class TransactionType(str, enum.Enum):
    sale = "sale"
    refund = "refund"
    void = "void"


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_number: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, autoincrement=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type"),
        nullable=False,
        default=TransactionType.sale,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # Cashier physically at the till (NF525 traceability). Nullable for legacy
    # rows pre-migration; new transactions must always set it.
    cashier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True
    )
    # For refund transactions: link to the original sale (NF525 traceability,
    # also lets the API compute "remaining refundable amount").
    original_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )
    refund_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Client-generated UUID for idempotent submission. The POS UI generates
    # this BEFORE the transaction is sent so that a network retry / offline
    # queue replay can be deduplicated server-side. Nullable for legacy
    # transactions; new submissions from the POS should always set it.
    client_uuid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=True
    )
    # B2B invoice mode (added 2026-05). When ``is_invoice=True`` the
    # transaction gets a separate ``invoice_number`` (FACT-{year}-{seq:06d})
    # and the receipt template renders the buyer's SIRET + company + a
    # detailed VAT breakdown. ``template_id`` is a snapshot pointer so a
    # later edit on the template doesn't retro-actively change historical
    # tickets.
    is_invoice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invoice_number: Mapped[int | None] = mapped_column(
        Integer, unique=True, nullable=True
    )
    client_siret: Mapped[str | None] = mapped_column(String(14), nullable=True)
    client_company_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    client_billing_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("receipt_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    total_ht: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_tva: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_ttc: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    hash_chain: Mapped[str] = mapped_column(String(64), nullable=False)

    items: Mapped[list["TransactionItem"]] = relationship(
        "TransactionItem", back_populates="transaction", lazy="selectin"
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="transaction", lazy="selectin"
    )
    receipt: Mapped["Receipt | None"] = relationship(
        "Receipt", back_populates="transaction", uselist=False, lazy="selectin"
    )


class TransactionItem(Base):
    __tablename__ = "transaction_items"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )
    # Set on refund items only — points back to the original sale's item
    # so partial refunds aggregate per *line*, not per product. Without it
    # two distinct lines that share the same product_id would share the
    # refund quota and the second refund would be wrongly rejected.
    original_transaction_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transaction_items.id"),
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    discount_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    line_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # Taux de TVA effectivement appliqué à cette ligne — figé au moment
    # de la vente même si le taux du Product change ensuite. Permet de
    # justifier le calcul HT/TVA/TTC lors d'un contrôle DGFiP, et de
    # produire des tickets / factures conformes (CGI art. 286).
    tva_rate: Mapped[float] = mapped_column(
        Numeric(4, 2), nullable=False, default=20.00
    )

    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="items", lazy="selectin"
    )
    product: Mapped["Product | None"] = relationship(  # noqa: F821
        "Product", lazy="selectin"
    )


class Payment(Base):
    __tablename__ = "payments"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False
    )
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="payments", lazy="selectin"
    )


class CashDrawer(Base):
    __tablename__ = "cash_drawers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    cashier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opening_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    closing_amount: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    expected_amount: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Detailed denomination breakdown captured at open / close time.
    # Shape: ``[{"denom": 50, "count": 5}, {"denom": 20, "count": 10}, ...]``
    # Optional — the POS still supports a "quick" mode where only the total is
    # entered. When present it lets the Z report PDF show an itemised count
    # and helps the cashier recover from a discrepancy alert.
    opening_breakdown: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    closing_breakdown: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    closing_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Per-drawer override of the global allowed discrepancy (Settings).
    # When the cashier closes with |closing - expected| > allowed_discrepancy,
    # the UI forces a mandatory note and surfaces a red alert on the Z report.
    allowed_discrepancy: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )


class ZReport(Base):
    __tablename__ = "z_reports"

    report_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    cashier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    cash_drawer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_drawers.id"), nullable=False
    )
    total_sales: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    total_refunds: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    total_net: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    transaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # NF525 intangibility (article 88 CGI) — once ``is_locked=True`` the row
    # may not be updated. The PDF + its SHA-256 are persisted at lock time so
    # any later display reproduces byte-identical output. Email send is also
    # recorded for the audit trail (Z report dispatched to comptable).
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    pdf_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    emailed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    emailed_to: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Receipt(Base):
    __tablename__ = "receipts"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), unique=True, nullable=False
    )
    receipt_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    printed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="receipt", lazy="selectin"
    )
