"""SumUp terminal registry — multi-device support + heartbeat status.

Vintiz used to expose a single SumUp terminal via env vars
(``SUMUP_READER_ID`` + ``SUMUP_API_KEY``). This works for one Solo at the
till but breaks for the M2 setup that adds a second mobile Solo for
in-store merchandising checkout (Galaxy Tab S11 Ultra). The new model
lets the manager:

- declare each terminal with a friendly label + location
- mark one as default (used when the POS doesn't pick a specific reader)
- record the last heartbeat status so the back-office shows red/amber/green

The env vars (``SUMUP_READER_ID``) / app_config stay valid as a fallback
when the table has no default terminal — that keeps the existing
single-terminal deployment working without any config change. As soon as a
default terminal is declared here, ``SumUpService.resolve_reader_from_registry``
makes the DB take precedence for the push. (The table is NOT auto-seeded
from env — declare terminals from ``/settings > Paiement``.)
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SumUpTerminalStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    unknown = "unknown"


class SumUpTerminal(Base):
    __tablename__ = "sumup_terminals"

    label: Mapped[str] = mapped_column(String(80), nullable=False)
    reader_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[SumUpTerminalStatus] = mapped_column(
        Enum(SumUpTerminalStatus, name="sumup_terminal_status"),
        nullable=False,
        default=SumUpTerminalStatus.unknown,
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_heartbeat_status: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )  # ok | unreachable | error | unauthorized
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
