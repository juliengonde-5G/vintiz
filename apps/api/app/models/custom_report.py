"""Custom report definitions — saved « Rapports sur-mesure ».

A report is a named page holding a ``layout`` of widgets. Each widget is a JSON
spec (title, chart type, dataset, measure, dimension, time grain, date range,
filters) that the reporting engine turns into an aggregation at render time.
The data is never stored — only the definition — so a report always reflects
live figures."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType


class CustomReport(Base):
    __tablename__ = "custom_reports"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # List of widget specs (see app/services/reporting_engine.py for the keys).
    layout: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
