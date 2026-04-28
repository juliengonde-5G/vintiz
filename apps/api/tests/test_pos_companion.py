"""Tests for the POS Companion service (PR4)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    Client, LoyaltyAccount, LoyaltyTransaction, LoyaltyTxType,
)
from app.models.coupon import Coupon, CouponDiscountType, CouponSource
from app.models.product import Category, Product, ProductStatus
from app.services.pos_companion import (
    CATEGORY_COMPLEMENTS,
    _normalize_category,
    _points_to_credit,
    _redemption_cap_cents,
    companion_payload,
)


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


@pytest.mark.anyio
async def test_normalize_category_handles_synonyms():
    assert _normalize_category("Tshirt") == "t-shirt"
    assert _normalize_category("ROBE") == "robe"
    assert _normalize_category(None) is None


@pytest.mark.anyio
async def test_points_to_credit_floor_division():
    assert _points_to_credit(0) == 0
    assert _points_to_credit(99) == 0
    assert _points_to_credit(100) == 1
    assert _points_to_credit(8400) == 84


@pytest.mark.anyio
async def test_redemption_cap_max_50_percent():
    # 100 pts = 10€ available, but cart is 8€ → cap at 50% of 800 cents.
    assert _redemption_cap_cents(800, 100) == 400
    # 5 pts = 0.50€, cart 100€ → not capped by 50%.
    assert _redemption_cap_cents(10000, 5) == 50
    # 0 pts → 0.
    assert _redemption_cap_cents(5000, 0) == 0


@pytest.mark.anyio
async def test_companion_returns_loyalty_block_for_member(session):
    client = Client(first_name="Alice", last_name="M", email="alice@x.fr")
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(
        client_id=client.id, points=120, membership_number="V100100"
    ))
    client.loyalty_subscribed_at = datetime.now(timezone.utc)
    client.loyalty_expires_at = datetime.now(timezone.utc) + timedelta(days=730)
    await session.flush()

    payload = await companion_payload(
        session,
        client_id=client.id,
        cart_total_cents=4200,
        cart_product_ids=[],
    )
    assert payload["client"]["membership_number"] == "V100100"
    assert payload["loyalty"]["active"] is True
    assert payload["loyalty"]["points_current"] == 120
    assert payload["loyalty"]["would_earn"] == 42
    # 1200 cents available, cart half = 2100 → cap at 1200.
    assert payload["loyalty"]["can_redeem_max_cents"] == 1200


@pytest.mark.anyio
async def test_companion_for_non_member_has_zero_redeem(session):
    client = Client(first_name="Bob", last_name="S", email="bob@x.fr")
    session.add(client)
    await session.commit()

    payload = await companion_payload(
        session,
        client_id=client.id,
        cart_total_cents=3000,
        cart_product_ids=[],
    )
    assert payload["loyalty"]["active"] is False
    assert payload["loyalty"]["would_earn"] == 30
    assert payload["loyalty"]["can_redeem_max_cents"] == 0


@pytest.mark.anyio
async def test_companion_returns_complementary_suggestions(session):
    cat_robe = Category(name="robe")
    cat_chaussures = Category(name="chaussures")
    cat_accessoire = Category(name="accessoire")
    session.add_all([cat_robe, cat_chaussures, cat_accessoire])
    await session.flush()

    cart_product = Product(
        barcode="V90001", name="Robe noire fluide", category_id=cat_robe.id,
        sale_price=49, condition="A", status=ProductStatus.stock,
    )
    suggestion_a = Product(
        barcode="V90002", name="Bottines tendance", category_id=cat_chaussures.id,
        sale_price=80, condition="A", status=ProductStatus.display,
        trend_score=85,
    )
    suggestion_b = Product(
        barcode="V90003", name="Foulard imprimé", category_id=cat_accessoire.id,
        sale_price=20, condition="A", status=ProductStatus.stock,
        trend_score=70,
    )
    session.add_all([cart_product, suggestion_a, suggestion_b])
    await session.flush()

    client = Client(first_name="C", last_name="T", email="c@x.fr")
    session.add(client)
    await session.commit()

    payload = await companion_payload(
        session,
        client_id=client.id,
        cart_total_cents=4900,
        cart_product_ids=[cart_product.id],
    )
    suggested_ids = {s["product_id"] for s in payload["suggestions"]}
    assert str(suggestion_a.id) in suggested_ids
    assert str(suggestion_b.id) in suggested_ids
    # Cart product never appears as a suggestion.
    assert str(cart_product.id) not in suggested_ids


@pytest.mark.anyio
async def test_companion_alerts_at_risk_segment(session):
    client = Client(
        first_name="Z", last_name="Y", email="z@x.fr",
        rfm_segment="at_risk",
    )
    session.add(client)
    await session.commit()

    payload = await companion_payload(
        session,
        client_id=client.id,
        cart_total_cents=0,
        cart_product_ids=[],
    )
    types = {a["type"] for a in payload["alerts"]}
    assert "rfm_at_risk" in types


@pytest.mark.anyio
async def test_companion_alerts_loyalty_milestone_close(session):
    client = Client(first_name="M", last_name="C", email="m@x.fr")
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(
        client_id=client.id, points=92, membership_number="V200001",
    ))
    client.loyalty_subscribed_at = datetime.now(timezone.utc)
    client.loyalty_expires_at = datetime.now(timezone.utc) + timedelta(days=730)
    await session.commit()

    payload = await companion_payload(
        session, client_id=client.id, cart_total_cents=0, cart_product_ids=[],
    )
    types = {a["type"] for a in payload["alerts"]}
    assert "loyalty_milestone_close" in types


@pytest.mark.anyio
async def test_companion_404_on_unknown_client(session):
    import uuid as _uuid

    with pytest.raises(LookupError):
        await companion_payload(
            session, client_id=_uuid.uuid4(),
            cart_total_cents=0, cart_product_ids=[],
        )
