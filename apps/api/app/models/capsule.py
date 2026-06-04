"""Capsule du mois — page éditoriale mensuelle alimentée par les signaux IA.

Une seule ligne par ISO-month ("2026-06"). Le cron du 1er du mois à 08:00
upsert la ligne ; le manager peut aussi forcer un regen depuis l'admin.
Le payload ``proposal`` est un dict libre (theme, audience, événement,
produits tendance/événement, pastilles couleurs/types/cadeaux).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType, UUIDType


class MonthlyCapsule(Base):
    __tablename__ = "monthly_capsules"

    iso_month: Mapped[str] = mapped_column(
        String(7), unique=True, nullable=False
    )
    proposal: Mapped[dict] = mapped_column(JSONType, nullable=False)
    used_llm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("users.id"), nullable=True
    )
