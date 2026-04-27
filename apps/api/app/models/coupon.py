"""Coupons / promo codes (P4-008 + future POS integration).

Each coupon is a single-use discount tied to one client (e.g. anniversary
gift, win-back campaign). The POS validates the code on checkout: it
must be active, not expired, owned by the same client (or unattached if
the coupon is generic), and not redeemed yet.

The minimal field set covers the use cases on the audit roadmap:
- Anniversary gift: percent off, valid 7 days, nominative.
- Win-back: percent or amount off, valid X days, nominative.
- Generic flyer: amount off, no client_id, expires on a fixed date.

Audit, RFM and refund flows already cover the surrounding ledgers; this
table is intentionally tiny.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CouponDiscountType(str, enum.Enum):
    percent = "percent"
    amount = "amount"


class CouponSource(str, enum.Enum):
    """Why this coupon was issued. Drives reporting + manager filters."""

    anniversary = "anniversary"           # legacy — replaced by Offer(birthday)
    winback = "winback"                   # at_risk / hibernating clients
    welcome = "welcome"                   # signup nudge
    manual = "manual"                     # admin one-off
    progressive = "progressive"           # bon généré sur cumul (Offer.progressive_voucher)
    loyalty_milestone = "loyalty_milestone"  # palier 100 pts = 8 €


class Coupon(Base):
    __tablename__ = "coupons"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True
    )
    discount_type: Mapped[CouponDiscountType] = mapped_column(
        Enum(CouponDiscountType, name="coupon_discount_type"), nullable=False
    )
    discount_value: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    source: Mapped[CouponSource] = mapped_column(
        Enum(CouponSource, name="coupon_source"), nullable=False
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    redeemed_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
