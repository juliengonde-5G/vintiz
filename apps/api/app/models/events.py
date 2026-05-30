"""Event store for downstream analytics, recommenders and audit (P1-003).

Every business action that the AI layer or the reporting layer might want
to learn from emits a row here. A separate, append-only stream lets us
replay history when the scoring or Personal Shopper algorithms change
without polluting OLTP tables with extra columns.

Design notes:
- The table is not partitioned in Phase 2; expected volume for Vernon is
  ~500 k events/year and a single table with a btree on ``occurred_at``
  is fine for years. Partitioning by RANGE(occurred_at) can be added
  later via a follow-up migration without touching this model — only the
  underlying physical layout changes.
- ``occurred_at`` is distinct from the inherited ``created_at`` so we can
  backfill events from older sources (e.g. seed data, imports) without
  rewriting history.
- ``meta`` (mapped to ``metadata`` column) holds arbitrary JSON; do not
  query it in hot paths — extract dimensions to a typed column when a
  metric matures.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType, UUIDType


class EventType(str, enum.Enum):
    """Whitelisted event names. Strict enum so emitters can't drift."""

    # Product life cycle
    product_created = "product.created"
    product_viewed = "product.viewed"
    product_try_requested = "product.try_requested"
    product_try_in_store = "product.try_in_store"
    product_sold = "product.sold"
    product_refunded = "product.refunded"
    product_donated = "product.donated"
    product_returned_to_sorting = "product.returned_to_sorting"
    product_markdown_applied = "product.markdown_applied"
    product_zone_changed = "product.zone_changed"

    # Customer life cycle
    customer_signed_up = "customer.signed_up"
    customer_visited = "customer.visited"
    customer_recommendation_shown = "customer.recommendation_shown"
    customer_recommendation_clicked = "customer.recommendation_clicked"
    # PS 360 V3 — « Pépites du jour » shown on the POS client panel. Drives the
    # 24 h frequency cap (don't re-surface a piece already shown) + adoption KPI.
    customer_picks_shown = "customer.picks_shown"

    # Cashier sessions
    cashier_session_opened = "cashier.session_opened"
    cashier_session_closed = "cashier.session_closed"


class EventSource(str, enum.Enum):
    """Where the event originated. Used for filtering + dashboards."""

    pos = "pos"
    site = "site"
    admin = "admin"
    api = "api"
    system = "system"


class EventLog(Base):
    __tablename__ = "events_log"

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    source: Mapped[EventSource] = mapped_column(
        Enum(EventSource, name="event_source", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("clients.id"), nullable=True, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("products.id"), nullable=True, index=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("transactions.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("users.id"), nullable=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    # Versioning for IA-driven events so we can compare algorithm iterations.
    algo_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Free-form metadata — keep payloads small (< 1 kB), promote to columns
    # when a key becomes a hot dimension.
    meta: Mapped[dict | None] = mapped_column("metadata", JSONType, nullable=True)

    __table_args__ = (
        Index(
            "ix_events_customer_time",
            "customer_id",
            "occurred_at",
        ),
        Index(
            "ix_events_product_time",
            "product_id",
            "occurred_at",
        ),
        Index(
            "ix_events_type_time",
            "event_type",
            "occurred_at",
        ),
    )
