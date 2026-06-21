"""Tests for the embedded reporting engine (requêteur sur-mesure)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Gender, Product, ProductStatus
from app.models.user import User
from app.services import reporting_engine as eng


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng_ = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        Category.__table__, Product.__table__, User.__table__,
        Transaction.__table__, TransactionItem.__table__,
    ]
    async with eng_.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    yield eng_
    await eng_.dispose()


@pytest.fixture
async def session(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


async def _seed_sales(session):
    user = User(username="caisse", email="c@vintiz.fr", password_hash="x")
    robes = Category(name="Robes", gender=Gender.femme)
    pulls = Category(name="Pulls", gender=Gender.femme)
    session.add_all([user, robes, pulls])
    await session.flush()

    p_robe = Product(barcode=f"B-{uuid.uuid4().hex[:6]}", name="Robe", category_id=robes.id,
                     status=ProductStatus.sold, sale_price=40, purchase_price=10, brand="Sandro")
    p_pull = Product(barcode=f"B-{uuid.uuid4().hex[:6]}", name="Pull", category_id=pulls.id,
                     status=ProductStatus.sold, sale_price=20, purchase_price=5, brand="Zara")
    session.add_all([p_robe, p_pull])
    await session.flush()

    now = datetime.now(timezone.utc)
    # Two sales this month, one a refund (must be excluded from "sales").
    tx1 = Transaction(transaction_number=1, transaction_type=TransactionType.sale,
                      user_id=user.id, total_ttc=40, hash_chain="h1", created_at=now)
    tx2 = Transaction(transaction_number=2, transaction_type=TransactionType.sale,
                      user_id=user.id, total_ttc=20, hash_chain="h2", created_at=now)
    tx3 = Transaction(transaction_number=3, transaction_type=TransactionType.refund,
                      user_id=user.id, total_ttc=-40, hash_chain="h3", created_at=now)
    session.add_all([tx1, tx2, tx3])
    await session.flush()
    session.add_all([
        TransactionItem(transaction_id=tx1.id, product_id=p_robe.id, quantity=1, unit_price=40, line_total=40),
        TransactionItem(transaction_id=tx2.id, product_id=p_pull.id, quantity=2, unit_price=10, line_total=20),
        TransactionItem(transaction_id=tx3.id, product_id=p_robe.id, quantity=1, unit_price=40, line_total=40),
    ])
    await session.flush()
    return now


def test_catalog_lists_datasets_and_measures():
    cat = eng.catalog()
    keys = {d["key"] for d in cat["datasets"]}
    assert {"sales", "inventory", "clients"} <= keys
    sales = next(d for d in cat["datasets"] if d["key"] == "sales")
    measure_keys = {m["key"] for m in sales["measures"]}
    assert "revenue" in measure_keys
    assert "month" in cat["granularities"]
    assert "bar" in cat["chart_types"]


@pytest.mark.anyio
async def test_revenue_by_category_excludes_refunds(session):
    await _seed_sales(session)
    res = await eng.run_query(session, dataset="sales", measure="revenue", dimension="category")
    by_key = {r["key"]: r["value"] for r in res["rows"]}
    # Only the two SALE lines count; the refund line is excluded.
    assert by_key["Robes"] == 40.0
    assert by_key["Pulls"] == 20.0
    assert res["format"] == "currency"


@pytest.mark.anyio
async def test_total_kpi_without_dimension(session):
    await _seed_sales(session)
    res = await eng.run_query(session, dataset="sales", measure="revenue")
    assert len(res["rows"]) == 1
    assert res["rows"][0]["value"] == 60.0  # 40 + 20, refund excluded


@pytest.mark.anyio
async def test_quantity_and_tickets(session):
    await _seed_sales(session)
    qty = await eng.run_query(session, dataset="sales", measure="quantity")
    assert qty["rows"][0]["value"] == 3.0  # 1 + 2
    tickets = await eng.run_query(session, dataset="sales", measure="tickets")
    assert tickets["rows"][0]["value"] == 2.0  # two sale transactions


@pytest.mark.anyio
async def test_time_dimension_buckets_by_month(session):
    await _seed_sales(session)
    res = await eng.run_query(session, dataset="sales", measure="revenue",
                              dimension="time", granularity="month")
    assert res["granularity"] == "month"
    assert len(res["rows"]) == 1  # all in the same month
    assert res["rows"][0]["value"] == 60.0


@pytest.mark.anyio
async def test_date_range_filters_out_old_sales(session):
    now = await _seed_sales(session)
    # Window that ends before "now" → excludes the sales.
    res = await eng.run_query(
        session, dataset="sales", measure="revenue",
        date_from=now - timedelta(days=40), date_to=now - timedelta(days=1),
    )
    assert res["rows"][0]["value"] == 0.0


@pytest.mark.anyio
async def test_inventory_count_by_brand(session):
    await _seed_sales(session)
    # Add live-stock products (the sold ones above are excluded from inventory).
    cat = Category(name="Manteaux", gender=Gender.femme)
    session.add(cat)
    await session.flush()
    session.add_all([
        Product(barcode=f"B-{uuid.uuid4().hex[:6]}", name="M1", category_id=cat.id,
                status=ProductStatus.stock, sale_price=50, purchase_price=15, brand="Maje"),
        Product(barcode=f"B-{uuid.uuid4().hex[:6]}", name="M2", category_id=cat.id,
                status=ProductStatus.display, sale_price=60, purchase_price=20, brand="Maje"),
    ])
    await session.flush()
    res = await eng.run_query(session, dataset="inventory", measure="count", dimension="brand")
    by_key = {r["key"]: r["value"] for r in res["rows"]}
    assert by_key.get("Maje") == 2.0


@pytest.mark.anyio
async def test_margin_measure(session):
    await _seed_sales(session)
    # Robe: 40 - 1*10 = 30 ; Pull: 20 - 2*5 = 10 ; total margin = 40 (refund excluded).
    res = await eng.run_query(session, dataset="sales", measure="margin")
    assert res["rows"][0]["value"] == 40.0


@pytest.mark.anyio
async def test_dimension_values_for_filter(session):
    await _seed_sales(session)
    vals = await eng.dimension_values(session, "sales", "category")
    assert set(vals) == {"Robes", "Pulls"}
    brands = await eng.dimension_values(session, "sales", "brand")
    assert "Sandro" in brands and "Zara" in brands


@pytest.mark.anyio
async def test_filter_narrows_query(session):
    await _seed_sales(session)
    res = await eng.run_query(session, dataset="sales", measure="revenue", filters={"category": "Robes"})
    assert res["rows"][0]["value"] == 40.0  # only the Robes sale


@pytest.mark.anyio
async def test_dimension_values_rejects_time(session):
    with pytest.raises(ValueError):
        await eng.dimension_values(session, "sales", "time")


@pytest.mark.anyio
async def test_unknown_dataset_or_measure_raises(session):
    with pytest.raises(ValueError):
        await eng.run_query(session, dataset="nope", measure="revenue")
    with pytest.raises(ValueError):
        await eng.run_query(session, dataset="sales", measure="nope")
    with pytest.raises(ValueError):
        await eng.run_query(session, dataset="sales", measure="revenue", dimension="nope")
