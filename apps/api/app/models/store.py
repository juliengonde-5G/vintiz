import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class StoreZone(Base):
    __tablename__ = "store_zones"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    product_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    color_code: Mapped[str | None] = mapped_column(String(20), nullable=True, default="#1A7A6A")

    zone_products: Mapped[list["ZoneProduct"]] = relationship(
        "ZoneProduct", back_populates="zone", lazy="selectin"
    )


class ZoneProduct(Base):
    __tablename__ = "zone_products"

    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("store_zones.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    zone: Mapped["StoreZone"] = relationship(
        "StoreZone", back_populates="zone_products", lazy="selectin"
    )


class TrendAnalysis(Base):
    __tablename__ = "trend_analyses"

    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class StoreArrangement(Base):
    __tablename__ = "store_arrangements"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    layout: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"

    arrangement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("store_arrangements.id"), nullable=True
    )
    recommendation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    applied: Mapped[bool] = mapped_column(default=False, nullable=False)
