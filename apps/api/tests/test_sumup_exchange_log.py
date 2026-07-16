"""Tests for the SumUp exchange diagnostic log + authoritative CB attempt.

Covers :
- ``SumUpService._send`` records every call (success + transport error) with
  PCI/secret redaction (affiliate key never leaks) ;
- ``persist_sumup_exchanges`` writes rows, filters keys, prunes by age ;
- ``/api/pos/payments/cb/initiate`` is now authoritative : it creates a
  ``PaymentAttempt`` and returns its ``attempt_id`` even when SumUp is down,
  and flags a checkout created in *link* mode (no reader → the TPE never
  rings) ;
- ``GET /api/admin/sumup-exchanges`` returns the log + headline summary.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base
from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus
from app.models.sumup_exchange import SumUpExchange
from app.models.user import User, UserRole
from app.services.sumup_exchange_log import persist_sumup_exchanges
from app.services.sumup_service import SumUpService


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Fakes — drive SumUpService._send without touching the network
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, status_code: int = 200, text: str = "{}") -> None:
        self.status_code = status_code
        self.text = text
        self.content = text.encode()


class _FakeClient:
    def __init__(self, resp: _FakeResp | None = None, raise_exc: Exception | None = None):
        self._resp = resp
        self._raise = raise_exc

    async def request(self, method, url, json=None, params=None, headers=None):
        if self._raise is not None:
            raise self._raise
        return self._resp


# ---------------------------------------------------------------------------
# _send instrumentation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_send_records_success_and_redacts_affiliate_key():
    svc = SumUpService()
    svc.api_key = "sup_sk_test_abcdef"  # makes environment == sandbox
    resp = await svc._send(
        _FakeClient(_FakeResp(200, '{"id":"chk_1","status":"PENDING"}')),
        "reader_push",
        "POST",
        "https://api.sumup.com/v0.1/merchants/M/readers/R/checkout",
        json={"total_amount": {"value": 1000}, "affiliate": {"key": "TOPSECRETKEY"}},
        mode="reader",
        foreign_transaction_id="vintiz-XYZ",
    )
    assert resp.status_code == 200
    assert len(svc.exchanges) == 1
    rec = svc.exchanges[0]
    assert rec["operation"] == "reader_push"
    assert rec["method"] == "POST"
    assert rec["ok"] is True
    assert rec["http_status"] == 200
    assert rec["mode"] == "reader"
    assert rec["foreign_transaction_id"] == "vintiz-XYZ"
    assert rec["latency_ms"] is not None and rec["latency_ms"] >= 0
    # The affiliate key must NEVER appear in the persisted summary.
    assert "TOPSECRETKEY" not in (rec["request_summary"] or "")
    assert "affiliate" in (rec["request_summary"] or "")


@pytest.mark.anyio
async def test_send_records_transport_error_then_reraises():
    svc = SumUpService()
    svc.api_key = "sup_sk_test_abcdef"
    with pytest.raises(httpx.ConnectError):
        await svc._send(
            _FakeClient(raise_exc=httpx.ConnectError("boom")),
            "ping",
            "GET",
            "https://api.sumup.com/v0.1/merchants/M/readers/R",
        )
    assert len(svc.exchanges) == 1
    rec = svc.exchanges[0]
    assert rec["ok"] is False
    assert rec["http_status"] is None
    assert "ConnectError" in (rec["error"] or "")


@pytest.mark.anyio
async def test_send_redacts_secret_in_response_body():
    svc = SumUpService()
    svc.api_key = "sup_sk_test_abcdef"
    # SumUp echoing a bearer token in an error body must not be persisted raw.
    await svc._send(
        _FakeClient(_FakeResp(401, "Authorization: Bearer sup_sk_live_SHOULDNOTLEAK1234567890")),
        "get_status",
        "GET",
        "https://api.sumup.com/v0.1/checkouts/chk_1",
        mode="checkout",
        checkout_id="chk_1",
    )
    rec = svc.exchanges[0]
    assert rec["ok"] is False
    assert "SHOULDNOTLEAK" not in (rec["response_summary"] or "")


def test_drain_exchanges_clears_buffer():
    svc = SumUpService()
    svc.exchanges.append({"operation": "ping"})
    drained = svc.drain_exchanges()
    assert drained == [{"operation": "ping"}]
    assert svc.exchanges == []


# ---------------------------------------------------------------------------
# persist_sumup_exchanges — DB write + key filter + prune
# ---------------------------------------------------------------------------


def _full_record(**over) -> dict:
    base = {
        "operation": "reader_push",
        "method": "POST",
        "url": "https://api.sumup.com/v0.1/.../checkout",
        "mode": "reader",
        "checkout_id": "reader:abc",
        "reader_id": "reader_123",
        "foreign_transaction_id": "vintiz-1",
        "environment": "production",
        "request_summary": '{"total_amount": 1000}',
        "http_status": 201,
        "ok": True,
        "latency_ms": 42,
        "response_summary": '{"data": {}}',
        "error": None,
        # An extraneous key the helper must drop, not crash on.
        "not_a_column": "ignore me",
    }
    base.update(over)
    return base


@pytest.mark.anyio
async def test_persist_writes_rows_and_drops_unknown_keys():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    svc = SumUpService()
    svc.exchanges = [_full_record(), _full_record(operation="get_status", ok=False)]

    async with Session() as s:
        written = await persist_sumup_exchanges(s, svc, prune=True)
        await s.commit()
        assert written == 2
        rows = (await s.execute(select(SumUpExchange))).scalars().all()
        assert len(rows) == 2
        ops = {r.operation for r in rows}
        assert ops == {"reader_push", "get_status"}
    # Buffer drained.
    assert svc.exchanges == []
    await eng.dispose()


@pytest.mark.anyio
async def test_persist_prunes_rows_older_than_retention():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as s:
        old = SumUpExchange(
            operation="reader_push",
            method="POST",
            ok=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=40),
        )
        s.add(old)
        await s.commit()

    svc = SumUpService()
    svc.exchanges = [_full_record()]
    async with Session() as s:
        await persist_sumup_exchanges(s, svc, prune=True)
        await s.commit()
        rows = (await s.execute(select(SumUpExchange))).scalars().all()
        # Old row pruned, fresh row kept.
        assert len(rows) == 1
        assert rows[0].latency_ms == 42
    await eng.dispose()


@pytest.mark.anyio
async def test_persist_never_raises_on_bad_session():
    """A logging failure must be swallowed (returns 0), never bubble up."""

    class _BoomSession:
        def begin_nested(self):  # not awaitable → triggers the except path
            raise RuntimeError("nope")

    svc = SumUpService()
    svc.exchanges = [_full_record()]
    written = await persist_sumup_exchanges(_BoomSession(), svc)
    assert written == 0


# ---------------------------------------------------------------------------
# Endpoint behaviour — authoritative attempt + diagnostic + admin log
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
    # Admin routes gate on RoleChecker (its own token dep), not get_current_user.
    app.dependency_overrides[admin_manager_only] = lambda: None
    yield Session
    app.dependency_overrides.clear()
    await eng.dispose()


@pytest.mark.anyio
async def test_initiate_fails_closed_when_unconfigured(app_ctx):
    """Aucun paiement ne peut être créé sans identifiants SumUp complets."""
    Session = app_ctx
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/pos/payments/cb/initiate", json={"amount": 19.9})
        assert r.status_code == 503, r.text

    async with Session() as s:
        rows = (await s.execute(select(PaymentAttempt))).scalars().all()
        assert rows == []


@pytest.mark.anyio
async def test_initiate_flags_link_mode_no_reader(app_ctx, monkeypatch):
    """A checkout created in link mode must be flagged: the TPE won't ring."""
    Session = app_ctx
    monkeypatch.setenv("SUMUP_API_KEY", "sup_sk_test")
    monkeypatch.setenv("SUMUP_MERCHANT_CODE", "MTEST")

    async def fake_create_checkout(self, **kwargs):
        return {
            "checkout_id": "chk_link_1",
            "checkout_reference": "R",
            "amount": kwargs.get("amount"),
            "currency": "EUR",
            "status": "PENDING",
            "environment": "production",
            "mode": "checkout",  # link mode — no reader
        }

    monkeypatch.setattr(
        "app.services.sumup_service.SumUpService.create_checkout",
        fake_create_checkout,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/pos/payments/cb/initiate", json={"amount": 25})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["reader_targeted"] is False
        assert "diagnostic" in body
        assert "TPE" in body["diagnostic"]
        assert body["attempt_id"]

    async with Session() as s:
        att = (await s.execute(select(PaymentAttempt))).scalars().all()
        # Pending (not failed) — the link checkout was accepted by SumUp.
        assert att[0].status == PaymentAttemptStatus.pending


@pytest.mark.anyio
async def test_initiate_persists_exchanges_to_admin_log(app_ctx, monkeypatch):
    """End-to-end: a CB initiate that talked to SumUp lands in the log table
    and is returned by GET /api/admin/sumup-exchanges."""
    monkeypatch.setenv("SUMUP_API_KEY", "sup_sk_test")
    monkeypatch.setenv("SUMUP_MERCHANT_CODE", "MTEST")

    async def fake_create_checkout(self, **kwargs):
        # Simulate the service having pushed to a reader (SumUp accepted).
        self.exchanges.append({
            "operation": "reader_push", "method": "POST",
            "url": "https://api.sumup.com/v0.1/merchants/M/readers/R/checkout",
            "mode": "reader", "checkout_id": "reader:abc", "reader_id": "reader_1",
            "foreign_transaction_id": kwargs.get("foreign_transaction_id"),
            "environment": "production", "request_summary": '{"total_amount": 2500}',
            "http_status": 201, "ok": True, "latency_ms": 30,
            "response_summary": '{"data": {}}', "error": None,
        })
        return {
            "checkout_id": "reader:abc", "status": "PENDING",
            "environment": "production", "mode": "reader",
        }

    monkeypatch.setattr(
        "app.services.sumup_service.SumUpService.create_checkout",
        fake_create_checkout,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/pos/payments/cb/initiate", json={"amount": 25})
        assert r.status_code == 200, r.text
        assert r.json()["reader_targeted"] is True

        log = await ac.get("/api/admin/sumup-exchanges")
        assert log.status_code == 200, log.text
        body = log.json()
        assert body["count"] == 1
        assert body["exchanges"][0]["operation"] == "reader_push"
        assert body["summary"]["reader_pushes"] == 1
        assert body["summary"]["link_checkouts"] == 0


@pytest.mark.anyio
async def test_admin_sumup_exchanges_lists_log_with_summary(app_ctx):
    Session = app_ctx
    async with Session() as s:
        s.add_all([
            SumUpExchange(
                operation="create_checkout", method="POST", mode="checkout",
                http_status=201, ok=True, is_error=False, checkout_id="chk_1",
            ),
            SumUpExchange(
                operation="reader_push", method="POST", mode="reader",
                http_status=409, ok=False, is_error=True, error="ReaderBusy",
            ),
        ])
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/admin/sumup-exchanges")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] == 2
        assert body["summary"]["link_checkouts"] == 1
        assert body["summary"]["reader_pushes"] == 1
        assert body["summary"]["failures"] == 1

        # only_failed filter.
        r2 = await ac.get("/api/admin/sumup-exchanges?only_failed=true")
        assert r2.json()["count"] == 1
        assert r2.json()["exchanges"][0]["operation"] == "reader_push"
