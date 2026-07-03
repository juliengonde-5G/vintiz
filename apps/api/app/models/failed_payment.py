"""Failed-payment queue — CB checkouts that failed *recoverably*.

Groundwork for the offline mode (Phase 2). When a card checkout fails for a
transient reason (terminal offline/busy, SumUp outage, network blip) the sale
would otherwise be lost. ``FailedPayment`` persists just enough to **re-attempt
it later** — automatically (cron every few minutes) or manually from the caisse
— by re-creating a payment-link checkout the customer can settle.

This is intentionally decoupled from the NF525 ``Transaction`` chain: a row here
is *not* a sale. ``transaction_id`` stays NULL until a retry actually succeeds
and a real Transaction is committed (wired in Phase 2). Rows are retained (not
deleted) with a terminal ``status`` so the back-office keeps an audit trail of
what failed and how it resolved — same append-only philosophy as
``PaymentAttempt``.

Security: ``error_detail`` is always stored through ``redact_sumup_error`` by
the writer (no PAN / CVV / token).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FailedPaymentStatus(str, enum.Enum):
    pending = "pending"      # awaiting the next retry
    succeeded = "succeeded"  # a retry created a valid checkout
    exhausted = "exhausted"  # max_attempts reached, still failing
    abandoned = "abandoned"  # cashier / manager gave up on it


class FailedPayment(Base):
    __tablename__ = "failed_payments"

    # NB: id / created_at / updated_at come from Base.
    # Linked Transaction once a retry succeeds (Phase 2). Plain nullable UUID —
    # kept decoupled from the transactions table so this queue can be pruned or
    # migrated independently of the fiscal chain.
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    checkout_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    foreign_transaction_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Redacted last error seen (never raw PAN/CVV/token).
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[FailedPaymentStatus] = mapped_column(
        Enum(
            FailedPaymentStatus,
            name="failed_payment_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=FailedPaymentStatus.pending,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_checkout_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    # When False the row is a dead letter we never auto-retry (definitive
    # failure captured for audit only).
    is_recoverable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    reader_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cashier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
