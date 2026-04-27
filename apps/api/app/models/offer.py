"""Commercial offers — basket-level promotions configured by the manager.

Vintiz never discounts the unit sale price; instead, the offers engine
adds line discounts or generates coupons when configured patterns match
the cart. Each row is a single rule the manager can enable/disable.

Six offer types are supported (cf. plan):

  * end_of_series       — week 6 product gets -20 % when bought combined
                          with another item.
  * birthday            — -10 % on the entire cart for a loyalty client
                          during their birthday week (Tue → Sat).
  * shoes_third_free    — buy 3 pairs of shoes, the cheapest is free.
  * progressive_voucher — once cumulative spend over a period crosses a
                          tier (e.g. 200 € → 10 € voucher), a Coupon is
                          issued for the next visit.
  * bundle_3_for_2      — 3 for the price of 2 on a curated selection.
  * seasonal_gift       — buying a category > min_amount unlocks a free
                          item from another category at checkout.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType


class OfferType(str, enum.Enum):
    end_of_series = "end_of_series"
    birthday = "birthday"
    shoes_third_free = "shoes_third_free"
    progressive_voucher = "progressive_voucher"
    bundle_3_for_2 = "bundle_3_for_2"
    seasonal_gift = "seasonal_gift"


class Offer(Base):
    """A single offer rule the manager has configured."""

    __tablename__ = "offers"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[OfferType] = mapped_column(
        Enum(OfferType, name="offer_type"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    valid_from: Mapped["datetime | None"] = mapped_column(  # type: ignore[name-defined]
        DateTime(timezone=True), nullable=True
    )
    valid_until: Mapped["datetime | None"] = mapped_column(  # type: ignore[name-defined]
        DateTime(timezone=True), nullable=True
    )
    requires_loyalty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Type-specific configuration. Schema documented in services/offers_engine.py.
    config: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True
    )


# Re-export ``datetime`` so the forward refs above resolve at runtime.
from datetime import datetime  # noqa: E402,F401
