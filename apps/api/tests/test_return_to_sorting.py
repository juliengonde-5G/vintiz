"""Tests for the automatic return-to-sorting cron (P3-007)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.events import EventLog, EventType
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.product_location import ProductLocationEvent
from app.models.user import User, UserRole
from app.services.return_to_sorting import (
    ReturnPolicy,
    ReturnToSortingService,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Category.__table__,
        Product.__table__,
        ProductPhoto.__table__,
        EventLog.__table__,
        ProductLocationEvent.__table__,
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


async def _make_product(
    session: AsyncSession,
    *,
    status: ProductStatus = ProductStatus.displayed,
    displayed_at: datetime | None = None,
    trend_score: float | None = 25.0,
    name: str = "Robe noire",
) -> Product:
    cat_result = await session.execute(
        select(Category).where(Category.name == "Robes")
    )
    cat = cat_result.scalar_one_or_none()
    if cat is None:
        cat = Category(name="Robes")
        session.add(cat)
        await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name=name,
        category_id=cat.id,
        sale_price=49.0,
        status=status,
        displayed_at=displayed_at,
        trend_score=trend_score,
    )
    session.add(p)
    await session.flush()
    return p


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_aged_low_score_product_is_eligible(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=120)
    p = await _make_product(
        session, displayed_at=long_ago, trend_score=15.0
    )
    candidates = await ReturnToSortingService(session).find_eligible()
    assert p in candidates


@pytest.mark.anyio
async def test_recent_product_is_not_eligible(session):
    recent = datetime.now(timezone.utc) - timedelta(days=10)
    p = await _make_product(session, displayed_at=recent, trend_score=10.0)
    candidates = await ReturnToSortingService(session).find_eligible()
    assert p not in candidates


@pytest.mark.anyio
async def test_aged_high_score_product_is_kept(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=200)
    p = await _make_product(
        session, displayed_at=long_ago, trend_score=80.0
    )
    candidates = await ReturnToSortingService(session).find_eligible()
    assert p not in candidates


@pytest.mark.anyio
async def test_aged_no_score_product_is_eligible_defensive(session):
    """A product 90+ days on the floor without scoring is suspect — return it."""
    long_ago = datetime.now(timezone.utc) - timedelta(days=120)
    p = await _make_product(
        session, displayed_at=long_ago, trend_score=None
    )
    candidates = await ReturnToSortingService(session).find_eligible()
    assert p in candidates


@pytest.mark.anyio
async def test_sold_or_returned_products_are_ignored(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=120)
    sold = await _make_product(
        session, status=ProductStatus.sold, displayed_at=long_ago
    )
    returned = await _make_product(
        session, status=ProductStatus.returned_to_sorting, displayed_at=long_ago
    )
    candidates = await ReturnToSortingService(session).find_eligible()
    assert sold not in candidates
    assert returned not in candidates


@pytest.mark.anyio
async def test_discounted_products_are_eligible(session):
    """The full markdown ladder (display → discounted → deep_discounted)
    must funnel into return-to-sorting if it sat too long."""
    long_ago = datetime.now(timezone.utc) - timedelta(days=120)
    a = await _make_product(
        session, status=ProductStatus.discounted, displayed_at=long_ago
    )
    b = await _make_product(
        session, status=ProductStatus.deep_discounted, displayed_at=long_ago
    )
    candidates = await ReturnToSortingService(session).find_eligible()
    assert a in candidates
    assert b in candidates


# ---------------------------------------------------------------------------
# run() — happy path + idempotence
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_run_marks_eligible_products_returned_and_emits_events(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=120)
    p1 = await _make_product(session, displayed_at=long_ago, trend_score=10.0)
    p2 = await _make_product(session, displayed_at=long_ago, trend_score=20.0, name="Jean")

    summary = await ReturnToSortingService(session).run()
    assert summary["returned"] == 2
    assert summary["scanned"] == 2

    await session.refresh(p1)
    await session.refresh(p2)
    assert p1.status == ProductStatus.returned_to_sorting
    assert p2.status == ProductStatus.returned_to_sorting

    rows = (await session.execute(
        select(EventLog).where(
            EventLog.event_type == EventType.product_returned_to_sorting
        )
    )).scalars().all()
    assert len(rows) == 2
    for row in rows:
        assert row.meta["reason"]


@pytest.mark.anyio
async def test_run_is_idempotent(session):
    """A second pass over the same products must be a no-op (terminal state)."""
    long_ago = datetime.now(timezone.utc) - timedelta(days=120)
    await _make_product(session, displayed_at=long_ago, trend_score=10.0)

    svc = ReturnToSortingService(session)
    first = await svc.run()
    assert first["returned"] == 1

    second = await svc.run()
    assert second["returned"] == 0
    assert second["scanned"] == 0


# ---------------------------------------------------------------------------
# Custom policy
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_policy_threshold_is_configurable(session):
    moderately_old = datetime.now(timezone.utc) - timedelta(days=45)
    p = await _make_product(
        session, displayed_at=moderately_old, trend_score=20.0
    )

    # Default 90j → not eligible
    default_candidates = await ReturnToSortingService(session).find_eligible()
    assert p not in default_candidates

    # Aggressive 30j policy → eligible
    aggressive = ReturnToSortingService(
        session, policy=ReturnPolicy(min_age_days=30, score_floor=30.0)
    )
    candidates = await aggressive.find_eligible()
    assert p in candidates


@pytest.mark.anyio
async def test_run_summary_includes_policy(session):
    summary = await ReturnToSortingService(session).run()
    assert summary["policy"]["min_age_days"] == 90
    assert summary["policy"]["score_floor"] == 30.0
    assert "displayed" in summary["policy"]["eligible_statuses"]
