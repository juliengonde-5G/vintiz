"""Tests for the intake batch service (P2-015)."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.batch import IntakeBatch, IntakeSource
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.user import User, UserRole
from app.services.batch import BatchService


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
        IntakeBatch.__table__,
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
# Batch number generation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_batch_assigns_monthly_sequence(session):
    svc = BatchService(session)
    fixed = datetime(2026, 4, 26, 10, 0, 0, tzinfo=timezone.utc)
    a = await svc.create_batch(
        source=IntakeSource.sorting_center,
        received_at=fixed,
        n_items_received=42,
    )
    b = await svc.create_batch(
        source=IntakeSource.sorting_center, received_at=fixed
    )
    assert a.batch_number == "BATCH-2026-04-0001"
    assert b.batch_number == "BATCH-2026-04-0002"


@pytest.mark.anyio
async def test_batch_number_resets_per_month(session):
    svc = BatchService(session)
    a = await svc.create_batch(
        source=IntakeSource.sorting_center,
        received_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )
    b = await svc.create_batch(
        source=IntakeSource.sorting_center,
        received_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    assert a.batch_number == "BATCH-2026-04-0001"
    assert b.batch_number == "BATCH-2026-05-0001"


@pytest.mark.anyio
async def test_create_batch_rejects_negative_count(session):
    from fastapi import HTTPException

    svc = BatchService(session)
    with pytest.raises(HTTPException) as exc:
        await svc.create_batch(
            source=IntakeSource.sorting_center, n_items_received=-3
        )
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Listing + read
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_batches_returns_newest_first_with_tagged_count(session):
    svc = BatchService(session)
    older = await svc.create_batch(
        source=IntakeSource.deposit,
        received_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    newer = await svc.create_batch(
        source=IntakeSource.sorting_center,
        received_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
        n_items_received=10,
    )

    # Tag two products to the newer batch.
    cat = Category(name="Robes")
    session.add(cat)
    await session.flush()
    for i in range(2):
        p = Product(
            barcode=f"B-{i}-{uuid.uuid4().hex[:6]}",
            name=f"Robe {i}",
            category_id=cat.id,
            sale_price=49.0,
            status=ProductStatus.tagged,
            intake_batch_id=newer.id,
        )
        session.add(p)
    await session.flush()

    rows = await svc.list_batches()
    assert [r["batch_number"] for r in rows][0] == newer.batch_number
    assert rows[0]["n_items_tagged"] == 2
    assert rows[1]["n_items_tagged"] == 0


@pytest.mark.anyio
async def test_get_batch_returns_attached_products(session):
    svc = BatchService(session)
    batch = await svc.create_batch(source=IntakeSource.sorting_center)

    cat = Category(name="Pulls")
    session.add(cat)
    await session.flush()
    p = Product(
        barcode="B-1",
        name="Pull",
        category_id=cat.id,
        sale_price=29.0,
        status=ProductStatus.tagged,
        intake_batch_id=batch.id,
    )
    session.add(p)
    await session.flush()

    detail = await svc.get_batch(batch.id)
    assert detail["batch_number"] == batch.batch_number
    assert detail["n_items_tagged"] == 1
    assert detail["products"][0]["barcode"] == "B-1"


@pytest.mark.anyio
async def test_get_batch_unknown_raises_404(session):
    from fastapi import HTTPException

    svc = BatchService(session)
    with pytest.raises(HTTPException) as exc:
        await svc.get_batch(uuid.uuid4())
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Assign existing product
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_assign_product_to_existing_batch(session):
    svc = BatchService(session)
    batch = await svc.create_batch(source=IntakeSource.sorting_center)

    cat = Category(name="Sacs")
    session.add(cat)
    await session.flush()
    p = Product(
        barcode="P-X",
        name="Sac",
        category_id=cat.id,
        sale_price=20.0,
        status=ProductStatus.received,
    )
    session.add(p)
    await session.flush()
    assert p.intake_batch_id is None

    await svc.assign_product(batch.id, p.id)
    assert p.intake_batch_id == batch.id


@pytest.mark.anyio
async def test_assign_product_unknown_batch_raises_404(session):
    from fastapi import HTTPException

    cat = Category(name="Sacs")
    session.add(cat)
    await session.flush()
    p = Product(
        barcode="P-Y",
        name="Sac",
        category_id=cat.id,
        sale_price=20.0,
        status=ProductStatus.received,
    )
    session.add(p)
    await session.flush()

    svc = BatchService(session)
    with pytest.raises(HTTPException) as exc:
        await svc.assign_product(uuid.uuid4(), p.id)
    assert exc.value.status_code == 404
