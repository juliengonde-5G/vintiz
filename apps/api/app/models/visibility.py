"""Visibility / SEO / social tracking (P3-003 + P3-004 + P3-005)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType, UUIDType


# ---------------------------------------------------------------------------
# P3-005 — SEO snapshots
# ---------------------------------------------------------------------------


class SEOSnapshot(Base):
    """Daily snapshot of the SEO health check.

    Stores the score + the full ``checks`` payload so the front can
    plot a 30-day evolution and surface which check started failing.
    """

    __tablename__ = "seo_snapshots"

    site_url: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Same shape as the SEOStatus.checks list returned by /api/seo/status:
    # [{"name": "...", "passed": bool, "detail": str|None}, ...]
    checks: Mapped[list] = mapped_column(JSONType, nullable=False)
    # The cron stamps this; manual triggers stamp it too. Both go in the
    # series.
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ---------------------------------------------------------------------------
# P3-004 — Calendrier éditorial RS
# ---------------------------------------------------------------------------


class SocialPostCategory(str, enum.Enum):
    """The 4 categories Claude must alternate between (V1 §7.4)."""

    produit_star = "PRODUIT_STAR"
    valeurs = "VALEURS"
    temoignage = "TEMOIGNAGE"
    actu_locale = "ACTU_LOCALE"


class SocialPlatform(str, enum.Enum):
    instagram = "instagram"
    tiktok = "tiktok"
    both = "both"


class SocialPost(Base):
    __tablename__ = "social_posts"

    iso_week: Mapped[str] = mapped_column(String(8), nullable=False)
    category: Mapped[SocialPostCategory] = mapped_column(
        Enum(SocialPostCategory, name="social_post_category"),
        nullable=False,
    )
    platform: Mapped[SocialPlatform] = mapped_column(
        Enum(SocialPlatform, name="social_platform"),
        nullable=False,
    )
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON list of strings, e.g. ["#fripandco", "#vernon", "#secondemain"]
    hashtags: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    best_time: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "HH:MM"
    media_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    used_llm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("users.id"), nullable=True
    )


# ---------------------------------------------------------------------------
# P3-003 — Mentions + avis Google
# ---------------------------------------------------------------------------


class SocialMention(Base):
    """A mention of the boutique on Instagram / TikTok / etc.

    For MVP these are inserted manually (or by an importer the staff
    runs ad hoc). A future connector will fetch them from the
    Instagram Graph API and the TikTok hashtag search.
    """

    __tablename__ = "social_mentions"

    platform: Mapped[SocialPlatform] = mapped_column(
        Enum(SocialPlatform, name="social_platform_mention"),
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    author: Mapped[str | None] = mapped_column(String(120), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # -1.0 (négatif) → +1.0 (positif). NULL = non analysé.
    sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class GoogleReview(Base):
    """Inbound Google Business Profile reviews.

    Same shape as ``SocialMention`` plus the rating. Inserted manually
    for now; a future GBP API connector will populate them.
    """

    __tablename__ = "google_reviews"

    author: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..5
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Optional manager-curated reply.
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
