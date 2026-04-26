"""48h reservations (P4-005).

A client can hold a single product for 48h before coming to the boutique
to pay. The reservation is exclusive: while ``status = active`` and the
product is on the floor, the POS hides it from the search results so
nobody else can ring it up.

Lifecycle:
    active ──► redeemed   (cliente vient en boutique, le POS encaisse)
       │
       ├────► cancelled   (cliente annule, ou manager annule)
       │
       └────► expired     (cron retire la réservation après 48h)

The terminal states are immutable. ``redeemed_transaction_id`` ties the
sale back to the reservation for audit. ``manager_user_id`` records who
set up the hold (or NULL when self-service).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


DEFAULT_HOLD_HOURS = 48


class ReservationStatus(str, enum.Enum):
    active = "active"
    redeemed = "redeemed"
    cancelled = "cancelled"
    expired = "expired"


class Reservation(Base):
    __tablename__ = "reservations"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status"),
        nullable=False,
        default=ReservationStatus.active,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    redeemed_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )
    manager_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    client = relationship("Client", lazy="selectin")
    product = relationship("Product", lazy="selectin")
