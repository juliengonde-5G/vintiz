"""Tests for the event store emitter (P1-003)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import Client
from app.models.events import EventLog, EventSource, EventType
from app.models.pos import (
    Payment,
    Receipt,
    Transaction,
    TransactionItem,
)
from app.models.product import Category, Product, ProductPhoto
from app.models.user import User, UserRole
from app.services.events import EventService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Client.__table__,
        Category.__table__,
        Product.__table__,
        ProductPhoto.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        Payment.__table__,
        Receipt.__table__,
        EventLog.__table__,
    ]
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


# ---------------------------------------------------------------------------
# emit() basics
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_emit_persists_a_row_with_all_fields(session):
    pid = uuid.uuid4()
    cid = uuid.uuid4()
    tid = uuid.uuid4()
    uid = uuid.uuid4()
    sid = uuid.uuid4()
    occurred = datetime(2026, 4, 26, 10, 0, 0, tzinfo=timezone.utc)

    row = await EventService(session).emit(
        EventType.product_sold,
        source=EventSource.pos,
        customer_id=cid,
        product_id=pid,
        transaction_id=tid,
        user_id=uid,
        session_id=sid,
        algo_version="v1",
        meta={"discount_percent": 10, "unit_price": 49.0},
        occurred_at=occurred,
    )

    assert row is not None
    assert row.event_type == EventType.product_sold
    assert row.source == EventSource.pos
    assert row.customer_id == cid
    assert row.product_id == pid
    assert row.transaction_id == tid
    assert row.user_id == uid
    assert row.session_id == sid
    assert row.algo_version == "v1"
    assert row.meta == {"discount_percent": 10, "unit_price": 49.0}
    # SQLite drops tzinfo — compare naive forms
    assert row.occurred_at.replace(tzinfo=None) == occurred.replace(tzinfo=None)


@pytest.mark.anyio
async def test_emit_accepts_string_event_type_and_source(session):
    """emit() must coerce raw strings so callers don't have to import enums."""
    row = await EventService(session).emit(
        "customer.visited",
        source="pos",
    )
    assert row is not None
    assert row.event_type == EventType.customer_visited
    assert row.source == EventSource.pos


@pytest.mark.anyio
async def test_emit_with_unknown_event_type_returns_none_and_does_not_raise(session):
    """A typo in the caller must never crash the business transaction.

    The contract: emit() returns None on bad input, logs a warning. The
    surrounding sale / refund / etc. is unaffected.
    """
    row = await EventService(session).emit(
        "product.exploded",  # not in the whitelist
        source=EventSource.pos,
    )
    assert row is None
    # Confirm no row landed in the table.
    rows = (await session.execute(select(EventLog))).scalars().all()
    assert rows == []


@pytest.mark.anyio
async def test_emit_with_unknown_source_returns_none(session):
    row = await EventService(session).emit(
        EventType.product_sold,
        source="mars",  # not in EventSource
    )
    assert row is None


@pytest.mark.anyio
async def test_emit_defaults_occurred_at_to_now(session):
    before = datetime.now(timezone.utc)
    row = await EventService(session).emit(
        EventType.product_viewed,
        source=EventSource.site,
    )
    after = datetime.now(timezone.utc)

    assert row is not None
    # tzinfo dropped on SQLite — strip both sides for comparison.
    occurred = row.occurred_at.replace(tzinfo=None)
    assert before.replace(tzinfo=None) <= occurred <= after.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Read helpers — counts_by_type and daily_volume
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_counts_by_type_aggregates_correctly(session):
    svc = EventService(session)
    await svc.emit(EventType.product_sold, source=EventSource.pos)
    await svc.emit(EventType.product_sold, source=EventSource.pos)
    await svc.emit(EventType.customer_visited, source=EventSource.pos)
    await svc.emit(EventType.product_viewed, source=EventSource.site)

    counts = await svc.counts_by_type()
    assert counts == {
        "product.sold": 2,
        "customer.visited": 1,
        "product.viewed": 1,
    }


@pytest.mark.anyio
async def test_counts_by_type_filters_by_since(session):
    svc = EventService(session)
    old = datetime.now(timezone.utc) - timedelta(days=10)
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    await svc.emit(
        EventType.product_sold, source=EventSource.pos, occurred_at=old
    )
    await svc.emit(
        EventType.product_sold, source=EventSource.pos, occurred_at=recent
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    counts = await svc.counts_by_type(since=cutoff)
    # Only the recent one is in window.
    assert counts == {"product.sold": 1}


@pytest.mark.anyio
async def test_daily_volume_returns_chronological_buckets(session):
    svc = EventService(session)
    # Two events two days ago, one yesterday.
    base = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    await svc.emit(
        EventType.product_sold,
        source=EventSource.pos,
        occurred_at=base - timedelta(days=2),
    )
    await svc.emit(
        EventType.product_sold,
        source=EventSource.pos,
        occurred_at=base - timedelta(days=2, hours=1),
    )
    await svc.emit(
        EventType.product_viewed,
        source=EventSource.site,
        occurred_at=base - timedelta(days=1),
    )

    daily = await svc.daily_volume(since=base - timedelta(days=3))
    assert len(daily) == 2
    # Newest day comes last (order_by ASC).
    assert daily[0]["count"] == 2
    assert daily[1]["count"] == 1


# ---------------------------------------------------------------------------
# Foreign key flexibility — orphan ids accepted (we don't want to block writes)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_emit_works_with_only_optional_fields(session):
    row = await EventService(session).emit(
        EventType.cashier_session_opened,
        source=EventSource.pos,
        meta={"opening_amount": 100.0},
    )
    assert row is not None
    assert row.customer_id is None
    assert row.product_id is None
    assert row.meta == {"opening_amount": 100.0}
