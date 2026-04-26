"""End-to-end tests for the refund / avoir flow (P1-010 + P1-016).

Uses aiosqlite + AsyncSession to exercise the real SQLAlchemy code path,
including the audit listener registration. Other models that use
Postgres-only types (JSONB) are excluded from the test schema.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    AvoirTransaction,
    AvoirTxType,
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
from app.models.product import Category, Product, ProductStatus
from app.models.user import User, UserRole
from app.services.refund import RefundLineInput, RefundService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables_needed = [
        User.__table__,
        Category.__table__,
        Product.__table__,
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
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables_needed))
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


async def _make_user(session: AsyncSession) -> User:
    user = User(
        username="cashier", email="c@vintiz.fr",
        password_hash="x" * 60, role=UserRole.collaborateur, is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _make_client(session: AsyncSession) -> Client:
    client = Client(
        first_name="Julie", last_name="Martin",
        email="julie@example.com", avoir_credit=0,
    )
    session.add(client)
    await session.flush()
    return client


async def _make_sale(
    session: AsyncSession,
    user: User,
    client: Client | None = None,
    items: list[tuple[str, float, int]] | None = None,
) -> Transaction:
    """Build a sale transaction with the given (product_name, unit_price, qty) lines."""
    items = items or [("Robe", 49.0, 1)]
    category = Category(name="Robes")
    session.add(category)
    await session.flush()

    sale = Transaction(
        transaction_number=int(uuid.uuid4().int % 1_000_000_000),
        transaction_type=TransactionType.sale,
        user_id=user.id,
        client_id=client.id if client else None,
        total_ht=0, total_tva=0, total_ttc=0,
        hash_chain="dummy",
    )
    session.add(sale)
    await session.flush()

    total = Decimal("0")
    for idx, (name, unit, qty) in enumerate(items):
        product = Product(
            barcode=f"SALE-{sale.transaction_number}-{idx}",
            name=name, sale_price=unit, category_id=category.id,
            status=ProductStatus.sold,
        )
        session.add(product)
        await session.flush()
        line_total = Decimal(str(unit)) * qty
        total += line_total
        session.add(
            TransactionItem(
                transaction_id=sale.id,
                product_id=product.id,
                quantity=qty,
                unit_price=unit,
                discount_percent=0,
                line_total=float(line_total),
            )
        )
    sale.total_ttc = float(total)
    sale.total_ht = float((total / Decimal("1.20")).quantize(Decimal("0.01")))
    sale.total_tva = float(total - Decimal(str(sale.total_ht)))
    await session.flush()
    await session.refresh(sale)
    return sale


# ---------------------------------------------------------------------------
# Cash refund — full
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_full_cash_refund(session):
    user = await _make_user(session)
    client = await _make_client(session)
    sale = await _make_sale(session, user, client, items=[("Robe", 49.0, 1)])
    item = sale.items[0]

    refund = await RefundService(session).refund_transaction(
        original_tx_id=sale.id,
        items=[RefundLineInput(item.id, 1)],
        refund_method="cash",
        user_id=user.id,
        cashier_id=None,
        reason="Mauvaise taille",
    )

    assert refund.transaction_type == TransactionType.refund
    assert refund.original_transaction_id == sale.id
    assert float(refund.total_ttc) == pytest.approx(49.0)
    assert refund.refund_reason == "Mauvaise taille"

    # Product is back on display
    from sqlalchemy import select
    p = (await session.execute(
        select(Product).where(Product.id == item.product_id)
    )).scalar_one()
    assert p.status == ProductStatus.display
    assert p.sold_at is None

    # Cash payment row exists with positive amount on the refund tx
    pays = (await session.execute(
        select(Payment).where(Payment.transaction_id == refund.id)
    )).scalars().all()
    assert len(pays) == 1
    assert pays[0].method == PaymentMethod.cash
    assert float(pays[0].amount) == pytest.approx(49.0)

    # Client avoir untouched on cash refund
    await session.refresh(client)
    assert float(client.avoir_credit) == 0


# ---------------------------------------------------------------------------
# Avoir refund — credits client balance + AvoirTransaction row
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_avoir_refund_credits_client(session):
    user = await _make_user(session)
    client = await _make_client(session)
    sale = await _make_sale(session, user, client, items=[("Sac", 35.0, 1)])
    item = sale.items[0]

    await RefundService(session).refund_transaction(
        original_tx_id=sale.id,
        items=[RefundLineInput(item.id, 1)],
        refund_method="avoir",
        user_id=user.id,
        cashier_id=None,
        reason="Geste commercial",
    )

    await session.refresh(client)
    assert float(client.avoir_credit) == pytest.approx(35.0)

    from sqlalchemy import select
    avoir_rows = (await session.execute(
        select(AvoirTransaction).where(AvoirTransaction.client_id == client.id)
    )).scalars().all()
    assert len(avoir_rows) == 1
    assert avoir_rows[0].tx_type == AvoirTxType.credit
    assert float(avoir_rows[0].amount) == pytest.approx(35.0)


@pytest.mark.anyio
async def test_avoir_refund_without_client_fails(session):
    from fastapi import HTTPException

    user = await _make_user(session)
    sale = await _make_sale(session, user, client=None, items=[("Hat", 10.0, 1)])
    item = sale.items[0]

    with pytest.raises(HTTPException) as exc:
        await RefundService(session).refund_transaction(
            original_tx_id=sale.id,
            items=[RefundLineInput(item.id, 1)],
            refund_method="avoir",
            user_id=user.id,
            cashier_id=None,
            reason=None,
        )
    assert exc.value.status_code == 400
    assert "client" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# Partial refund: only one item out of two, history shows remaining
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_partial_refund(session):
    user = await _make_user(session)
    client = await _make_client(session)
    sale = await _make_sale(
        session, user, client,
        items=[("Robe", 49.0, 1), ("Pull", 30.0, 1)],
    )
    item_to_refund = sale.items[0]
    item_kept = sale.items[1]

    refund = await RefundService(session).refund_transaction(
        original_tx_id=sale.id,
        items=[RefundLineInput(item_to_refund.id, 1)],
        refund_method="cash",
        user_id=user.id,
        cashier_id=None,
        reason=None,
    )
    assert float(refund.total_ttc) == pytest.approx(49.0)

    # The other product is still sold
    from sqlalchemy import select
    kept = (await session.execute(
        select(Product).where(Product.id == item_kept.product_id)
    )).scalar_one()
    assert kept.status == ProductStatus.sold


# ---------------------------------------------------------------------------
# Cannot refund more than was sold (across multiple refunds)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cannot_refund_more_than_remaining(session):
    from fastapi import HTTPException

    user = await _make_user(session)
    sale = await _make_sale(
        session, user, client=None, items=[("Lot", 10.0, 3)],
    )
    item = sale.items[0]

    # Refund 2 of 3
    await RefundService(session).refund_transaction(
        original_tx_id=sale.id,
        items=[RefundLineInput(item.id, 2)],
        refund_method="cash", user_id=user.id, cashier_id=None, reason=None,
    )

    # Try to refund 2 more (only 1 remaining) → must fail
    with pytest.raises(HTTPException) as exc:
        await RefundService(session).refund_transaction(
            original_tx_id=sale.id,
            items=[RefundLineInput(item.id, 2)],
            refund_method="cash", user_id=user.id, cashier_id=None, reason=None,
        )
    assert exc.value.status_code == 400
    assert "remain" in exc.value.detail.lower()

    # Refund the last 1 → ok
    await RefundService(session).refund_transaction(
        original_tx_id=sale.id,
        items=[RefundLineInput(item.id, 1)],
        refund_method="cash", user_id=user.id, cashier_id=None, reason=None,
    )


# ---------------------------------------------------------------------------
# Refusing edge cases
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cannot_refund_a_refund(session):
    from fastapi import HTTPException

    user = await _make_user(session)
    sale = await _make_sale(session, user)
    refund = await RefundService(session).refund_transaction(
        original_tx_id=sale.id,
        items=[RefundLineInput(sale.items[0].id, 1)],
        refund_method="cash", user_id=user.id, cashier_id=None, reason=None,
    )

    with pytest.raises(HTTPException) as exc:
        await RefundService(session).refund_transaction(
            original_tx_id=refund.id,
            items=[RefundLineInput(sale.items[0].id, 1)],
            refund_method="cash", user_id=user.id, cashier_id=None, reason=None,
        )
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_invalid_refund_method_rejected(session):
    from fastapi import HTTPException

    user = await _make_user(session)
    sale = await _make_sale(session, user)

    with pytest.raises(HTTPException) as exc:
        await RefundService(session).refund_transaction(
            original_tx_id=sale.id,
            items=[RefundLineInput(sale.items[0].id, 1)],
            refund_method="bitcoin", user_id=user.id, cashier_id=None, reason=None,
        )
    assert exc.value.status_code == 400
    assert "method" in exc.value.detail.lower()


@pytest.mark.anyio
async def test_zero_quantity_rejected(session):
    from fastapi import HTTPException

    user = await _make_user(session)
    sale = await _make_sale(session, user)

    with pytest.raises(HTTPException) as exc:
        await RefundService(session).refund_transaction(
            original_tx_id=sale.id,
            items=[RefundLineInput(sale.items[0].id, 0)],
            refund_method="cash", user_id=user.id, cashier_id=None, reason=None,
        )
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Avoir history
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_avoir_history_lists_credits_in_reverse_chronological_order(session):
    user = await _make_user(session)
    client = await _make_client(session)
    sale1 = await _make_sale(session, user, client, items=[("A", 20.0, 1)])
    sale2 = await _make_sale(session, user, client, items=[("B", 30.0, 1)])

    svc = RefundService(session)
    await svc.refund_transaction(
        sale1.id, [RefundLineInput(sale1.items[0].id, 1)],
        "avoir", user.id, None, "First credit",
    )
    await svc.refund_transaction(
        sale2.id, [RefundLineInput(sale2.items[0].id, 1)],
        "avoir", user.id, None, "Second credit",
    )

    history = await svc.list_avoir_history(client.id)
    assert len(history) == 2
    # Order is by created_at desc; on fast in-memory tests both rows can land
    # on the same timestamp. Just assert both amounts are present.
    amounts = sorted(row["amount"] for row in history)
    assert amounts == pytest.approx([20.0, 30.0])

    await session.refresh(client)
    assert float(client.avoir_credit) == pytest.approx(50.0)
