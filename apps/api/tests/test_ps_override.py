"""Tests for the Personal Shopper human-override endpoint (audit C10).

Covers :
- Route is registered (deploy smoke)
- Auth gate (401 without bearer)
- note validation (≥ 10 chars)
- decision validation (whitelist)
- happy path writes an AuditLog with action="ps_human_override" and the
  expected structured payload (decision, note, customer hash, etc.)
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.crm.router import (
    PersonalShopperOverrideRequest,
    personal_shopper_override,
)
from app.models import Base
from app.models.audit import AuditLog
from app.models.client import (
    AvoirTransaction,
    Client,
    Consent,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.user import User, UserRole


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Client.__table__,
        Consent.__table__,
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        AvoirTransaction.__table__,
        AuditLog.__table__,
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


async def _seed_manager(session) -> User:
    user = User(
        username="manager",
        email="m@v.fr",
        password_hash="x" * 60,
        role=UserRole.manager,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


# ---------------------------------------------------------------------------
# Route registration & auth
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_route_registered():
    from app.main import app

    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/crm/personal-shopper/override" in paths


@pytest.mark.anyio
async def test_auth_gate(client):
    res = await client.post(
        "/api/crm/personal-shopper/override",
        json={
            "recommendation_set_id": str(uuid.uuid4()),
            "decision": "revised",
            "note": "Cliente a indiqué qu'elle ne porte plus de rouge.",
        },
    )
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Validation business
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_note_too_short_rejected(session):
    user = await _seed_manager(session)
    req = PersonalShopperOverrideRequest(
        recommendation_set_id=uuid.uuid4(),
        decision="revised",
        note="court",  # 5 chars < 10
    )
    with pytest.raises(HTTPException) as exc:
        await personal_shopper_override(req, db=session, current_user=user)
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "override_note_too_short"


@pytest.mark.anyio
async def test_invalid_decision_rejected(session):
    user = await _seed_manager(session)
    req = PersonalShopperOverrideRequest(
        recommendation_set_id=uuid.uuid4(),
        decision="approved",  # not in whitelist
        note="Note suffisamment longue pour passer la validation.",
    )
    with pytest.raises(HTTPException) as exc:
        await personal_shopper_override(req, db=session, current_user=user)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_happy_path_writes_audit_log(session):
    """Override valide → AuditLog persisté + payload structuré."""
    user = await _seed_manager(session)
    rec_id = uuid.uuid4()
    req = PersonalShopperOverrideRequest(
        recommendation_set_id=rec_id,
        decision="revised",
        note="Cliente a contesté, on remplace par un blazer écru à la place.",
        customer_email="anais@example.com",
        replacement_product_ids=[uuid.uuid4(), uuid.uuid4()],
    )
    out = await personal_shopper_override(req, db=session, current_user=user)

    assert out["decision"] == "revised"
    assert out["logged"] is True
    assert out["intervention_window_days"] == 30
    assert out["recommendation_set_id"] == str(rec_id)

    rows = (await session.execute(
        select(AuditLog).where(AuditLog.action == "ps_human_override")
    )).scalars().all()
    assert len(rows) == 1
    log = rows[0]
    assert log.entity == "personal_shopper_recommendation"
    assert log.entity_id == rec_id
    assert log.user_id == user.id

    payload = log.data or {}
    assert payload["decision"] == "revised"
    assert payload["note"].startswith("Cliente a contesté")
    # Hash SHA-256 tronqué à 12 chars + préfixe sha256:
    h = payload["customer_email_hash"]
    assert h is not None and h.startswith("sha256:") and len(h) == len("sha256:") + 12
    assert len(payload["replacement_product_ids"]) == 2
    assert payload["policy_version"] == "v1.0-2026-04"


@pytest.mark.anyio
async def test_decision_removed_accepted(session):
    """`removed` est dans la whitelist."""
    user = await _seed_manager(session)
    req = PersonalShopperOverrideRequest(
        recommendation_set_id=uuid.uuid4(),
        decision="removed",
        note="Recommandation retirée — produit déjà vendu en boutique.",
    )
    out = await personal_shopper_override(req, db=session, current_user=user)
    assert out["decision"] == "removed"


@pytest.mark.anyio
async def test_decision_confirmed_after_review_accepted(session):
    """`confirmed_after_review` est dans la whitelist."""
    user = await _seed_manager(session)
    req = PersonalShopperOverrideRequest(
        recommendation_set_id=uuid.uuid4(),
        decision="confirmed_after_review",
        note="Reco maintenue après revue manager — pertinente.",
    )
    out = await personal_shopper_override(req, db=session, current_user=user)
    assert out["decision"] == "confirmed_after_review"


@pytest.mark.anyio
async def test_resolves_customer_id_from_email(session):
    """Si email fourni et matche une cliente → customer_id résolu et hashé."""
    user = await _seed_manager(session)
    c = Client(first_name="Léa", last_name="X", email="lea@example.com")
    session.add(c)
    await session.flush()

    req = PersonalShopperOverrideRequest(
        recommendation_set_id=uuid.uuid4(),
        decision="revised",
        note="Override test — vérification résolution email→client_id.",
        customer_email="LEA@example.com",  # uppercase pour tester _normalize
    )
    await personal_shopper_override(req, db=session, current_user=user)

    rows = (await session.execute(
        select(AuditLog).where(AuditLog.action == "ps_human_override")
    )).scalars().all()
    assert len(rows) == 1
    payload = rows[0].data or {}
    assert payload["customer_id"] == str(c.id)
