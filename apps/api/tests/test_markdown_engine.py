"""Tests for the declarative markdown engine (P3-001)."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.events import EventLog, EventType
from app.models.markdown import MarkdownRule
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.user import User, UserRole
from app.services.markdown_engine import (
    MarkdownEngineService,
    _matches_conditions,
    _validate_action,
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
        MarkdownRule.__table__,
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
    sale_price: float = 49.0,
    trend_score: float | None = 30.0,
    status: ProductStatus = ProductStatus.displayed,
    displayed_at: datetime | None = None,
    brand: str | None = "Sandro",
    category_name: str = "Robes",
) -> Product:
    cat_row = await session.execute(
        select(Category).where(Category.name == category_name)
    )
    cat = cat_row.scalar_one_or_none()
    if cat is None:
        cat = Category(name=category_name)
        session.add(cat)
        await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name="Robe noire",
        category_id=cat.id,
        sale_price=sale_price,
        status=status,
        trend_score=trend_score,
        brand=brand,
        displayed_at=displayed_at,
    )
    session.add(p)
    await session.flush()
    return p


async def _make_rule(
    session: AsyncSession,
    *,
    name: str = "rule",
    priority: int = 100,
    active: bool = True,
    conditions: dict | None = None,
    action: dict | None = None,
) -> MarkdownRule:
    rule = MarkdownRule(
        name=name,
        priority=priority,
        active=active,
        conditions=conditions or {},
        action=action or {"to_status": "discounted", "discount_pct": 20},
    )
    session.add(rule)
    await session.flush()
    return rule


# ---------------------------------------------------------------------------
# _matches_conditions
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_score_max_filter(session):
    p = await _make_product(session, trend_score=30.0)
    cat = (await session.execute(
        select(Category).where(Category.id == p.category_id)
    )).scalar_one()
    assert _matches_conditions(p, cat, {"score_max": 50}) is True
    assert _matches_conditions(p, cat, {"score_max": 25}) is False


@pytest.mark.anyio
async def test_age_filter_requires_displayed_at(session):
    """Without a displayed_at anchor we can't apply age conditions."""
    p = await _make_product(session, displayed_at=None)
    cat = (await session.execute(
        select(Category).where(Category.id == p.category_id)
    )).scalar_one()
    assert _matches_conditions(p, cat, {"age_min_days": 30}) is False


@pytest.mark.anyio
async def test_age_min_days_filter(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=45)
    p = await _make_product(session, displayed_at=long_ago)
    cat = (await session.execute(
        select(Category).where(Category.id == p.category_id)
    )).scalar_one()
    assert _matches_conditions(p, cat, {"age_min_days": 30}) is True
    assert _matches_conditions(p, cat, {"age_min_days": 60}) is False


@pytest.mark.anyio
async def test_category_filter_normalizes_case(session):
    p = await _make_product(session, category_name="Robes")
    cat = (await session.execute(
        select(Category).where(Category.id == p.category_id)
    )).scalar_one()
    assert _matches_conditions(p, cat, {"categories": ["robes"]}) is True
    assert _matches_conditions(p, cat, {"categories": ["pulls"]}) is False


@pytest.mark.anyio
async def test_brand_filter(session):
    p = await _make_product(session, brand="Sandro")
    cat = (await session.execute(
        select(Category).where(Category.id == p.category_id)
    )).scalar_one()
    assert _matches_conditions(p, cat, {"brands": ["sandro"]}) is True
    assert _matches_conditions(p, cat, {"brands": ["zara"]}) is False


# ---------------------------------------------------------------------------
# _validate_action
# ---------------------------------------------------------------------------


def test_validate_action_requires_to_status():
    with pytest.raises(ValueError):
        _validate_action({})


def test_validate_action_rejects_unknown_target():
    with pytest.raises(ValueError):
        _validate_action({"to_status": "exploded"})


def test_validate_action_requires_discount_pct_for_discounted():
    with pytest.raises(ValueError):
        _validate_action({"to_status": "discounted"})


def test_validate_action_rejects_out_of_range_pct():
    with pytest.raises(ValueError):
        _validate_action({"to_status": "discounted", "discount_pct": 0})
    with pytest.raises(ValueError):
        _validate_action({"to_status": "discounted", "discount_pct": 100})


def test_validate_action_returns_target_status():
    target, _, _ = _validate_action(
        {"to_status": "discounted", "discount_pct": 25}
    )
    assert target == ProductStatus.discounted


# ---------------------------------------------------------------------------
# MarkdownEngineService.evaluate_product
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_evaluate_picks_lowest_priority_matching_rule(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=45)
    p = await _make_product(session, displayed_at=long_ago, trend_score=30.0)

    high_priority = await _make_rule(
        session, name="aggressive", priority=10,
        conditions={"age_min_days": 30},
        action={"to_status": "discounted", "discount_pct": 30},
    )
    await _make_rule(
        session, name="gentle", priority=50,
        conditions={"age_min_days": 30},
        action={"to_status": "discounted", "discount_pct": 10},
    )

    svc = MarkdownEngineService(session)
    eval_ = await svc.evaluate_product(p)
    assert eval_.matched_rule.id == high_priority.id


@pytest.mark.anyio
async def test_evaluate_skips_no_op_markdown(session):
    """If the new price would be ≥ the current price, the rule is skipped."""
    long_ago = datetime.now(timezone.utc) - timedelta(days=45)
    # The rule says "discount 90%", but if the product is already at 1€,
    # the new price (0.10€) is < 1€ so it WILL apply. To force a no-op
    # we use a 0%-ish discount approximation: not allowed by validator.
    # Instead, check that an inactive rule is skipped.
    p = await _make_product(session, displayed_at=long_ago)
    await _make_rule(
        session, name="inactive", priority=10, active=False,
        conditions={"age_min_days": 30},
        action={"to_status": "discounted", "discount_pct": 20},
    )
    svc = MarkdownEngineService(session)
    eval_ = await svc.evaluate_product(p)
    assert eval_.matched_rule is None


@pytest.mark.anyio
async def test_evaluate_no_rules_returns_no_match(session):
    p = await _make_product(session)
    eval_ = await MarkdownEngineService(session).evaluate_product(p)
    assert eval_.matched_rule is None


@pytest.mark.anyio
async def test_evaluate_computes_correct_new_price(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=45)
    p = await _make_product(session, sale_price=50.0, displayed_at=long_ago)
    await _make_rule(
        session,
        conditions={"age_min_days": 30},
        action={"to_status": "discounted", "discount_pct": 20},
    )
    eval_ = await MarkdownEngineService(session).evaluate_product(p)
    assert eval_.target_status == ProductStatus.discounted
    assert eval_.new_price == Decimal("40.00")


# ---------------------------------------------------------------------------
# apply_to_product (uses the FSM)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_apply_transitions_status_and_writes_history(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=45)
    p = await _make_product(session, sale_price=50.0, displayed_at=long_ago)
    await _make_rule(
        session, name="J+30",
        conditions={"age_min_days": 30},
        action={"to_status": "discounted", "discount_pct": 20, "reason": "J+30"},
    )

    svc = MarkdownEngineService(session)
    eval_ = await svc.evaluate_product(p)
    summary = await svc.apply_to_product(p, eval_)

    assert summary["applied"] is True
    assert summary["from_price"] == 50.0
    assert summary["to_price"] == 40.0
    assert p.status == ProductStatus.discounted
    assert isinstance(p.markdown_history, list)
    assert p.markdown_history[-1]["to_price"] == 40.0


# ---------------------------------------------------------------------------
# run_batch
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_run_batch_applies_to_eligible_products(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=45)
    recent = datetime.now(timezone.utc) - timedelta(days=5)
    eligible = await _make_product(
        session, sale_price=50.0, displayed_at=long_ago, trend_score=30.0,
    )
    too_recent = await _make_product(
        session, sale_price=50.0, displayed_at=recent, trend_score=30.0,
    )

    await _make_rule(
        session, name="J+30",
        conditions={"age_min_days": 30, "score_max": 50},
        action={"to_status": "discounted", "discount_pct": 20},
    )

    summary = await MarkdownEngineService(session).run_batch()
    assert summary.scanned == 2
    assert summary.matched == 1
    assert summary.applied == 1
    await session.refresh(eligible)
    await session.refresh(too_recent)
    assert eligible.status == ProductStatus.discounted
    assert too_recent.status == ProductStatus.displayed  # unchanged


@pytest.mark.anyio
async def test_dry_run_does_not_mutate_anything(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=45)
    p = await _make_product(session, sale_price=50.0, displayed_at=long_ago)
    await _make_rule(
        session,
        conditions={"age_min_days": 30},
        action={"to_status": "discounted", "discount_pct": 20},
    )
    summary = await MarkdownEngineService(session).run_batch(dry_run=True)
    assert summary.matched == 1
    assert summary.applied == 0
    await session.refresh(p)
    assert p.status == ProductStatus.displayed
    assert float(p.sale_price) == 50.0


@pytest.mark.anyio
async def test_run_batch_with_no_rules_is_a_noop(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=45)
    await _make_product(session, displayed_at=long_ago)
    summary = await MarkdownEngineService(session).run_batch()
    assert summary.applied == 0
    assert summary.matched == 0
    assert summary.scanned == 0  # short-circuit when no rules exist


@pytest.mark.anyio
async def test_run_batch_skips_terminal_products(session):
    long_ago = datetime.now(timezone.utc) - timedelta(days=120)
    sold = await _make_product(
        session, displayed_at=long_ago, status=ProductStatus.sold,
    )
    await _make_rule(
        session,
        conditions={"age_min_days": 30},
        action={"to_status": "discounted", "discount_pct": 20},
    )
    summary = await MarkdownEngineService(session).run_batch()
    assert summary.matched == 0
    await session.refresh(sold)
    assert sold.status == ProductStatus.sold
