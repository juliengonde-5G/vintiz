"""Tests for the stock-movement module (flux vertical / horizontal).

Couvre l'historisation (record_move), l'exécution scan (move_by_barcode),
la timeline fiche (location_history), les deux moteurs de proposition
(weekly_layout_plan / restock_plan) et les métriques (stock_movement_metrics).
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.events import EventLog, EventType
from app.models.product import Category, Gender, Product, ProductPhoto, ProductStatus
from app.models.product_location import LocationMoveType, ProductLocationEvent
from app.models.pos import Transaction, TransactionItem
from app.models.store import FurnitureItem, StoreZone, ZoneProduct, ZoneTag
from app.models.user import User
from app.services import stock_movement as sm
from app.services.stock_metrics import stock_movement_metrics


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Category.__table__,
        StoreZone.__table__,
        ZoneTag.__table__,
        FurnitureItem.__table__,
        ZoneProduct.__table__,
        Product.__table__,
        ProductPhoto.__table__,
        EventLog.__table__,
        ProductLocationEvent.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
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


async def _zone(session, name, **kw) -> StoreZone:
    z = StoreZone(name=name, capacity=kw.pop("capacity", 20), **kw)
    session.add(z)
    await session.flush()
    return z


async def _product(session, **kw) -> Product:
    cat = kw.pop("category", None)
    if cat is None:
        cat = Category(name="Robes", gender=Gender.femme)
        session.add(cat)
        await session.flush()
    p = Product(
        barcode=kw.pop("barcode", f"P-{uuid.uuid4().hex[:8]}"),
        name=kw.pop("name", "Robe noire"),
        category_id=cat.id,
        sale_price=kw.pop("sale_price", 30.0),
        status=kw.pop("status", ProductStatus.stock),
        **kw,
    )
    session.add(p)
    await session.flush()
    return p


# ---------------------------------------------------------------------------
# Classification (pure function)
# ---------------------------------------------------------------------------


def test_classify_move_vertical_and_horizontal():
    z1, z2 = uuid.uuid4(), uuid.uuid4()
    assert sm.classify_move(
        ProductStatus.stock, ProductStatus.displayed, None, z1
    ) == LocationMoveType.to_floor
    assert sm.classify_move(
        ProductStatus.displayed, ProductStatus.stock, z1, None
    ) == LocationMoveType.to_stock
    assert sm.classify_move(
        ProductStatus.displayed, ProductStatus.displayed, z1, z2
    ) == LocationMoveType.zone_change
    assert sm.classify_move(
        ProductStatus.displayed, ProductStatus.returned_to_sorting, z1, z1
    ) == LocationMoveType.exit
    # Pure markdown rayon→rayon, same zone → no physical relocation.
    assert sm.classify_move(
        ProductStatus.displayed, ProductStatus.discounted, z1, z1
    ) is None


# ---------------------------------------------------------------------------
# record_move + location_history
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_move_by_barcode_vertical_records_to_floor(session):
    zone = await _zone(session, "Tendance")
    p = await _product(session, status=ProductStatus.stock, barcode="BC-123")

    product, event = await sm.move_by_barcode(
        session, "BC-123",
        to_status=ProductStatus.displayed, to_zone_id=zone.id, source="scan",
    )
    assert product.status == ProductStatus.displayed
    assert product.zone_id == zone.id
    # A piece coming up from the réserve straight into a zone = a single,
    # clean to_floor event (not a to_floor + a zone_change).
    assert event.move_type == LocationMoveType.to_floor
    assert event.to_zone_id == zone.id

    history = await sm.location_history(session, p.id)
    assert len(history) == 1
    assert history[0]["move_type"] == "to_floor"
    assert history[0]["to_zone_name"] == "Tendance"


@pytest.mark.anyio
async def test_zone_change_records_horizontal_and_emits_event(session):
    z1 = await _zone(session, "Entrée")
    z2 = await _zone(session, "Vitrine")
    p = await _product(session, status=ProductStatus.displayed, barcode="BC-9")
    p.zone_id = z1.id
    await session.flush()

    _, event = await sm.move_by_barcode(session, "BC-9", to_zone_id=z2.id)
    assert event.move_type == LocationMoveType.zone_change
    assert event.from_zone_id == z1.id and event.to_zone_id == z2.id

    # The long-dormant analytics event is now emitted on horizontal moves.
    evs = (await session.execute(
        select(EventLog).where(EventLog.event_type == EventType.product_zone_changed)
    )).scalars().all()
    assert len(evs) == 1
    assert evs[0].product_id == p.id


@pytest.mark.anyio
async def test_move_by_barcode_unknown_barcode_raises(session):
    with pytest.raises(sm.MovementError):
        await sm.move_by_barcode(session, "NOPE", to_status=ProductStatus.displayed)


# ---------------------------------------------------------------------------
# Proposal engines
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_restock_plan_proposes_stock_for_empty_zone(session):
    cat = Category(name="Robes", gender=Gender.femme)
    session.add(cat)
    await session.flush()
    # An (almost) empty women's zone + matching stock pieces to bring up.
    await _zone(session, "Femme", capacity=10, match_genders=["femme"])
    for i in range(3):
        await _product(
            session, category=cat, status=ProductStatus.stock,
            gender=Gender.femme, trend_score=70.0, barcode=f"S-{i}",
        )

    plan = await sm.restock_plan(session)
    zones = {z["zone_name"]: z for z in plan["zones"]}
    assert "Femme" in zones
    assert zones["Femme"]["candidates"], "stock matching the zone should be proposed"


@pytest.mark.anyio
async def test_weekly_layout_plan_proposes_horizontal_moves(session):
    cat = Category(name="Robes", gender=Gender.femme)
    session.add(cat)
    await session.flush()
    misc = await _zone(session, "Divers", capacity=20, assignment_priority=200)
    await _zone(
        session, "Femme", capacity=20, assignment_priority=10, match_genders=["femme"]
    )
    # A women's piece sitting in the catch-all zone should be proposed to move
    # into the dedicated women's zone.
    p = await _product(
        session, category=cat, status=ProductStatus.displayed,
        gender=Gender.femme, trend_score=40.0,
    )
    p.zone_id = misc.id
    await session.flush()

    plan = await sm.weekly_layout_plan(session)
    assert plan["total_moves"] >= 1
    targets = {
        item["to_zone_name"]
        for z in plan["zones"] for item in z["items"]
    }
    assert "Femme" in targets


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_stock_movement_metrics_shape(session):
    await _product(session, status=ProductStatus.stock)
    await _product(session, status=ProductStatus.displayed)
    # One historised vertical move so the rhythm section is non-empty.
    await _product(session, status=ProductStatus.stock, barcode="M-1")
    await sm.move_by_barcode(session, "M-1", to_status=ProductStatus.displayed)

    metrics = await stock_movement_metrics(session, period_days=30)
    assert metrics["repartition"]["reserve"]["count"] >= 1
    assert metrics["repartition"]["floor"]["count"] >= 1
    assert metrics["repartition"]["floor_ratio"] is not None
    assert metrics["rhythm"]["vertical"]["to_floor"] >= 1
    assert "horizontal" in metrics["rhythm"]
    assert "sell_through_rate" in metrics["velocity"]
