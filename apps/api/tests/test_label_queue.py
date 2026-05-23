"""Tests for the label print queue (enqueue / claim / ack / status).

Self-contained: a private in-memory SQLite engine holds just the
``label_print_jobs`` + ``app_settings`` tables, so the queue logic is exercised
without the full app or a network printer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.audit import Settings
from app.models.label_job import LabelJobStatus, LabelJobType, LabelPrintJob
from app.services import label_queue


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(
                c, tables=[LabelPrintJob.__table__, Settings.__table__]
            )
        )
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as s:
        yield s
    await eng.dispose()


class _StubProduct:
    def __init__(self):
        import uuid

        self.id = uuid.uuid4()
        self.name = "Veste en jean"
        self.category = None
        self.size = "M"
        self.condition = "bon"
        self.sale_price = 12.0
        self.barcode = "VTZ-2026-00142"
        self.status = type("S", (), {"value": "displayed"})()
        self.received_at = None
        self.shelf_date = None
        self.displayed_at = None
        self.week_number = 20


@pytest.mark.anyio
async def test_enqueue_product_snapshots_content(session):
    product = _StubProduct()
    job = await label_queue.enqueue_product(session, product, copies=3)
    assert job.status == LabelJobStatus.pending.value
    assert job.job_type == LabelJobType.product.value
    assert job.copies == 3
    assert job.product_id == product.id
    assert job.payload["ref"] == "VTZ-2026-00142"
    assert job.payload["name"] == "Veste en jean"
    assert job.payload["week_label"] == "Semaine 20"


@pytest.mark.anyio
async def test_enqueue_test_has_no_product(session):
    job = await label_queue.enqueue_test(session)
    assert job.job_type == LabelJobType.test.value
    assert job.product_id is None
    assert job.payload["ref"] == "VINTIZ-TEST"


@pytest.mark.anyio
async def test_claim_marks_jobs_printing_and_heartbeats(session):
    await label_queue.enqueue_product(session, _StubProduct())
    await label_queue.enqueue_product(session, _StubProduct())

    claimed = await label_queue.claim_next(session, limit=5)
    assert len(claimed) == 2
    assert all(j.status == LabelJobStatus.printing.value for j in claimed)
    assert all(j.claimed_at is not None for j in claimed)
    # Polling records a heartbeat even though it's the first contact.
    assert await label_queue.last_seen(session) is not None


@pytest.mark.anyio
async def test_claim_respects_limit(session):
    for _ in range(3):
        await label_queue.enqueue_product(session, _StubProduct())
    claimed = await label_queue.claim_next(session, limit=2)
    assert len(claimed) == 2
    status = await label_queue.queue_status(session)
    assert status["printing"] == 2
    assert status["pending"] == 1


@pytest.mark.anyio
async def test_ack_success_and_failure(session):
    job = await label_queue.enqueue_product(session, _StubProduct())
    await label_queue.claim_next(session, limit=5)

    done = await label_queue.ack(session, job.id, success=True)
    assert done.status == LabelJobStatus.done.value
    assert done.completed_at is not None
    assert done.error is None

    job2 = await label_queue.enqueue_product(session, _StubProduct())
    await label_queue.claim_next(session, limit=5)
    failed = await label_queue.ack(session, job2.id, success=False, error="paper out")
    assert failed.status == LabelJobStatus.error.value
    assert failed.error == "paper out"


@pytest.mark.anyio
async def test_ack_unknown_job_returns_none(session):
    import uuid

    assert await label_queue.ack(session, uuid.uuid4(), success=True) is None


@pytest.mark.anyio
async def test_stale_printing_jobs_are_reclaimed(session):
    job = await label_queue.enqueue_product(session, _StubProduct())
    # Simulate an agent that claimed the job then crashed before acking.
    job.status = LabelJobStatus.printing.value
    job.claimed_at = datetime.now(timezone.utc) - timedelta(seconds=600)
    await session.flush()

    claimed = await label_queue.claim_next(session, limit=5, stale_seconds=120)
    assert [j.id for j in claimed] == [job.id]
    assert job.status == LabelJobStatus.printing.value


@pytest.mark.anyio
async def test_queue_status_online_reflects_recent_poll(session):
    await label_queue.enqueue_product(session, _StubProduct())
    before = await label_queue.queue_status(session, stale_seconds=120)
    assert before["online"] is False  # never polled yet

    await label_queue.claim_next(session, limit=5)
    after = await label_queue.queue_status(session, stale_seconds=120)
    assert after["online"] is True
