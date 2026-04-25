import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.types import JSONType


class DailyReport(Base):
    __tablename__ = "daily_reports"

    report_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    total_sales: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    total_items_sold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_refunds: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    net_revenue: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    data: Mapped[dict | None] = mapped_column(JSONType, nullable=True)


class CommercialAction(Base):
    __tablename__ = "commercial_actions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    discount_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    target_categories: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    results: Mapped[list["ActionResult"]] = relationship(
        "ActionResult", backref="action", lazy="selectin"
    )


class ActionResult(Base):
    __tablename__ = "action_results"

    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commercial_actions.id"), nullable=False
    )
    result_date: Mapped[date] = mapped_column(Date, nullable=False)
    items_sold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revenue: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
