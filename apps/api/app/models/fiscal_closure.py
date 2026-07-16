"""Immutable NF525 periodic and cumulative fiscal closures."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType


class FiscalClosure(Base):
    __tablename__ = "fiscal_closures"

    sequence_number: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False
    )
    closure_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    software_version: Mapped[str] = mapped_column(String(32), nullable=False)
    transaction_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_transaction_number: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    last_transaction_number: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    last_transaction_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    last_z_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    archive_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    archive_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONType, nullable=False)
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
