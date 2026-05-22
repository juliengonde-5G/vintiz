"""Mid-day cash movement — entries / withdrawals from the till during a session.

Captures every cash flow that's neither a sale nor a refund:
- ``out / bank_deposit`` : the manager removes cash to deposit it at the bank
- ``out / supplier_payment`` : a supplier paid in cash
- ``out / personal_withdrawal`` : owner takes a personal withdrawal
- ``in / float_top_up`` : extra change brought from the safe to the till
- ``in / other`` / ``out / other`` : misc, with a free ``note``

Used by:
- The Z report (closing reconciliation): expected_amount =
  opening_amount + ∑ cash payments + ∑ in - ∑ out
- The admin /admin/transactions and /admin/cash-management pages
- The audit log (NF525-friendly: append-only, never edited)
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CashMovementDirection(str, enum.Enum):
    inflow = "in"
    outflow = "out"


class CashMovementReason(str, enum.Enum):
    bank_deposit = "bank_deposit"
    supplier_payment = "supplier_payment"
    personal_withdrawal = "personal_withdrawal"
    float_top_up = "float_top_up"
    other = "other"


class CashMovement(Base):
    __tablename__ = "cash_movements"

    drawer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_drawers.id"), nullable=False
    )
    direction: Mapped[CashMovementDirection] = mapped_column(
        # Les LABELS de l'enum PG (migration 0035) sont "in"/"out" — soit les
        # VALEURS de l'enum, pas ses noms (inflow/outflow). Sans
        # values_callable, SQLAlchemy persiste le NOM ("inflow") que le type
        # PG rejette → 500 sur chaque mouvement de caisse. Même convention que
        # EventType/EventSource (app/models/events.py).
        Enum(
            CashMovementDirection,
            name="cash_movement_direction",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[CashMovementReason] = mapped_column(
        Enum(CashMovementReason, name="cash_movement_reason"),
        nullable=False,
        default=CashMovementReason.other,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    cashier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
