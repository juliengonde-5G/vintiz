"""Tests for the POS product insights service (P4-010)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.brand_tier import BRAND_TIER_SCORE, BrandTier, BrandTierLevel
from app.models.client import (
    AvoirTransaction,
    Client,
    Consent,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Gender, Product, ProductPhoto, ProductStatus
from app.models.user import User
from app.services.product_insights import compute_for_product


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Client.__table__,
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        AvoirTransaction.__table__,
        Consent.__table__,
        Category.__table__,
        Product.__table__,
        ProductPhoto.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        BrandTier.__table__,
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


@pytest.fixture(autouse=True)
def _reset_brand_cache():
    from app.services.brand_tiers import invalidate_cache
    invalidate_cache()
    yield
    invalidate_cache()


_TX_SEQ = {"n": 0}


async def _make_user(session) -> User:
    suffix = uuid.uuid4().hex[:6]
    u = User(
        username=f"u-{suffix}",
        email=f"{suffix}@x.fr",
        password_hash="x",
    )
    session.add(u)
    await session.flush()
    return u


async def _make_product(session, **overrides) -> Product:
    cat = (await session.execute(Category.__table__.select())).first()
    if not cat:
        c = Category(name="Robes", gender=Gender.femme)
        session.add(c)
        await session.flush()
        cat_id = c.id
    else:
        cat_id = cat[0]

    defaults = dict(
        barcode=f"B-{uuid.uuid4().hex[:8]}",
        name="Robe",
        category_id=cat_id,
        status=ProductStatus.displayed,
        sale_price=49,
        purchase_price=8,
    )
    defaults.update(overrides)
    p = Product(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _record_sale(session, user, product, *, when, qty=1):
    _TX_SEQ["n"] += 1
    tx = Transaction(
        transaction_number=_TX_SEQ["n"],
        transaction_type=TransactionType.sale,
        user_id=user.id,
        total_ht=product.sale_price / 1.2,
        total_tva=product.sale_price - product.sale_price / 1.2,
        total_ttc=product.sale_price,
        hash_chain="x" * 64,
        created_at=when,
    )
    session.add(tx)
    await session.flush()
    item = TransactionItem(
        transaction_id=tx.id,
        product_id=product.id,
        quantity=qty,
        unit_price=product.sale_price,
        line_total=product.sale_price * qty,
    )
    session.add(item)
    await session.flush()


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_insights_for_unknown_product(session):
    result = await compute_for_product(session, uuid.uuid4())
    assert result.insights == []


@pytest.mark.anyio
async def test_hot_seller_emits_velocity_badge(session):
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    user = await _make_user(session)
    product = await _make_product(session)
    for d in (1, 2, 3):
        await _record_sale(session, user, product, when=now - timedelta(days=d))

    result = await compute_for_product(session, product.id, now=now)
    labels = [i.label for i in result.insights]
    assert any("3" in label and "semaine" in label for label in labels)


@pytest.mark.anyio
async def test_stale_product_emits_warning(session):
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    product = await _make_product(
        session,
        status=ProductStatus.displayed,
        displayed_at=now - timedelta(days=60),
    )

    result = await compute_for_product(session, product.id, now=now)
    severities = [i.severity for i in result.insights]
    assert "warn" in severities


@pytest.mark.anyio
async def test_premium_brand_emits_star(session):
    session.add(BrandTier(name="sandro", tier=BrandTierLevel.premium))
    await session.flush()

    product = await _make_product(session, brand="Sandro Paris")
    result = await compute_for_product(session, product.id)
    labels = [i.label for i in result.insights]
    # Sandro is premium → score 18 → "Marque premium"
    assert "Marque premium" in labels


@pytest.mark.anyio
async def test_top_score_emits_target_badge(session):
    product = await _make_product(session, trend_score=92)
    result = await compute_for_product(session, product.id)
    labels = [i.label for i in result.insights]
    assert any("92" in label and "Score" in label for label in labels)


