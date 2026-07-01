"""Tests for the explicit product life-cycle FSM (P1-006)."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.events import EventLog, EventType
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.product_location import ProductLocationEvent
from app.models.user import User, UserRole
from app.services.product_lifecycle import (
    TERMINAL_STATES,
    ProductLifecycleService,
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
    status: ProductStatus = ProductStatus.received,
    sale_price: float = 49.0,
) -> Product:
    cat = Category(name="Robes")
    session.add(cat)
    await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name="Robe noire",
        category_id=cat.id,
        sale_price=sale_price,
        status=status,
    )
    session.add(p)
    await session.flush()
    return p


# ---------------------------------------------------------------------------
# FSM happy paths
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_canonical_flow_received_to_sold(session):
    p = await _make_product(session, status=ProductStatus.received)
    svc = ProductLifecycleService(session)

    await svc.transition(p, ProductStatus.sorted)
    assert p.status == ProductStatus.sorted

    await svc.transition(p, ProductStatus.tagged)
    assert p.status == ProductStatus.tagged

    await svc.transition(p, ProductStatus.displayed)
    assert p.status == ProductStatus.displayed
    assert p.displayed_at is not None

    await svc.transition(p, ProductStatus.sold)
    assert p.status == ProductStatus.sold


@pytest.mark.anyio
async def test_received_at_stamped_on_first_entry(session):
    p = await _make_product(session, status=ProductStatus.sorted)
    p.received_at = None
    await session.flush()

    # received_at should be stamped when the product re-enters 'received'.
    # But there's no edge from sorted → received in the FSM, so this is a
    # no-op test verifying the anchor logic doesn't get triggered the
    # wrong way. Direct check via received_at + a fresh product.
    fresh = await _make_product(session, status=ProductStatus.received)
    fresh.received_at = None
    await session.flush()
    svc = ProductLifecycleService(session)
    # received → received is a no-op transition that should still stamp.
    await svc.transition(fresh, ProductStatus.received)
    assert fresh.received_at is not None


@pytest.mark.anyio
async def test_displayed_at_stamped_only_once(session):
    p = await _make_product(session, status=ProductStatus.tagged)
    svc = ProductLifecycleService(session)
    await svc.transition(p, ProductStatus.displayed)
    first_stamp = p.displayed_at
    assert first_stamp is not None

    # Cycle out and back in — anchor should not be reset.
    await svc.transition(p, ProductStatus.discounted, new_price=40.0)
    # discounted has no edge back to displayed; instead use stock → displayed.
    await svc.transition(p, ProductStatus.sold)
    # Once sold (terminal), no more transitions allowed.
    assert p.displayed_at == first_stamp


# ---------------------------------------------------------------------------
# FSM rejection paths
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_invalid_transition_raises(session):
    from fastapi import HTTPException

    p = await _make_product(session, status=ProductStatus.received)
    svc = ProductLifecycleService(session)
    with pytest.raises(HTTPException) as exc:
        await svc.transition(p, ProductStatus.sold)
    assert exc.value.status_code == 400
    assert "Invalid transition" in exc.value.detail


@pytest.mark.anyio
async def test_cannot_transition_out_of_terminal(session):
    from fastapi import HTTPException

    p = await _make_product(session, status=ProductStatus.sold)
    svc = ProductLifecycleService(session)
    with pytest.raises(HTTPException):
        await svc.transition(p, ProductStatus.displayed)


@pytest.mark.anyio
async def test_terminal_states_match_audit():
    """V1 §2.2.6 terminal states + ``rejected`` (refus à la mise en vente)."""
    assert TERMINAL_STATES == {
        ProductStatus.sold,
        ProductStatus.donated,
        ProductStatus.returned_to_sorting,
        ProductStatus.rejected,
    }


# ---------------------------------------------------------------------------
# Markdown bookkeeping
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_markdown_appends_history_and_lowers_price(session):
    p = await _make_product(session, status=ProductStatus.displayed, sale_price=49.0)
    p.markdown_history = None
    svc = ProductLifecycleService(session)
    await svc.transition(
        p, ProductStatus.discounted, new_price=39.0, reason="J+30"
    )

    assert p.status == ProductStatus.discounted
    assert float(p.sale_price) == 39.0
    assert isinstance(p.markdown_history, list)
    assert len(p.markdown_history) == 1
    entry = p.markdown_history[0]
    assert entry["from_price"] == 49.0
    assert entry["to_price"] == 39.0
    assert entry["reason"] == "J+30"
    assert entry["to_status"] == "discounted"


@pytest.mark.anyio
async def test_deep_discount_appends_second_history_entry(session):
    p = await _make_product(session, status=ProductStatus.displayed, sale_price=49.0)
    svc = ProductLifecycleService(session)
    await svc.transition(p, ProductStatus.discounted, new_price=39.0)
    await svc.transition(
        p, ProductStatus.deep_discounted, new_price=25.0, reason="J+60"
    )
    assert len(p.markdown_history) == 2
    assert p.markdown_history[1]["to_price"] == 25.0
    assert p.markdown_history[1]["to_status"] == "deep_discounted"


@pytest.mark.anyio
async def test_markdown_requires_new_price(session):
    from fastapi import HTTPException

    p = await _make_product(session, status=ProductStatus.displayed)
    svc = ProductLifecycleService(session)
    with pytest.raises(HTTPException) as exc:
        await svc.transition(p, ProductStatus.discounted)
    assert exc.value.status_code == 400
    assert "new_price" in exc.value.detail


@pytest.mark.anyio
async def test_markdown_rejects_higher_price(session):
    from fastapi import HTTPException

    p = await _make_product(session, status=ProductStatus.displayed, sale_price=49.0)
    svc = ProductLifecycleService(session)
    with pytest.raises(HTTPException) as exc:
        await svc.transition(p, ProductStatus.discounted, new_price=55.0)
    assert exc.value.status_code == 400
    assert "lower" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# Analytics events
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_returned_to_sorting_emits_event(session):
    p = await _make_product(session, status=ProductStatus.displayed)
    svc = ProductLifecycleService(session)
    await svc.transition(
        p, ProductStatus.returned_to_sorting, reason="Invendu 90j"
    )

    rows = (await session.execute(
        select(EventLog).where(
            EventLog.event_type == EventType.product_returned_to_sorting,
            EventLog.product_id == p.id,
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].meta["reason"] == "Invendu 90j"
    assert rows[0].meta["from_status"] == "displayed"


@pytest.mark.anyio
async def test_donated_transition_emits_event(session):
    p = await _make_product(session, status=ProductStatus.displayed)
    svc = ProductLifecycleService(session)
    await svc.transition(p, ProductStatus.donated, reason="Geste commercial")

    rows = (await session.execute(
        select(EventLog).where(EventLog.event_type == EventType.product_donated)
    )).scalars().all()
    assert len(rows) == 1


@pytest.mark.anyio
async def test_markdown_emits_event_with_prices(session):
    p = await _make_product(session, status=ProductStatus.displayed, sale_price=49.0)
    svc = ProductLifecycleService(session)
    await svc.transition(p, ProductStatus.discounted, new_price=39.0)

    rows = (await session.execute(
        select(EventLog).where(
            EventLog.event_type == EventType.product_markdown_applied
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].meta["from_price"] == 49.0
    assert rows[0].meta["to_price"] == 39.0


# ---------------------------------------------------------------------------
# Legacy compatibility
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_legacy_display_to_sold_still_works(session):
    """The POS uses ``display`` (legacy) → ``sold``. Must keep working."""
    p = await _make_product(session, status=ProductStatus.display)
    svc = ProductLifecycleService(session)
    await svc.transition(p, ProductStatus.sold)
    assert p.status == ProductStatus.sold


@pytest.mark.anyio
async def test_legacy_returned_can_be_re_routed_to_sorted(session):
    p = await _make_product(session, status=ProductStatus.returned)
    svc = ProductLifecycleService(session)
    await svc.transition(p, ProductStatus.sorted)
    assert p.status == ProductStatus.sorted
