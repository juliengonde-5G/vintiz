"""DB-backed brand tier table (P2-012).

Replaces the hardcoded ``luxury_brands`` / ``premium_brands`` /
``mid_brands`` sets in ``scoring_service``. Camille edits these from
the admin so adding a new label (e.g. "Sézane") doesn't require a
deploy.
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BrandTierLevel(str, enum.Enum):
    luxury = "luxury"
    premium = "premium"
    mid = "mid"
    basic = "basic"


# Numeric score per tier — fed straight to the scoring formula.
# Aligned with the ``score_brand`` ladder in scoring_service.compute_score.
BRAND_TIER_SCORE: dict[BrandTierLevel, float] = {
    BrandTierLevel.luxury: 20.0,
    BrandTierLevel.premium: 15.0,
    BrandTierLevel.mid: 10.0,
    BrandTierLevel.basic: 8.0,
}


class BrandTier(Base):
    __tablename__ = "brand_tiers"

    # Stored lowercase to match the lookup at scoring time.
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    tier: Mapped[BrandTierLevel] = mapped_column(
        Enum(BrandTierLevel, name="brand_tier_level"),
        nullable=False,
    )
    # Override slot so an exceptional brand can sit between two tiers.
    # Optional — when null, ``BRAND_TIER_SCORE[tier]`` wins.
    score_override: Mapped[float | None] = mapped_column(Float, nullable=True)
