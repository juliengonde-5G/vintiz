"""Label print queue — jobs drained by the in-store Raspberry Pi agent.

The API runs off-site (cloud) and cannot open a socket to a printer on the
boutique LAN. Instead of pushing to the printer, the manager's "print label"
action enqueues a row here; the Raspberry Pi in the shop polls the agent
endpoints (outbound only, NAT-friendly), renders nothing itself — it just
prints the server-rendered PDF carried by the job — and acks the result.

The printable content is snapshotted into ``payload`` at enqueue time so the
label reflects what the manager saw, even if the product is later edited or
deleted before the Pi gets to it.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType


class LabelJobType(str, enum.Enum):
    product = "product"
    test = "test"


class LabelJobStatus(str, enum.Enum):
    pending = "pending"    # waiting to be claimed by the agent
    printing = "printing"  # claimed by the agent, awaiting ack
    done = "done"          # printed successfully
    error = "error"        # the agent reported a failure


class LabelPrintJob(Base):
    __tablename__ = "label_print_jobs"

    # Stored as plain strings (not a PG enum) to keep the migration portable
    # across PostgreSQL and the SQLite test database.
    job_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default=LabelJobType.product.value
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    copies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=LabelJobStatus.pending.value, index=True
    )
    # Snapshot of the printable content: {"ref", "name", "week_label"}.
    payload: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
