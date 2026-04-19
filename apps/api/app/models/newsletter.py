"""Newsletter subscriber model.

RGPD-compliant email capture for the public site:
- Explicit consent stored with timestamp + IP + source.
- Unique unsubscribe token for 1-click revocation (no login required).
- Soft-delete via is_active + unsubscribed_at to preserve audit trail.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)

    # RGPD audit trail
    consent_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    consent_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="site_landing")

    # Unsubscribe — public token embedded in links, rotated on resubscribe
    unsubscribe_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
