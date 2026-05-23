"""Label print queue operations — enqueue, claim, ack, heartbeat, status.

Pure SQLAlchemy logic (no FastAPI) so it can be unit-tested against the SQLite
test database. The boutique runs a single Raspberry Pi agent, so the
claim/reclaim logic is deliberately simple (no SELECT … FOR UPDATE SKIP LOCKED,
which SQLite can't do); a lone consumer makes races a non-issue.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Settings
from app.models.label_job import LabelJobStatus, LabelJobType, LabelPrintJob
from app.services.label_render import product_label_snapshot, test_label_snapshot

_HEARTBEAT_KEY = "rpi_agent_last_seen"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def enqueue_product(
    db: AsyncSession,
    product: Any,
    *,
    copies: int = 1,
    user_id: uuid.UUID | None = None,
) -> LabelPrintJob:
    """Queue a product label, snapshotting its printable content now."""
    job = LabelPrintJob(
        job_type=LabelJobType.product.value,
        product_id=getattr(product, "id", None),
        copies=max(1, int(copies)),
        status=LabelJobStatus.pending.value,
        payload=product_label_snapshot(product),
        created_by_user_id=user_id,
    )
    db.add(job)
    await db.flush()
    return job


async def enqueue_test(
    db: AsyncSession, *, user_id: uuid.UUID | None = None
) -> LabelPrintJob:
    """Queue a hardware test label (used by /settings)."""
    job = LabelPrintJob(
        job_type=LabelJobType.test.value,
        product_id=None,
        copies=1,
        status=LabelJobStatus.pending.value,
        payload=test_label_snapshot(),
        created_by_user_id=user_id,
    )
    db.add(job)
    await db.flush()
    return job


async def claim_next(
    db: AsyncSession, *, limit: int = 5, stale_seconds: int = 120
) -> list[LabelPrintJob]:
    """Reclaim stale in-flight jobs, then claim up to ``limit`` pending jobs.

    Also records the agent heartbeat, so a poll that returns no work still
    keeps the printer shown as "online" in the UI.
    """
    now = _now()

    # Re-queue jobs a previous agent claimed but never acked (crash / power cut).
    cutoff = now - timedelta(seconds=max(10, stale_seconds))
    stale = (
        await db.execute(
            select(LabelPrintJob).where(
                LabelPrintJob.status == LabelJobStatus.printing.value,
                LabelPrintJob.claimed_at < cutoff,
            )
        )
    ).scalars().all()
    for job in stale:
        job.status = LabelJobStatus.pending.value
        job.claimed_at = None

    claimed = (
        await db.execute(
            select(LabelPrintJob)
            .where(LabelPrintJob.status == LabelJobStatus.pending.value)
            .order_by(LabelPrintJob.created_at.asc())
            .limit(max(1, int(limit)))
        )
    ).scalars().all()
    for job in claimed:
        job.status = LabelJobStatus.printing.value
        job.claimed_at = now

    await _record_heartbeat(db, now)
    await db.flush()
    return claimed


async def ack(
    db: AsyncSession,
    job_id: uuid.UUID,
    *,
    success: bool,
    error: str | None = None,
) -> LabelPrintJob | None:
    """Mark a claimed job done or failed. Returns None if the id is unknown."""
    job = (
        await db.execute(select(LabelPrintJob).where(LabelPrintJob.id == job_id))
    ).scalar_one_or_none()
    if job is None:
        return None
    job.status = LabelJobStatus.done.value if success else LabelJobStatus.error.value
    job.error = (error or "")[:500] if not success else None
    job.completed_at = _now()
    await _record_heartbeat(db, _now())
    await db.flush()
    return job


async def _record_heartbeat(db: AsyncSession, when: datetime) -> None:
    row = (
        await db.execute(select(Settings).where(Settings.key == _HEARTBEAT_KEY))
    ).scalar_one_or_none()
    if row is None:
        db.add(
            Settings(
                key=_HEARTBEAT_KEY,
                value=when.isoformat(),
                description="Dernier contact de l'agent d'impression Raspberry Pi",
            )
        )
    else:
        row.value = when.isoformat()


async def last_seen(db: AsyncSession) -> datetime | None:
    row = (
        await db.execute(select(Settings).where(Settings.key == _HEARTBEAT_KEY))
    ).scalar_one_or_none()
    if not row or not row.value:
        return None
    try:
        dt = datetime.fromisoformat(row.value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def queue_status(db: AsyncSession, *, stale_seconds: int = 120) -> dict:
    """Counts + agent freshness for the inventory/settings status pill."""
    counts = dict(
        (
            await db.execute(
                select(LabelPrintJob.status, func.count())
                .group_by(LabelPrintJob.status)
            )
        ).all()
    )
    seen = await last_seen(db)
    online = bool(seen and (_now() - seen).total_seconds() <= max(10, stale_seconds))
    return {
        "pending": int(counts.get(LabelJobStatus.pending.value, 0)),
        "printing": int(counts.get(LabelJobStatus.printing.value, 0)),
        "done": int(counts.get(LabelJobStatus.done.value, 0)),
        "error": int(counts.get(LabelJobStatus.error.value, 0)),
        "last_seen": seen.isoformat() if seen else None,
        "online": online,
    }
