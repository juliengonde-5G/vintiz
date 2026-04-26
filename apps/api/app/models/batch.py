"""Intake batches: cartons / palettes received by the boutique (P2-015).

Each carton from the Solidarité Textiles sorting centre — or any other
intake source — is registered here so we can attribute every Product to
the lot it came in with. This unlocks two downstream features:
- Mandatory traceability for the ESS reporting (réemploi rates,
  tonnages, source of inventory).
- The automatic return-to-sorting cron (P3-007) groups its picks by
  origin batch so Sophie prints one return slip per source.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import UUIDType


class IntakeSource(str, enum.Enum):
    """Where a batch came from. ESS reporting groups by this dimension."""

    sorting_center = "sorting_center"   # Solidarité Textiles centre de tri
    deposit = "deposit"                 # dépôt-vente cliente
    direct_donation = "direct_donation"  # don direct en boutique
    purchase = "purchase"                # achat sourcing externe
    other = "other"


class IntakeBatch(Base):
    __tablename__ = "intake_batches"

    # Human-readable counter (e.g. "BATCH-2026-04-001"). Globally unique.
    batch_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    source: Mapped[IntakeSource] = mapped_column(
        Enum(IntakeSource, name="intake_source"), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Cashier / employee who logged the carton on arrival.
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("users.id"), nullable=True
    )
    # Counter set by the operator at reception, before items are tagged.
    # Helps detect attrition between intake and tagging.
    n_items_received: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
