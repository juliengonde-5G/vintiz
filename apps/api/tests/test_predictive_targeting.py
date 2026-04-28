"""Tests for predictive_targeting helpers (PR4)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import Client, LoyaltyAccount
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Product, ProductStatus
from app.models.user import User, UserRole
from app.services import predictive_targeting as pt


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as s:
        yield s
    await eng.dispose()


async def _seed_user(session) -> User:
    u = User(
        username="cashier", email="cashier@x.fr",
        password_hash="x" * 60, role=UserRole.manager, is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


async def _seed_member(session, *, email: str) -> Client:
    client = Client(first_name="A", last_name="B", email=email)
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(
        client_id=client.id, points=0,
        membership_number=f"V{abs(hash(email)) % 1_000_000:06d}",
    ))
    client.loyalty_subscribed_at = datetime.now(timezone.utc)
    client.loyalty_expires_at = datetime.now(timezone.utc) + timedelta(days=730)
    await session.flush()
    return client


async def _seed_sale(session, *, user: User, client: Client | None, product: Product, txn_no: int):
    tx = Transaction(
        transaction_number=txn_no,
        transaction_type=TransactionType.sale,
        user_id=user.id,
        client_id=client.id if client else None,
        total_ht=10,
        total_tva=2,
        total_ttc=12,
        hash_chain="0" * 64,
    )
    session.add(tx)
    await session.flush()
    session.add(TransactionItem(
        transaction_id=tx.id, product_id=product.id,
        quantity=1, unit_price=12, discount_percent=0, line_total=12,
    ))
    await session.flush()


@pytest.mark.anyio
async def test_weighted_sales_count_audience_all(session):
    user = await _seed_user(session)
    cat = Category(name="t-shirt")
    session.add(cat)
    await session.flush()
    product = Product(
        barcode="V70001", name="T-shirt", category_id=cat.id,
        sale_price=12, condition="A", status=ProductStatus.sold,
    )
    session.add(product)
    await session.flush()

    member = await _seed_member(session, email="alice@x.fr")
    visitor = Client(first_name="B", last_name="V", email="b@x.fr")
    session.add(visitor)
    await session.flush()

    await _seed_sale(session, user=user, client=member, product=product, txn_no=1)
    await _seed_sale(session, user=user, client=visitor, product=product, txn_no=2)

    counts = await pt.weighted_sales_count(session, audience="all")
    assert counts[str(cat.id)] == 2.0


@pytest.mark.anyio
async def test_weighted_sales_count_loyal_active_falls_back_when_cohort_small(session):
    """Below MIN_COHORT_SIZE the audience switches back to flat counting."""
    user = await _seed_user(session)
    cat = Category(name="robe")
    session.add(cat)
    await session.flush()
    product = Product(
        barcode="V70002", name="Robe", category_id=cat.id,
        sale_price=49, condition="A", status=ProductStatus.sold,
    )
    session.add(product)
    await session.flush()

    member = await _seed_member(session, email="m@x.fr")
    await _seed_sale(session, user=user, client=member, product=product, txn_no=10)

    counts = await pt.weighted_sales_count(session, audience="loyal_active")
    # Cohort is 1 member → fallback to flat counting (no ×2).
    assert counts[str(cat.id)] == 1.0


@pytest.mark.anyio
async def test_dominant_tastes_loyal_active_aggregates(session):
    user = await _seed_user(session)
    cat = Category(name="robe")
    session.add(cat)
    await session.flush()
    product_a = Product(
        barcode="V70010", name="Robe rouge", category_id=cat.id,
        sale_price=49, condition="A", status=ProductStatus.sold,
        brand="Sezane", color="Rouge",
    )
    product_b = Product(
        barcode="V70011", name="Robe noire", category_id=cat.id,
        sale_price=39, condition="A", status=ProductStatus.sold,
        brand="Maje", color="Noir",
    )
    session.add_all([product_a, product_b])
    await session.flush()

    member = await _seed_member(session, email="alice@x.fr")
    visitor = Client(first_name="B", last_name="V", email="b@x.fr")
    session.add(visitor)
    await session.flush()

    await _seed_sale(session, user=user, client=member, product=product_a, txn_no=20)
    await _seed_sale(session, user=user, client=member, product=product_b, txn_no=21)
    # Visitor's purchase should be ignored.
    await _seed_sale(session, user=user, client=visitor, product=product_a, txn_no=22)

    result = await pt.dominant_tastes_loyal_active(session)
    assert result.cohort_size == 1
    cat_names = {n for n, _ in result.top_categories}
    brand_names = {n for n, _ in result.top_brands}
    assert "robe" in cat_names
    assert "Sezane" in brand_names
    assert "Maje" in brand_names
