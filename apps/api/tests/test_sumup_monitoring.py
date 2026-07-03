"""Tests monitoring paiement SumUp (P3).

Couvre :
- les nouveaux champs de triage ``is_error`` / ``error_type`` / ``retry_count``
  peuplés par ``_send`` et persistés par ``persist_sumup_exchanges`` ;
- l'endpoint ``GET /api/admin/payment-failures`` (agrégation double source :
  payment_attempts + sumup_exchanges) ;
- l'endpoint ``GET /api/pos/payments/cb/terminal-status`` (sonde TPE) ;
- le filtre ``error_type`` + exposition des nouveaux champs sur
  ``GET /api/admin/sumup-exchanges``.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.services.sumup_service as svc_mod
from app.main import app
from app.models import Base
from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus
from app.models.pos import PaymentMethod
from app.models.sumup_exchange import SumUpExchange
from app.models.user import User, UserRole
from app.services.sumup_exchange_log import persist_sumup_exchanges
from app.services.sumup_service import SumUpService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    monkeypatch.setattr(svc_mod, "RETRY_WAIT_MULTIPLIER", 0.0)
    monkeypatch.setattr(svc_mod, "RETRY_WAIT_MIN", 0.0)
    monkeypatch.setattr(svc_mod, "RETRY_WAIT_MAX", 0.0)


# ---------------------------------------------------------------------------
# _send populates the triage fields
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_send_classifies_http_error_type():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"error_code": "READER_OFFLINE"})

    s = SumUpService()
    s.api_key = "sup_sk_test_x"
    s._transport = httpx.MockTransport(handler)
    async with s._client(5) as client:
        await s._send(client, "reader_push", "POST", "https://api.sumup.com/v0.1/x")
    rec = s.exchanges[-1]
    assert rec["is_error"] is True
    assert rec["error_type"] == "READER_OFFLINE"  # code wins over http_422
    assert rec["retry_count"] == 0


@pytest.mark.anyio
async def test_send_http_status_bucket_when_no_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    s = SumUpService()
    s.api_key = "sup_sk_test_x"
    s._transport = httpx.MockTransport(handler)
    async with s._client(5) as client:
        await s._send(client, "get_status", "GET", "https://api.sumup.com/v0.1/x")
    rec = s.exchanges[-1]
    assert rec["error_type"] == "http_500"


@pytest.mark.anyio
async def test_persist_writes_triage_fields():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    svc = SumUpService()
    svc.exchanges = [{
        "operation": "reader_push", "method": "POST", "ok": False,
        "is_error": True, "error_type": "READER_BUSY", "retry_count": 2,
        "latency_ms": 5,
    }]
    async with Session() as s:
        await persist_sumup_exchanges(s, svc)
        await s.commit()
        row = (await s.execute(select(SumUpExchange))).scalar_one()
        assert row.is_error is True
        assert row.error_type == "READER_BUSY"
        assert row.retry_count == 2
    await eng.dispose()


@pytest.mark.anyio
async def test_persist_derives_is_error_when_absent():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    svc = SumUpService()
    # A legacy-shaped record with ok=False but no explicit is_error.
    svc.exchanges = [{"operation": "get_status", "method": "GET", "ok": False}]
    async with Session() as s:
        await persist_sumup_exchanges(s, svc)
        await s.commit()
        row = (await s.execute(select(SumUpExchange))).scalar_one()
        assert row.is_error is True
    await eng.dispose()


# ---------------------------------------------------------------------------
# Endpoint tests via ASGI + in-memory SQLite (dependency overrides)
# ---------------------------------------------------------------------------


@pytest.fixture
async def app_ctx():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as s:
        u = User(
            username="mgr", email="mgr@v.fr", password_hash="x" * 60,
            role=UserRole.manager, is_active=True,
        )
        s.add(u)
        await s.commit()
        uid = u.id

    async def _override_db():
        async with Session() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    from app.api.admin.router import manager_only as admin_manager_only
    from app.core.database import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=uid, username="mgr", email="mgr@v.fr",
        password_hash="x" * 60, role=UserRole.manager, is_active=True,
    )
    app.dependency_overrides[admin_manager_only] = lambda: None
    yield Session
    app.dependency_overrides.clear()
    await eng.dispose()


@pytest.mark.anyio
async def test_payment_failures_endpoint_aggregates(app_ctx):
    Session = app_ctx
    async with Session() as s:
        s.add_all([
            PaymentAttempt(
                method=PaymentMethod.card, amount=10,
                status=PaymentAttemptStatus.failed, error_detail="TPE hors ligne",
            ),
            PaymentAttempt(
                method=PaymentMethod.card, amount=20,
                status=PaymentAttemptStatus.failed, error_detail="TPE hors ligne",
            ),
            PaymentAttempt(
                method=PaymentMethod.card, amount=30,
                status=PaymentAttemptStatus.succeeded,  # not a failure
            ),
            SumUpExchange(
                operation="reader_push", method="POST", ok=False,
                is_error=True, error_type="READER_OFFLINE", retry_count=1,
            ),
            SumUpExchange(
                operation="reader_push", method="POST", ok=False,
                is_error=True, error_type="READER_OFFLINE", retry_count=2,
            ),
        ])
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/admin/payment-failures?days=7")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_failed_attempts"] == 2
        assert len(body["failures"]) == 2
        # error_stats grouped by error_detail.
        assert body["error_stats"][0]["error"] == "TPE hors ligne"
        assert body["error_stats"][0]["count"] == 2
        # sumup_error_types: READER_OFFLINE x2, retries summed = 3.
        offline = [e for e in body["sumup_error_types"] if e["error_type"] == "READER_OFFLINE"][0]
        assert offline["count"] == 2
        assert offline["total_retries"] == 3


@pytest.mark.anyio
async def test_sumup_exchanges_error_type_filter_and_fields(app_ctx):
    Session = app_ctx
    async with Session() as s:
        s.add_all([
            SumUpExchange(
                operation="reader_push", method="POST", ok=False,
                is_error=True, error_type="READER_BUSY", retry_count=1,
            ),
            SumUpExchange(
                operation="get_status", method="GET", ok=False,
                is_error=True, error_type="http_500", retry_count=2,
            ),
        ])
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/admin/sumup-exchanges?error_type=READER_BUSY")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] == 1
        ex = body["exchanges"][0]
        assert ex["error_type"] == "READER_BUSY"
        assert ex["is_error"] is True
        assert ex["retry_count"] == 1


@pytest.mark.anyio
async def test_terminal_status_endpoint(app_ctx, monkeypatch):
    async def fake_ping(self):
        return {
            "configured": True, "paired": True, "online": True, "ready": True,
            "status": "online", "message": "TPE en ligne (IDLE)",
            "battery_level": 85, "connection_type": "WIFI",
        }

    monkeypatch.setattr(
        "app.services.sumup_service.SumUpService.ping_reader", fake_ping
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/pos/payments/cb/terminal-status")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["online"] is True
        assert body["ready"] is True
        assert body["battery_level"] == 85
