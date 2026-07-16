"""Payment attempt log — every initiated payment, succeeded or failed.

Vintiz's NF525 ``Transaction`` row is created only when a sale commits
(idempotent via ``client_uuid``) — so failed CB tries, cancelled cash
entries, abandoned baskets used to leave **zero** trace. This makes
debugging "the TPE didn't work this morning" impossible.

``PaymentAttempt`` plugs that gap without polluting NF525:
- One row per attempted payment (CB initiate, cash submit, cheque entry, avoir).
- ``transaction_id`` stays NULL until the sale commits — only succeeded
  attempts that landed in a real Transaction get linked.
- Provides the data for ``/admin/payment-attempts`` (debugging) and
  ``/admin/transactions`` (full history filterable by status).

Read-only ledger: rows are inserted, never updated except for the
``status`` transition pending → succeeded|failed|cancelled.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.pos import PaymentMethod


class PaymentAttemptStatus(str, enum.Enum):
    pending = "pending"        # CB initiated, awaiting reader / cash entered, awaiting commit
    succeeded = "succeeded"    # paid + bound to a Transaction (transaction_id set)
    failed = "failed"          # SumUp FAILED, network error, cashier cancelled
    cancelled = "cancelled"    # cashier explicitly cancelled the attempt


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[PaymentAttemptStatus] = mapped_column(
        Enum(PaymentAttemptStatus, name="payment_attempt_status"),
        nullable=False,
        default=PaymentAttemptStatus.pending,
    )
    cashier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    drawer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_drawers.id"), nullable=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    sumup_checkout_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Vintiz idempotence key forwarded to SumUp. It binds a paid checkout to
    # the exact sale intent and prevents reusing a checkout on another basket.
    foreign_transaction_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True, index=True
    )
    # SumUp Solo call + return — captured when the reader settles a CB attempt
    # (PAID or FAILED). Mirrors the Payment columns so a failed/cancelled try
    # that never produced a Transaction still records the terminal outcome:
    # transaction reference, auth code and masked card for SAV / reconciliation.
    sumup_transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sumup_transaction_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sumup_auth_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sumup_card_brand: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sumup_card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
