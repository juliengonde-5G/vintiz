"""Authentication-related models (PR1: magic-link)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MagicLinkToken(Base):
    """Single-use OTP for the public client space.

    Issued by ``services.magic_link.issue`` (rate-limited per email/IP),
    consumed by ``services.magic_link.verify`` (5 attempts max). Never
    serves as long-term auth — verify exchanges it for a 1h JWT.
    """

    __tablename__ = "magic_link_tokens"

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
