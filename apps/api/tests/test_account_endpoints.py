"""Tests for the espace client public endpoints (PR3).

Covers /account/coupons, /account/transactions, /account/consents (GET + POST).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.security import create_access_token
from app.models.client import Client, Consent, ConsentPurpose
from app.models.coupon import Coupon, CouponDiscountType, CouponSource
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Product, ProductStatus


def _client_headers(client_id: object) -> dict[str, str]:
    token = create_access_token({"sub": str(client_id), "role": "client"})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_account_coupons_lists_active(_create_tables, client):
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.database import engine

    async with AsyncSession(engine) as session:
        c = Client(first_name="Alice", last_name="M", email="alice@x.fr")
        session.add(c)
        await session.flush()
        headers = _client_headers(c.id)
        now = datetime.now(timezone.utc)
        session.add(Coupon(
            code="ANNIV-AAAAA",
            client_id=c.id,
            discount_type=CouponDiscountType.amount,
            discount_value=Decimal("10"),
            source=CouponSource.anniversary,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=10),
            is_active=True,
        ))
        # Inactive coupon should be filtered out.
        session.add(Coupon(
            code="OFF-OFF",
            client_id=c.id,
            discount_type=CouponDiscountType.percent,
            discount_value=Decimal("5"),
            source=CouponSource.manual,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=10),
            is_active=False,
        ))
        await session.commit()

    res = await client.get(
        "/api/crm/account/coupons?email=alice@x.fr",
        headers=headers,
    )
    assert res.status_code == 200
    rows = res.json()
    codes = [r["code"] for r in rows]
    assert "ANNIV-AAAAA" in codes
    assert "OFF-OFF" not in codes


@pytest.mark.anyio
async def test_account_transactions_lists_recent(_create_tables, client):
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.database import engine
    from app.models.user import User, UserRole

    async with AsyncSession(engine) as session:
        user = User(
            username="cashier", email="cashier@x.fr",
            password_hash="x" * 60, role=UserRole.manager, is_active=True,
        )
        session.add(user)
        await session.flush()
        c = Client(first_name="Bob", last_name="S", email="bob@x.fr")
        session.add(c)
        await session.flush()
        headers = _client_headers(c.id)
        cat = Category(name="t-shirt")
        session.add(cat)
        await session.flush()
        product = Product(
            barcode="V40001", name="T-shirt blanc", category_id=cat.id,
            sale_price=25, condition="A", status=ProductStatus.sold,
        )
        session.add(product)
        await session.flush()
        tx = Transaction(
            transaction_number=42,
            transaction_type=TransactionType.sale,
            user_id=user.id,
            client_id=c.id,
            total_ht=20.83,
            total_tva=4.17,
            total_ttc=25.0,
            hash_chain="0" * 64,
        )
        session.add(tx)
        await session.flush()
        session.add(TransactionItem(
            transaction_id=tx.id,
            product_id=product.id,
            quantity=1,
            unit_price=25,
            discount_percent=0,
            line_total=25,
        ))
        await session.commit()

    res = await client.get(
        "/api/crm/account/transactions?email=bob@x.fr",
        headers=headers,
    )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["transaction_number"] == 42
    assert rows[0]["items"][0]["name"] == "T-shirt blanc"


@pytest.mark.anyio
async def test_account_consents_returns_all_purposes(_create_tables, client):
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.database import engine

    async with AsyncSession(engine) as session:
        c = Client(first_name="Charlie", last_name="T", email="charlie@x.fr")
        session.add(c)
        await session.flush()
        headers = _client_headers(c.id)
        session.add(Consent(
            client_id=c.id,
            purpose=ConsentPurpose.email_marketing,
            granted=True,
            policy_version="v2",
            source="site_signup",
        ))
        await session.commit()

    res = await client.get(
        "/api/crm/account/consents?email=charlie@x.fr",
        headers=headers,
    )
    assert res.status_code == 200
    rows = res.json()
    purposes = {r["purpose"]: r for r in rows}
    # Every purpose surfaces (granted false if no row).
    assert purposes["email_marketing"]["granted"] is True
    assert purposes["profiling"]["granted"] is False
    assert "trend_alerts" in purposes
    assert purposes["trend_alerts"]["granted"] is False


@pytest.mark.anyio
async def test_account_consent_toggle_appends_row(_create_tables, client):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.database import engine

    async with AsyncSession(engine) as session:
        c = Client(first_name="Diana", last_name="T", email="diana@x.fr")
        session.add(c)
        await session.flush()
        headers = _client_headers(c.id)
        await session.commit()

    res = await client.post(
        "/api/crm/account/consents/trend_alerts",
        json={"email": "diana@x.fr", "granted": True},
        headers=headers,
    )
    assert res.status_code == 204

    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(Consent).where(Consent.purpose == ConsentPurpose.trend_alerts)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].granted is True
        assert rows[0].source == "account_self_service"


@pytest.mark.anyio
async def test_account_consent_unknown_purpose_404(_create_tables, client):
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.database import engine

    async with AsyncSession(engine) as session:
        c = Client(first_name="Ed", last_name="W", email="ed@x.fr")
        session.add(c)
        await session.flush()
        headers = _client_headers(c.id)
        await session.commit()

    res = await client.post(
        "/api/crm/account/consents/something_made_up",
        json={"email": "ed@x.fr", "granted": True},
        headers=headers,
    )
    assert res.status_code == 404


@pytest.mark.anyio
async def test_account_coupons_rejects_another_email(_create_tables, client):
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.database import engine

    async with AsyncSession(engine) as session:
        c = Client(first_name="Auth", last_name="Client", email="auth@x.fr")
        session.add(c)
        await session.flush()
        headers = _client_headers(c.id)
        await session.commit()

    res = await client.get(
        "/api/crm/account/coupons?email=ghost@x.fr",
        headers=headers,
    )
    assert res.status_code == 403
