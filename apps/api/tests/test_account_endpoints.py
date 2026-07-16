"""Tests for the espace client public endpoints (PR3).

Covers /account/coupons, /account/transactions, /account/consents (GET + POST).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.security import create_access_token
from app.models.client import Client, Consent, ConsentPurpose
from app.models.coupon import Coupon, CouponDiscountType, CouponSource
from app.models.embeddings import CustomerTasteProfile
from app.models.events import EventLog, EventSource, EventType
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
@pytest.mark.parametrize(
    ("path", "toggle_payload"),
    [
        (
            "/api/crm/account/personal-shopper/toggle",
            {"enabled": False, "source": "site_account_settings"},
        ),
        (
            "/api/crm/account/consents/profiling",
            {"granted": False},
        ),
    ],
)
async def test_personal_shopper_revoke_erases_taste_profile(
    _create_tables,
    client,
    path,
    toggle_payload,
):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.database import engine

    async with AsyncSession(engine) as session:
        c = Client(
            first_name="Diane",
            last_name="Profil",
            email="diane.profil@x.fr",
            gender_profile="femme",
            age_band="35-44",
            season_bias="winter",
            price_ceiling_cents=12000,
            price_sensitivity=0.7,
            trend_affinity=0.8,
        )
        session.add(c)
        await session.flush()
        headers = _client_headers(c.id)
        session.add(
            CustomerTasteProfile(
                customer_id=c.id,
                n_purchases_analyzed=3,
                algo_version="test-profile",
            )
        )
        session.add(
            Consent(
                client_id=c.id,
                purpose=ConsentPurpose.profiling,
                granted=True,
                policy_version="v2",
                source="site_onboarding",
            )
        )
        event = EventLog(
            occurred_at=datetime.now(timezone.utc),
            event_type=EventType.customer_recommendation_clicked,
            source=EventSource.site,
            customer_id=c.id,
        )
        session.add(event)
        await session.flush()
        client_id = c.id
        event_id = event.id
        await session.commit()

    res = await client.post(
        path,
        json={"email": "diane.profil@x.fr", **toggle_payload},
        headers=headers,
    )
    assert res.status_code == 204

    async with AsyncSession(engine) as session:
        stored_client = await session.get(Client, client_id)
        assert stored_client is not None
        assert stored_client.gender_profile is None
        assert stored_client.age_band is None
        assert stored_client.season_bias is None
        assert stored_client.price_ceiling_cents is None
        assert stored_client.price_sensitivity is None
        assert stored_client.trend_affinity is None

        profile = await session.scalar(
            select(CustomerTasteProfile).where(
                CustomerTasteProfile.customer_id == client_id
            )
        )
        assert profile is None

        anonymized_event = await session.get(EventLog, event_id)
        assert anonymized_event is not None
        assert anonymized_event.customer_id is None

        consent_rows = await session.scalars(
            select(Consent)
            .where(
                Consent.client_id == client_id,
                Consent.purpose == ConsentPurpose.profiling,
            )
        )
        revoked = [row for row in consent_rows if not row.granted]
        assert len(revoked) == 1
        assert revoked[0].source in {
            "site_account_settings",
            "account_self_service",
        }


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
