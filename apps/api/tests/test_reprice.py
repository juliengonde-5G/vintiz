"""Tests for the reprice orchestration endpoint (price → note → move + history).

The route coroutine is driven directly against an in-memory aiosqlite session
so the real orchestration runs (``suggest_zone`` + the audit listener) without
needing HTTP auth or the app lifespan. The heavy scoring chain
(``_compute_product_score``) is monkeypatched to a fixed note — it has its own
coverage in ``test_scoring_service`` and pulls in market-price / trend / brand
services we don't want to stand up here. What we assert is the new wiring:
the price + refreshed note are persisted, the move is *proposed* off the
refreshed note, and the price change lands in the movement history (audit).
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.inventory.router import RepriceRequest, reprice_product
from app.core.audit_context import reset_current_user_id, set_current_user_id
from app.models import Base
from app.models.audit import AuditLog
from app.models.product import Category, Gender, Product, ProductPhoto, ProductStatus
from app.models.store import FurnitureItem, StoreZone, ZoneProduct, ZoneTag
from app.models.user import User
from app.services.audit import register_audit_listeners, unregister_audit_listeners


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Category.__table__,
        StoreZone.__table__,
        ZoneTag.__table__,
        ZoneProduct.__table__,
        FurnitureItem.__table__,
        Product.__table__,
        ProductPhoto.__table__,
        AuditLog.__table__,
    ]
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    register_audit_listeners()
    yield eng
    unregister_audit_listeners()
    await eng.dispose()


@pytest.fixture
async def session(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


@pytest.fixture(autouse=True)
def _reset_context():
    handle = set_current_user_id(None)
    yield
    reset_current_user_id(handle)


@pytest.fixture(autouse=True)
def _fixed_note(monkeypatch):
    """Pin the Vintiz note so the move proposal is deterministic.

    Replaces the scoring chain (config/trend/velocity/brand/market-price) with
    a fixed 75/100 — high enough to clear ``ZoneB.min_trend_score`` below.
    """
    async def _fake(db, product):  # noqa: ANN001 - test stub
        return {
            "total_score": 75.0,
            "action": "METTRE EN AVANT — déplacer en vitrine ou zone Tendance",
            "action_color": "yellow",
            "score_price": 16,
            "sortie_forcee": False,
        }

    monkeypatch.setattr(
        "app.api.inventory.router._compute_product_score", _fake
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_user(session) -> User:
    suffix = uuid.uuid4().hex[:6]
    u = User(username=f"u-{suffix}", email=f"{suffix}@x.fr", password_hash="x")
    session.add(u)
    await session.flush()
    return u


async def _make_zone(session, *, name, genders, min_score=None, priority=100) -> StoreZone:
    z = StoreZone(
        name=name,
        capacity=30,
        match_genders=genders,
        min_trend_score=min_score,
        assignment_priority=priority,
        auto_assign=True,
        display_order=priority,
    )
    session.add(z)
    await session.flush()
    return z


async def _make_product(session, *, zone_id, sale_price=50.0) -> Product:
    cat = Category(name="Robes", gender=Gender.femme)
    session.add(cat)
    await session.flush()
    now = datetime.now(timezone.utc)
    p = Product(
        barcode=f"B-{uuid.uuid4().hex[:8]}",
        name="Robe",
        category_id=cat.id,
        status=ProductStatus.displayed,
        sale_price=sale_price,
        purchase_price=8,
        zone_id=zone_id,
        created_at=now,
        updated_at=now,
    )
    session.add(p)
    await session.flush()
    return p


# ---------------------------------------------------------------------------
# Price + note persistence
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_reprice_persists_price_and_refreshed_note(session):
    user = await _make_user(session)
    set_current_user_id(user.id)
    zone_b = await _make_zone(session, name="Zone B", genders=["femme"], min_score=60.0)
    product = await _make_product(session, zone_id=zone_b.id, sale_price=50.0)

    resp = await reprice_product(
        product_id=product.id,
        request=RepriceRequest(new_price=29.5),
        db=session,
        current_user=user,
    )

    assert resp["old_price"] == 50.0
    assert resp["new_price"] == 29.5
    assert resp["price_changed"] is True
    assert resp["score"]["total_score"] == 75.0
    # The refreshed note is persisted on the product (catalogue + suggest_zone).
    assert float(product.sale_price) == 29.5
    assert float(product.trend_score) == 75.0
    assert resp["product"]["sale_price"] == 29.5


@pytest.mark.anyio
async def test_reprice_rejects_negative_price(session):
    user = await _make_user(session)
    zone_b = await _make_zone(session, name="Zone B", genders=["femme"], min_score=60.0)
    product = await _make_product(session, zone_id=zone_b.id)

    with pytest.raises(HTTPException) as exc:
        await reprice_product(
            product_id=product.id,
            request=RepriceRequest(new_price=-1),
            db=session,
            current_user=user,
        )
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Move proposal driven by the refreshed note
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_reprice_proposes_move_when_zone_differs(session):
    user = await _make_user(session)
    set_current_user_id(user.id)
    # Current zone only takes "homme" → the femme product doesn't belong here.
    zone_a = await _make_zone(session, name="Zone A", genders=["homme"], priority=10)
    # Target zone matches femme + needs note ≥ 60 (our fixed note is 75).
    zone_b = await _make_zone(session, name="Zone B", genders=["femme"], min_score=60.0, priority=20)
    product = await _make_product(session, zone_id=zone_a.id)

    resp = await reprice_product(
        product_id=product.id,
        request=RepriceRequest(new_price=29.5),
        db=session,
        current_user=user,
    )

    move = resp["move"]
    assert move["recommended"] is True
    assert move["current_zone_id"] == str(zone_a.id)
    assert move["current_zone_name"] == "Zone A"
    assert move["suggested_zone_id"] == str(zone_b.id)
    assert move["suggested_zone_name"] == "Zone B"
    # Reprice only *proposes* — it must not have moved the product itself.
    assert str(product.zone_id) == str(zone_a.id)


@pytest.mark.anyio
async def test_reprice_no_move_when_already_in_suggested_zone(session):
    user = await _make_user(session)
    set_current_user_id(user.id)
    await _make_zone(session, name="Zone A", genders=["homme"], priority=10)
    zone_b = await _make_zone(session, name="Zone B", genders=["femme"], min_score=60.0, priority=20)
    product = await _make_product(session, zone_id=zone_b.id)

    resp = await reprice_product(
        product_id=product.id,
        request=RepriceRequest(new_price=29.5),
        db=session,
        current_user=user,
    )

    assert resp["move"]["recommended"] is False
    assert resp["move"]["suggested_zone_id"] == str(zone_b.id)


# ---------------------------------------------------------------------------
# Movement history (audit)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_reprice_logs_price_change_to_history(session):
    user = await _make_user(session)
    set_current_user_id(user.id)
    zone_b = await _make_zone(session, name="Zone B", genders=["femme"], min_score=60.0)
    product = await _make_product(session, zone_id=zone_b.id, sale_price=50.0)

    # Drop the create-audit rows from setup so we isolate the reprice entry.
    await session.execute(delete(AuditLog))
    await session.flush()

    await reprice_product(
        product_id=product.id,
        request=RepriceRequest(new_price=29.5),
        db=session,
        current_user=user,
    )

    rows = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.entity == "product", AuditLog.action == "update"
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    diff = rows[0].data
    assert "sale_price" in diff
    assert diff["sale_price"]["before"] == 50.0
    assert diff["sale_price"]["after"] == 29.5
    assert rows[0].user_id == user.id
    # The note is refreshed but is not a tracked field → no extra noise.
    assert "trend_score" not in diff


@pytest.mark.anyio
async def test_reprice_same_price_makes_no_history_entry(session):
    user = await _make_user(session)
    set_current_user_id(user.id)
    zone_b = await _make_zone(session, name="Zone B", genders=["femme"], min_score=60.0)
    product = await _make_product(session, zone_id=zone_b.id, sale_price=29.5)

    await session.execute(delete(AuditLog))
    await session.flush()

    resp = await reprice_product(
        product_id=product.id,
        request=RepriceRequest(new_price=29.5),
        db=session,
        current_user=user,
    )

    assert resp["price_changed"] is False
    rows = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.entity == "product", AuditLog.action == "update"
            )
        )
    ).scalars().all()
    assert rows == []
    # Note is still refreshed even when the price is unchanged.
    assert float(product.trend_score) == 75.0
