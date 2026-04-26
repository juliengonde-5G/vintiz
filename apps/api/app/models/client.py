import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LoyaltyTxType(str, enum.Enum):
    earn = "earn"
    redeem = "redeem"
    adjust = "adjust"


class AvoirTxType(str, enum.Enum):
    credit = "credit"  # Issued from a refund — increases client balance
    debit = "debit"    # Spent at checkout — decreases client balance
    adjust = "adjust"  # Manual adjustment by manager


class Client(Base):
    __tablename__ = "clients"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_optin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sms_optin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Store credit (avoir) balance — incremented on refunds with method "avoir",
    # decremented when used at checkout. AvoirTransaction holds the audit trail.
    avoir_credit: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )

    loyalty_account: Mapped["LoyaltyAccount | None"] = relationship(
        "LoyaltyAccount", back_populates="client", uselist=False, lazy="selectin"
    )


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), unique=True, nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tier: Mapped[str] = mapped_column(String(50), nullable=False, default="bronze")

    client: Mapped["Client"] = relationship(
        "Client", back_populates="loyalty_account", lazy="selectin"
    )
    transactions: Mapped[list["LoyaltyTransaction"]] = relationship(
        "LoyaltyTransaction", back_populates="account", lazy="selectin"
    )


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loyalty_accounts.id"), nullable=False
    )
    tx_type: Mapped[LoyaltyTxType] = mapped_column(
        Enum(LoyaltyTxType, name="loyalty_tx_type"), nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped["LoyaltyAccount"] = relationship(
        "LoyaltyAccount", back_populates="transactions", lazy="selectin"
    )


class AvoirTransaction(Base):
    """Append-only ledger of avoir credits and debits.

    Sums of (credit - debit) by client_id reproduce Client.avoir_credit and
    serve as the audit trail required by NF525 for refunds settled in
    store credit.
    """

    __tablename__ = "avoir_transactions"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )
    tx_type: Mapped[AvoirTxType] = mapped_column(
        Enum(AvoirTxType, name="avoir_tx_type"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
