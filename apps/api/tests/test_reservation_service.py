"""Tests for reservation lifecycle (P4-005)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    AvoirTransaction,
    Client,
    Consent,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.pos import Transaction
from app.models.product import Category, Gender, Product, ProductPhoto, ProductStatus
from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User
from app.services.reservation import (
    ReservationError,
    cancel_reservation,
    create_reservation,
    expire_due,
    list_active_reservation_product_ids,
    list_reservations,
    redeem_reservation,
)


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
        Reservation.__table__,
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
def _no_email(monkeypatch):
    for k in ("BREVO_API_KEY", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)


async def _client(session, email: str = "alice@x.fr") -> Client:
    c = Client(first_name="Alice", last_name="X", email=email)
    session.add(c)
    await session.flush()
    return c


async def _category(session) -> Category:
    c = Category(name="Robes", gender=Gender.femme)
    session.add(c)
    await session.flush()
    return c


async def _product(session, category, *, status=ProductStatus.displayed) -> Product:
    p = Product(
        barcode=f"B-{uuid.uuid4().hex[:8]}",
        name="Robe rouge",
        category_id=category.id,
        status=status,
        sale_price=49,
        purchase_price=8,
    )
    session.add(p)
    await session.flush()
    return p


# ---------------------------------------------------------------------------
# create_reservation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_reservation_happy_path(session):
    cat = await _category(session)
    client = await _client(session)
    product = await _product(session, cat)

    reservation = await create_reservation(
        session, client_id=client.id, product_id=product.id,
    )
    assert reservation.status == ReservationStatus.active
    delta = reservation.expires_at - datetime.now(timezone.utc).replace(tzinfo=reservation.expires_at.tzinfo)
    assert 47.5 < delta.total_seconds() / 3600 < 48.5


@pytest.mark.anyio
async def test_create_rejects_unknown_client(session):
    cat = await _category(session)
    product = await _product(session, cat)
    with pytest.raises(ReservationError, match="client_not_found"):
        await create_reservation(
            session, client_id=uuid.uuid4(), product_id=product.id,
        )


@pytest.mark.anyio
async def test_create_rejects_off_floor_product(session):
    cat = await _category(session)
    client = await _client(session)
    sold = await _product(session, cat, status=ProductStatus.sold)
    with pytest.raises(ReservationError, match="product_not_on_floor"):
        await create_reservation(
            session, client_id=client.id, product_id=sold.id,
        )


@pytest.mark.anyio
async def test_create_rejects_double_active_hold(session):
    cat = await _category(session)
    a = await _client(session, "a@x.fr")
    b = await _client(session, "b@x.fr")
    product = await _product(session, cat)
    await create_reservation(session, client_id=a.id, product_id=product.id)
    with pytest.raises(ReservationError, match="product_already_reserved"):
        await create_reservation(
            session, client_id=b.id, product_id=product.id,
        )


# ---------------------------------------------------------------------------
# cancel + expire + redeem
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cancel_flips_status(session):
    cat = await _category(session)
    client = await _client(session)
    product = await _product(session, cat)
    r = await create_reservation(session, client_id=client.id, product_id=product.id)

    await cancel_reservation(session, r.id, reason="changed mind")
    assert r.status == ReservationStatus.cancelled
    assert "cancel:" in (r.notes or "")


@pytest.mark.anyio
async def test_cancel_rejects_terminal_states(session):
    cat = await _category(session)
    client = await _client(session)
    product = await _product(session, cat)
    r = await create_reservation(session, client_id=client.id, product_id=product.id)
    await cancel_reservation(session, r.id)
    with pytest.raises(ReservationError, match="reservation_not_active"):
        await cancel_reservation(session, r.id)


@pytest.mark.anyio
async def test_expire_due_only_touches_past_active(session):
    cat = await _category(session)
    a = await _client(session, "a@x.fr")
    b = await _client(session, "b@x.fr")
    p1 = await _product(session, cat)
    p2 = await _product(session, cat)
    now = datetime.now(timezone.utc)

    r1 = await create_reservation(
        session, client_id=a.id, product_id=p1.id, hold_hours=1,
        now=now - timedelta(hours=2),  # expired 1h ago
    )
    r2 = await create_reservation(
        session, client_id=b.id, product_id=p2.id, hold_hours=48,
        now=now,
    )
    assert r1.status == ReservationStatus.active
    assert r2.status == ReservationStatus.active

    n = await expire_due(session, now=now)
    assert n == 1
    assert r1.status == ReservationStatus.expired
    assert r2.status == ReservationStatus.active


@pytest.mark.anyio
async def test_redeem_links_transaction(session):
    cat = await _category(session)
    client = await _client(session)
    product = await _product(session, cat)
    r = await create_reservation(session, client_id=client.id, product_id=product.id)

    fake_tx_id = uuid.uuid4()
    await redeem_reservation(session, r.id, fake_tx_id)
    assert r.status == ReservationStatus.redeemed
    assert r.redeemed_transaction_id == fake_tx_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_active_product_ids_helper(session):
    cat = await _category(session)
    client = await _client(session)
    p_held = await _product(session, cat)
    p_free = await _product(session, cat)

    await create_reservation(session, client_id=client.id, product_id=p_held.id)
    ids = await list_active_reservation_product_ids(session)
    assert p_held.id in ids
    assert p_free.id not in ids


@pytest.mark.anyio
async def test_list_reservations_filters_by_status(session):
    cat = await _category(session)
    client = await _client(session)
    p1 = await _product(session, cat)
    p2 = await _product(session, cat)

    r1 = await create_reservation(session, client_id=client.id, product_id=p1.id)
    r2 = await create_reservation(session, client_id=client.id, product_id=p2.id)
    await cancel_reservation(session, r1.id)

    rows = await list_reservations(session, statuses=[ReservationStatus.active])
    assert len(rows) == 1
    assert rows[0].id == r2.id
