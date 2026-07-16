"""Local calendar + commercial operations + cahier archive (L2.4)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType


class LocalEvent(Base):
    """Événement local Vernon / Giverny / vacances scolaires zone B.

    Drives the cahier du jour predictive engine (saison + jour semaine +
    vacances + événement). Manuellement saisi (CRUD admin) ou pré-chargé
    via seed.
    """

    __tablename__ = "local_events"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str] = mapped_column(String(50), nullable=False, default="Vernon")
    expected_traffic_boost_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_school_holiday: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )


class CommercialOperation(Base):
    """Opération commerciale (soldes, vente privée, opération adhérent…).

    Visible côté cahier du jour ; auto-applied côté POS si visible_pos
    et que les catégories / zones matchent. Visible côté site si
    visible_site=True.
    """

    __tablename__ = "commercial_operations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    op_type: Mapped[str] = mapped_column(String(50), nullable=False)
    discount_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applicable_categories: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    applicable_zones: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    visible_pos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    visible_site: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CahierDayArchive(Base):
    """Archive jour J-1 du cahier du jour avec commentaires manager.

    Le commentaire manager est modifiable jusqu'à locked_at (J+7 par
    défaut), puis read-only. Sert à la vue "Historique" du cahier.
    """

    __tablename__ = "cahier_day_archive"

    report_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    forecast_revenue: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    actual_revenue: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    forecast_tickets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_tickets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manager_morning_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_evening_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
