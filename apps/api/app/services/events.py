"""Event store emitter (P1-003).

The recommender, the dashboards and any future analytics layer all read
from ``events_log``. The emitter is intentionally tolerant: a failure to
write an event must never break the business transaction that generated
it. In production we'd ship those failures to Sentry; here we log a
warning and move on.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.events import EventLog, EventSource, EventType

logger = logging.getLogger("vintiz.events")


class EventService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def emit(
        self,
        event_type: EventType | str,
        *,
        source: EventSource | str,
        customer_id: uuid.UUID | None = None,
        product_id: uuid.UUID | None = None,
        transaction_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        algo_version: str | None = None,
        meta: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> EventLog | None:
        """Insert an event row. Returns the row, or ``None`` on failure.

        Catches and logs every exception so a buggy event payload cannot
        roll back the surrounding business write. Validation errors on
        ``event_type`` / ``source`` (i.e. wrong enum value) are still
        surfaced as warnings so they're visible in CI logs.
        """
        try:
            et = (
                event_type
                if isinstance(event_type, EventType)
                else EventType(event_type)
            )
            src = (
                source
                if isinstance(source, EventSource)
                else EventSource(source)
            )
        except ValueError as exc:
            logger.warning(
                "events.emit rejected unknown enum value: %s", exc
            )
            return None

        row = EventLog(
            occurred_at=occurred_at or datetime.now(timezone.utc),
            event_type=et,
            source=src,
            customer_id=customer_id,
            product_id=product_id,
            transaction_id=transaction_id,
            user_id=user_id,
            session_id=session_id,
            algo_version=algo_version,
            meta=meta,
        )
        try:
            self.db.add(row)
            await self.db.flush()
            return row
        except Exception as exc:  # pragma: no cover — defensive only
            logger.warning(
                "events.emit failed for type=%s: %s", et.value, exc
            )
            return None

    # ------------------------------------------------------------------
    # Read helpers (used by the data-quality dashboard)
    # ------------------------------------------------------------------

    async def counts_by_type(
        self,
        since: datetime | None = None,
    ) -> dict[str, int]:
        """Return ``{event_type: count}`` aggregated since ``since``.

        Used by ``GET /api/admin/data-quality`` to spot anomalies (e.g.
        zero ``product.viewed`` events for a day = JS instrumentation
        broke).
        """
        query = select(EventLog.event_type, func.count(EventLog.id))
        if since is not None:
            query = query.where(EventLog.occurred_at >= since)
        query = query.group_by(EventLog.event_type)
        result = await self.db.execute(query)
        return {row[0].value: row[1] for row in result.all()}

    async def daily_volume(
        self, since: datetime, until: datetime | None = None
    ) -> list[dict]:
        """Return per-day total event counts in [since, until)."""
        until = until or datetime.now(timezone.utc)
        result = await self.db.execute(
            select(
                func.date(EventLog.occurred_at).label("day"),
                func.count(EventLog.id).label("count"),
            )
            .where(EventLog.occurred_at >= since)
            .where(EventLog.occurred_at < until)
            .group_by(func.date(EventLog.occurred_at))
            .order_by(func.date(EventLog.occurred_at))
        )
        return [{"day": str(row.day), "count": row.count} for row in result.all()]
