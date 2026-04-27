"""AI companion task model.

Represents an actionable suggestion the AI surfaces to the collaborator.
Lifecycle: pending -> accepted | snoozed | dismissed | completed.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType


class AITask(Base):
    __tablename__ = "ai_tasks"

    # Category of the task (e.g. "markdown", "mise_en_avant", "vitrine", "commande", "zone_alert")
    type: Mapped[str] = mapped_column(String(50), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # priority: 1 (low) .. 5 (urgent)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Lifecycle status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    # Optional deep-link for "Accepter"
    action_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Free-form payload (linked product id, price suggestion, zone id, etc.)
    payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    # Source endpoint or skill (e.g. "weekly-checklist", "pricing/markdowns")
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
