"""Reference pricing grid — minimum sale price per category × brand tier.

The "grille tarifaire de référence" is the boutique's floor-price chart (the
laminated sheet at the till). It is keyed by product category and splits each
category into two brand buckets:

  - ``standard_price`` : floor for *standard* brands (mid / basic / unknown)
  - ``premium_price``  : floor "à partir de" for *premium* brands (premium /
    luxury tier in ``brand_tiers``)

It is purely advisory: at product creation (and reprice) the UI raises a
non-blocking notification when the chosen sale price falls below the applicable
floor. It does not change the AI price suggestion, which keeps blending the
inventory history, recent sales and the second-hand market estimate.

One row per category (``category_id`` unique). Defaults are pre-filled from the
Vintiz grid the first time the admin page is opened (see
``app/services/price_reference.py``)."""

import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PriceReference(Base):
    __tablename__ = "price_references"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Floor for standard brands (€). Nullable so a manager can leave a bucket
    # unset for a category (no alert for that bucket).
    standard_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Floor "à partir de" for premium/luxury brands (€).
    premium_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Free note (e.g. "synthétique 10 / cuir à partir de 12" for les chaussures).
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
