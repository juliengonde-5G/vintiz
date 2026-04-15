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
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    card = "card"
    cheque = "cheque"
    transfer = "transfer"


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
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True
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
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    discount_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    line_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

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


class ZReport(Base):
    __tablename__ = "z_reports"

    report_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
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
