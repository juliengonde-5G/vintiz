"""Tests for trend_alerts service (PR2)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    Client, Consent, ConsentPurpose, LoyaltyAccount,
)
from app.models.embeddings import (
    EMBEDDING_DIM, CustomerTasteProfile, ProductEmbedding,
)
from app.models.product import Category, Product, ProductStatus
from app.services import trend_alerts as ta


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


def _now():
    return datetime.now(timezone.utc)


def _vec(value: float) -> list[float]:
    return [value] * EMBEDDING_DIM


async def _seed_client(session, *, email: str, with_profiling: bool, with_trend: bool, last_alert: datetime | None = None):
    client = Client(first_name="A", last_name="B", email=email)
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(
        client_id=client.id, points=10, membership_number=f"V{abs(hash(email)) % 1_000_000:06d}",
    ))
    client.loyalty_subscribed_at = _now()
    client.loyalty_expires_at = _now() + timedelta(days=730)
    if last_alert:
        client.last_trend_alert_at = last_alert
    await session.flush()
    if with_profiling:
        session.add(Consent(
            client_id=client.id, purpose=ConsentPurpose.profiling,
            granted=True, policy_version="v2", source="test",
        ))
    if with_trend:
        session.add(Consent(
            client_id=client.id, purpose=ConsentPurpose.trend_alerts,
            granted=True, policy_version="v2", source="test",
        ))
    if with_profiling:
        # Taste profile aligned to v=1.0 vectors so any v=1.0 product
        # produces cosine = 1.
        session.add(CustomerTasteProfile(
            customer_id=client.id,
            visual_centroid=_vec(1.0),
            text_centroid=_vec(1.0),
            algo_version="v1",
        ))
    await session.flush()
    return client


async def _seed_trending_product(session, *, score: float, created_at: datetime | None = None):
    cat = Category(name="robe")
    session.add(cat)
    await session.flush()
    product = Product(
        barcode=f"V{abs(hash(score)) % 1_000_000:06d}",
        name="Robe trend",
        category_id=cat.id,
        sale_price=49.0,
        condition="A",
        status=ProductStatus.display,
        trend_score=score,
    )
    session.add(product)
    await session.flush()
    if created_at:
        product.created_at = created_at
    session.add(ProductEmbedding(
        product_id=product.id,
        visual_embedding=_vec(1.0),
        text_embedding=_vec(1.0),
        algo_version="v1",
    ))
    await session.flush()
    return product


@pytest.mark.anyio
async def test_no_trending_products_returns_zero(session):
    summary = await ta.run_trend_alerts(session)
    assert summary["sent"] == 0


@pytest.mark.anyio
async def test_sends_to_eligible_member(session, monkeypatch):
    # Stub the email gateway so we don't try to actually send.
    sent: list = []

    def fake_send(message):
        sent.append(message)
        from app.services.email_gateway import EmailResult
        return EmailResult(status="simulated", backend="simulation", sent_at="now")

    monkeypatch.setattr("app.services.trend_alerts.send_email", fake_send)

    await _seed_client(session, email="alice@x.fr", with_profiling=True, with_trend=True)
    await _seed_trending_product(session, score=85)

    summary = await ta.run_trend_alerts(session)
    assert summary["sent"] == 1
    assert summary["matched"] == 1
    assert sent[0].to == "alice@x.fr"


@pytest.mark.anyio
async def test_frequency_cap_skips_recent_recipient(session, monkeypatch):
    monkeypatch.setattr(
        "app.services.trend_alerts.send_email",
        lambda m: __import__("app.services.email_gateway", fromlist=["EmailResult"]).EmailResult(
            status="simulated", backend="simulation", sent_at="now",
        ),
    )

    recent = _now() - timedelta(days=2)
    await _seed_client(
        session, email="bob@x.fr", with_profiling=True,
        with_trend=True, last_alert=recent,
    )
    await _seed_trending_product(session, score=85)

    summary = await ta.run_trend_alerts(session)
    assert summary["sent"] == 0
    assert summary["audience"] == 0


@pytest.mark.anyio
async def test_missing_trend_consent_skipped(session, monkeypatch):
    monkeypatch.setattr(
        "app.services.trend_alerts.send_email",
        lambda m: __import__("app.services.email_gateway", fromlist=["EmailResult"]).EmailResult(
            status="simulated", backend="simulation", sent_at="now",
        ),
    )

    await _seed_client(
        session, email="charlie@x.fr",
        with_profiling=True, with_trend=False,
    )
    await _seed_trending_product(session, score=85)

    summary = await ta.run_trend_alerts(session)
    assert summary["sent"] == 0
