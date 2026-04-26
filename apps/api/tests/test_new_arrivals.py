"""Tests for the weekly new-arrivals digest (P4-009)."""

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
from app.models.product import Category, Gender, Product, ProductPhoto, ProductStatus
from app.models.user import User
from app.services.new_arrivals import (
    LOOKBACK_DAYS,
    _generic_new_arrivals,
    run_new_arrivals_pass,
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
def _force_simulation(monkeypatch):
    for key in ("BREVO_API_KEY", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)


async def _category(session) -> Category:
    c = Category(name="Robes", gender=Gender.femme)
    session.add(c)
    await session.flush()
    return c


async def _product(
    session,
    category: Category,
    *,
    name: str,
    displayed_at: datetime | None,
) -> Product:
    p = Product(
        barcode=f"B-{uuid.uuid4().hex[:8]}",
        name=name,
        category_id=category.id,
        status=ProductStatus.displayed if displayed_at else ProductStatus.stock,
        sale_price=20,
        purchase_price=5,
        displayed_at=displayed_at,
    )
    session.add(p)
    await session.flush()
    return p


@pytest.mark.anyio
async def test_generic_new_arrivals_returns_recently_displayed(session):
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    cat = await _category(session)
    p_recent = await _product(session, cat, name="Recent", displayed_at=now - timedelta(days=2))
    p_old = await _product(session, cat, name="Old", displayed_at=now - timedelta(days=30))
    p_stock = await _product(session, cat, name="Stock", displayed_at=None)

    since = now - timedelta(days=LOOKBACK_DAYS)
    products = await _generic_new_arrivals(session, since=since)
    assert [p.id for p in products] == [p_recent.id]


@pytest.mark.anyio
async def test_run_pass_skips_when_no_recent_products(session):
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    summary = await run_new_arrivals_pass(session, now=now)
    assert summary["recipients"] == 0
    assert summary.get("skipped_no_products") is True


@pytest.mark.anyio
async def test_run_pass_sends_to_optin_clients(session):
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    cat = await _category(session)
    await _product(session, cat, name="A", displayed_at=now - timedelta(days=1))
    await _product(session, cat, name="B", displayed_at=now - timedelta(days=2))

    optin = Client(
        first_name="Alice", last_name="Optin", email="alice@x.fr",
        email_optin=True,
    )
    optout = Client(
        first_name="Bob", last_name="Out", email="bob@x.fr",
        email_optin=False,
    )
    session.add_all([optin, optout])
    await session.flush()

    summary = await run_new_arrivals_pass(session, now=now)
    assert summary["recipients"] == 1
    assert summary["sent"] == 1
    assert summary["failed"] == 0
