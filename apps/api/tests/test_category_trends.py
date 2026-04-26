"""Tests for the per-category trend signal (P2-010)."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.audit import Settings
from app.models.client import Client
from app.models.pos import (
    Payment,
    Receipt,
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.user import User, UserRole
from app.services.category_trends import (
    CACHE_KEY,
    NEUTRAL_TREND,
    compute_category_trends,
    get_category_trend,
    get_category_trends,
    refresh_cache,
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
        Client.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        Payment.__table__,
        Receipt.__table__,
        Settings.__table__,
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


async def _make_user(session: AsyncSession) -> User:
    u = User(
        username=f"u-{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:6]}@v.fr",
        password_hash="x" * 60,
        role=UserRole.collaborateur,
        is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


async def _make_category(session: AsyncSession, name: str) -> Category:
    cat = Category(name=name)
    session.add(cat)
    await session.flush()
    return cat


async def _make_product(
    session: AsyncSession, category: Category, *, name: str = "X"
) -> Product:
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name=name,
        category_id=category.id,
        sale_price=49.0,
        status=ProductStatus.display,
    )
    session.add(p)
    await session.flush()
    return p


async def _record_sale(
    session: AsyncSession,
    user: User,
    product: Product,
    *,
    when: datetime | None = None,
):
    tx = Transaction(
        transaction_number=int(uuid.uuid4().int % 1_000_000_000),
        transaction_type=TransactionType.sale,
        user_id=user.id,
        total_ht=40, total_tva=9, total_ttc=49,
        hash_chain="x",
        created_at=when or datetime.now(timezone.utc),
    )
    session.add(tx)
    await session.flush()
    session.add(TransactionItem(
        transaction_id=tx.id,
        product_id=product.id,
        quantity=1,
        unit_price=49.0,
        discount_percent=0,
        line_total=49.0,
    ))
    await session.flush()


# ---------------------------------------------------------------------------
# compute_category_trends — algorithm
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_sales_returns_neutral_for_every_category(session):
    a = await _make_category(session, "Robes")
    b = await _make_category(session, "Sacs")
    trends = await compute_category_trends(session)
    assert trends == {str(a.id): NEUTRAL_TREND, str(b.id): NEUTRAL_TREND}


@pytest.mark.anyio
async def test_top_selling_category_scores_100(session):
    user = await _make_user(session)
    hot = await _make_category(session, "Robes")
    cold = await _make_category(session, "Sacs")

    p_hot1 = await _make_product(session, hot, name="r1")
    p_hot2 = await _make_product(session, hot, name="r2")
    p_cold = await _make_product(session, cold, name="s1")

    # Hot: 4 sales. Cold: 1 sale.
    for _ in range(2):
        await _record_sale(session, user, p_hot1)
    for _ in range(2):
        await _record_sale(session, user, p_hot2)
    await _record_sale(session, user, p_cold)

    trends = await compute_category_trends(session)
    assert trends[str(hot.id)] == 100.0
    assert trends[str(cold.id)] == 25.0  # 1/4 × 100


@pytest.mark.anyio
async def test_categories_without_sales_keep_neutral(session):
    user = await _make_user(session)
    seen = await _make_category(session, "Robes")
    unseen = await _make_category(session, "Bijoux")
    p = await _make_product(session, seen, name="r1")
    await _record_sale(session, user, p)

    trends = await compute_category_trends(session)
    assert trends[str(seen.id)] == 100.0
    # No sales → neutral, NOT zero (we don't punish brand-new categories)
    assert trends[str(unseen.id)] == NEUTRAL_TREND


@pytest.mark.anyio
async def test_old_sales_are_ignored_outside_window(session):
    user = await _make_user(session)
    cat = await _make_category(session, "Robes")
    p = await _make_product(session, cat, name="r1")

    long_ago = datetime.now(timezone.utc) - timedelta(days=120)
    await _record_sale(session, user, p, when=long_ago)

    trends = await compute_category_trends(session, window_days=28)
    # No sales in the 28-day window → all categories neutral.
    assert trends[str(cat.id)] == NEUTRAL_TREND


@pytest.mark.anyio
async def test_only_sale_transactions_count(session):
    """Refunds (transaction_type=refund) must NOT lift the trend."""
    user = await _make_user(session)
    cat = await _make_category(session, "Robes")
    p = await _make_product(session, cat, name="r1")

    refund = Transaction(
        transaction_number=int(uuid.uuid4().int % 1_000_000_000),
        transaction_type=TransactionType.refund,
        user_id=user.id,
        total_ht=40, total_tva=9, total_ttc=49,
        hash_chain="x",
    )
    session.add(refund)
    await session.flush()
    session.add(TransactionItem(
        transaction_id=refund.id, product_id=p.id, quantity=1,
        unit_price=49.0, discount_percent=0, line_total=49.0,
    ))
    await session.flush()

    trends = await compute_category_trends(session)
    assert trends[str(cat.id)] == NEUTRAL_TREND


# ---------------------------------------------------------------------------
# Cache (Settings table)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_category_trends_caches_result(session):
    cat = await _make_category(session, "Robes")
    user = await _make_user(session)
    p = await _make_product(session, cat, name="r1")
    await _record_sale(session, user, p)

    _ = await get_category_trends(session)
    row = (await session.execute(
        select(Settings).where(Settings.key == CACHE_KEY)
    )).scalar_one()
    payload = json.loads(row.value)
    assert "trends" in payload
    assert "computed_at" in payload
    assert payload["trends"][str(cat.id)] == 100.0


@pytest.mark.anyio
async def test_fresh_cache_is_reused_without_recomputing(session):
    cat = await _make_category(session, "Robes")
    user = await _make_user(session)
    p = await _make_product(session, cat, name="r1")
    await _record_sale(session, user, p)

    first = await get_category_trends(session)

    # Add a new sale — but the cache is fresh, so the read should ignore it.
    await _record_sale(session, user, p)
    second = await get_category_trends(session, max_age_hours=24)
    assert second == first


@pytest.mark.anyio
async def test_stale_cache_triggers_recomputation(session):
    cat = await _make_category(session, "Robes")
    user = await _make_user(session)
    p = await _make_product(session, cat, name="r1")
    await _record_sale(session, user, p)

    await get_category_trends(session)

    # Manually age the cache.
    row = (await session.execute(
        select(Settings).where(Settings.key == CACHE_KEY)
    )).scalar_one()
    payload = json.loads(row.value)
    payload["computed_at"] = (
        datetime.now(timezone.utc) - timedelta(days=2)
    ).isoformat()
    row.value = json.dumps(payload)
    await session.flush()

    # Add data — recompute will pick it up.
    other_cat = await _make_category(session, "Sacs")
    p_other = await _make_product(session, other_cat, name="s1")
    for _ in range(3):
        await _record_sale(session, user, p_other)

    refreshed = await get_category_trends(session, max_age_hours=24)
    # 'Sacs' now has 3 sales vs 1 for 'Robes' → Sacs is the new top.
    assert refreshed[str(other_cat.id)] == 100.0
    assert refreshed[str(cat.id)] < 100.0


@pytest.mark.anyio
async def test_get_category_trend_returns_neutral_for_unknown_category(session):
    trend = await get_category_trend(session, uuid.uuid4())
    assert trend == NEUTRAL_TREND


@pytest.mark.anyio
async def test_get_category_trend_handles_none(session):
    trend = await get_category_trend(session, None)
    assert trend == NEUTRAL_TREND


@pytest.mark.anyio
async def test_refresh_cache_returns_payload(session):
    cat = await _make_category(session, "Robes")
    user = await _make_user(session)
    p = await _make_product(session, cat, name="r1")
    await _record_sale(session, user, p)

    payload = await refresh_cache(session)
    assert payload[str(cat.id)] == 100.0
