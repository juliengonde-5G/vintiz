"""Tests for POS submission idempotence via client_uuid (P1-005).

The POS UI buffers transactions in an IndexedDB queue when offline.
On reconnect, each one is replayed against POST /api/pos/transactions.
The client generates a UUID before the first attempt; the backend uses
it to short-circuit duplicates.
"""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    AvoirTransaction,
    Client,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.pos import (
    Payment,
    PaymentMethod,
    Receipt,
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.user import User, UserRole
from app.services.pos import PosService


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
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        AvoirTransaction.__table__,
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
    user = User(
        username="cashier", email="c@vintiz.fr",
        password_hash="x" * 60, role=UserRole.collaborateur, is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _make_product(session: AsyncSession, sale_price: float = 49.0) -> Product:
    cat = Category(name="Robes")
    session.add(cat)
    await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name="Robe",
        category_id=cat.id,
        sale_price=sale_price,
        status=ProductStatus.display,
    )
    session.add(p)
    await session.flush()
    return p


def _cart_item(product: Product, qty: int = 1):
    return SimpleNamespace(
        product_id=product.id,
        name=None,
        quantity=qty,
        unit_price=float(product.sale_price),
        discount_percent=0,
    )


def _payment(method: str, amount: float):
    return SimpleNamespace(method=method, amount=amount)


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_repeated_submission_with_same_client_uuid_returns_existing(session):
    """Two POSTs carrying the same client_uuid must yield exactly one
    Transaction row — and the second call returns the original."""
    user = await _make_user(session)
    product = await _make_product(session, sale_price=49.0)
    cuuid = uuid.uuid4()

    svc = PosService(session)
    first = await svc.create_transaction(
        user_id=user.id,
        items=[_cart_item(product)],
        payments=[_payment("cash", 49.0)],
        client_uuid=cuuid,
    )
    assert first.client_uuid == cuuid

    # Second submission — same UUID. The product is already sold so the
    # naive code path would 400; idempotence must short-circuit before that.
    second = await svc.create_transaction(
        user_id=user.id,
        items=[_cart_item(product)],
        payments=[_payment("cash", 49.0)],
        client_uuid=cuuid,
    )

    assert second.id == first.id
    assert second.transaction_number == first.transaction_number

    # Only one row in the table.
    rows = (await session.execute(
        select(Transaction).where(Transaction.client_uuid == cuuid)
    )).scalars().all()
    assert len(rows) == 1


@pytest.mark.anyio
async def test_different_client_uuid_creates_distinct_transactions(session):
    """Distinct UUIDs → distinct rows (sanity check on the index)."""
    user = await _make_user(session)
    p1 = await _make_product(session, sale_price=10.0)
    p2 = await _make_product(session, sale_price=20.0)

    svc = PosService(session)
    first = await svc.create_transaction(
        user_id=user.id, items=[_cart_item(p1)], payments=[_payment("cash", 10.0)],
        client_uuid=uuid.uuid4(),
    )
    second = await svc.create_transaction(
        user_id=user.id, items=[_cart_item(p2)], payments=[_payment("cash", 20.0)],
        client_uuid=uuid.uuid4(),
    )
    assert first.id != second.id
    assert first.transaction_number != second.transaction_number


@pytest.mark.anyio
async def test_no_client_uuid_does_not_short_circuit(session):
    """Legacy callers that don't supply a client_uuid keep working —
    each POST still creates a fresh transaction."""
    user = await _make_user(session)
    p1 = await _make_product(session, sale_price=10.0)
    p2 = await _make_product(session, sale_price=20.0)

    svc = PosService(session)
    a = await svc.create_transaction(
        user_id=user.id, items=[_cart_item(p1)], payments=[_payment("cash", 10.0)],
    )
    b = await svc.create_transaction(
        user_id=user.id, items=[_cart_item(p2)], payments=[_payment("cash", 20.0)],
    )
    assert a.id != b.id
    assert a.client_uuid is None
    assert b.client_uuid is None


@pytest.mark.anyio
async def test_replay_does_not_re_validate_stock(session):
    """If a product was sold via the first attempt, the replay must NOT
    trip on "product not for sale" — short-circuiting happens before
    the stock check."""
    user = await _make_user(session)
    product = await _make_product(session, sale_price=49.0)
    cuuid = uuid.uuid4()

    svc = PosService(session)
    first = await svc.create_transaction(
        user_id=user.id,
        items=[_cart_item(product)],
        payments=[_payment("cash", 49.0)],
        client_uuid=cuuid,
    )
    # The product is now sold. Simulate the exact replay payload.
    second = await svc.create_transaction(
        user_id=user.id,
        items=[_cart_item(product)],   # same payload
        payments=[_payment("cash", 49.0)],
        client_uuid=cuuid,
    )
    assert second.id == first.id


@pytest.mark.anyio
async def test_replay_with_different_payload_still_returns_original(session):
    """Even if the replay carries a slightly different payload (a UI bug),
    the idempotence key wins — we must not create a second row that
    silently differs from the first."""
    user = await _make_user(session)
    product = await _make_product(session, sale_price=49.0)
    cuuid = uuid.uuid4()

    svc = PosService(session)
    original = await svc.create_transaction(
        user_id=user.id,
        items=[_cart_item(product)],
        payments=[_payment("cash", 49.0)],
        client_uuid=cuuid,
    )

    # Simulate a slightly different replay payload (different qty).
    p2 = await _make_product(session, sale_price=10.0)
    replay = await svc.create_transaction(
        user_id=user.id,
        items=[_cart_item(p2)],  # totally different cart!
        payments=[_payment("cash", 10.0)],
        client_uuid=cuuid,
    )
    # Same id, same number, original totals preserved.
    assert replay.id == original.id
    assert float(replay.total_ttc) == 49.0
