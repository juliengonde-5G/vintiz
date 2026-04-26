"""Declarative markdown rules (P3-001).

Camille edits these from the admin without a code change. A nightly cron
walks the active catalogue, picks the first matching rule per product
(by ascending ``priority``), and applies the markdown via
``ProductLifecycleService``.

Rule schema (loose JSON, validated by the service before each apply):

    conditions:
      score_max: float           // product.trend_score < this
      score_min: float           // product.trend_score >= this
      age_min_days: int          // days since displayed_at
      age_max_days: int
      categories: list[str]      // category name in this list
      brands: list[str]          // brand in this list
      from_status: list[str]     // current ProductStatus.value
    action:
      to_status: "discounted" | "deep_discounted" | "returned_to_sorting" | "donated"
      discount_pct: float        // % off the current price (required for discounted/deep)
      tag_color: "yellow" | "orange" | "red" | "green"
      reason: str
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType, UUIDType


class MarkdownRule(Base):
    __tablename__ = "markdown_rules"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    # Lower priority wins when multiple rules match the same product.
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100
    )
    conditions: Mapped[dict] = mapped_column(JSONType, nullable=False)
    action: Mapped[dict] = mapped_column(JSONType, nullable=False)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("users.id"), nullable=True
    )
