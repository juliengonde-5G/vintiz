"""Tests file de réessai des paiements CB échoués (P4 — offline groundwork).

Couvre le modèle ``FailedPayment``, le service ``FailedPaymentService``
(create / retry_one / retry_failed_payments / listing) et les endpoints
(retry manuel POS + création auto sur échec récupérable de /initiate).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base
from app.models.failed_payment import FailedPayment, FailedPaymentStatus
from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus
from app.models.user import User, UserRole
from app.services.failed_payment_service import FailedPaymentService


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeSvc:
    """Stand-in for SumUpService — canned create_checkout, no network."""

    def __init__(self, result=None, results=None, configured=True):
        self.is_configured = configured
        self.exchanges: list = []
        self._result = result or {"status": "PENDING", "checkout_id": "chk_ok"}
        self._results = list(results) if results else None
        self.calls: list[dict] = []

    async def create_checkout(self, **kwargs):
        self.calls.append(kwargs)
        if self._results is not None:
            return self._results.pop(0)
        return self._result

    def drain_exchanges(self):
        out = self.exchanges
        self.exchanges = []
        return out


async def _memory_session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return eng, async_sessionmaker(eng, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Service — create + retry_one
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_failed_payment_schedules_retry():
    eng, Session = await _memory_session()
    async with Session() as s:
        svc = FailedPaymentService(svc=_FakeSvc())
        fp = await svc.create_failed_payment(
            s, amount=19.9, checkout_reference="R1",
            error_detail="TPE hors ligne", is_recoverable=True,
        )
        await s.commit()
        assert fp.status == FailedPaymentStatus.pending
        assert fp.next_retry_at is not None
        assert fp.attempt_count == 0
    await eng.dispose()


@pytest.mark.anyio
async def test_create_non_recoverable_is_abandoned_dead_letter():
    eng, Session = await _memory_session()
    async with Session() as s:
        svc = FailedPaymentService(svc=_FakeSvc())
        fp = await svc.create_failed_payment(
            s, amount=5, checkout_reference="R2", is_recoverable=False,
        )
        await s.commit()
        assert fp.status == FailedPaymentStatus.abandoned
        assert fp.next_retry_at is None
    await eng.dispose()


@pytest.mark.anyio
async def test_retry_one_success_marks_succeeded_and_uses_link():
    eng, Session = await _memory_session()
    fake = _FakeSvc(result={"status": "PENDING", "checkout_id": "chk_win", "mode": "checkout"})
    async with Session() as s:
        svc = FailedPaymentService(svc=fake)
        fp = await svc.create_failed_payment(s, amount=12, checkout_reference="R3")
        outcome = await svc.retry_one(s, fp)
        await s.commit()
        assert outcome["status"] == "SUCCESS"
        assert fp.status == FailedPaymentStatus.succeeded
        assert fp.resolved_checkout_id == "chk_win"
        assert fp.next_retry_at is None
        # Retry must go through a payment LINK, never a reader push.
        assert fake.calls[0]["prefer_link"] is True
    await eng.dispose()


@pytest.mark.anyio
async def test_retry_one_failure_reschedules_then_exhausts():
    eng, Session = await _memory_session()
    fake = _FakeSvc(result={"status": "FAILED", "error_detail": "still down"})
    async with Session() as s:
        svc = FailedPaymentService(svc=fake)
        fp = await svc.create_failed_payment(s, amount=8, checkout_reference="R4")
        fp.max_attempts = 2

        o1 = await svc.retry_one(s, fp)
        assert o1["status"] == "FAILED"
        assert fp.attempt_count == 1
        assert fp.status == FailedPaymentStatus.pending
        assert fp.next_retry_at is not None

        o2 = await svc.retry_one(s, fp)
        assert o2["status"] == "EXHAUSTED"
        assert fp.attempt_count == 2
        assert fp.status == FailedPaymentStatus.exhausted
        assert fp.next_retry_at is None
        await s.commit()
    await eng.dispose()


@pytest.mark.anyio
async def test_retry_one_skips_already_resolved():
    eng, Session = await _memory_session()
    async with Session() as s:
        svc = FailedPaymentService(svc=_FakeSvc())
        fp = await svc.create_failed_payment(s, amount=8, checkout_reference="R5")
        fp.status = FailedPaymentStatus.succeeded
        outcome = await svc.retry_one(s, fp)
        assert outcome["status"] == "SKIPPED"
    await eng.dispose()


# ---------------------------------------------------------------------------
# Service — batch retry_failed_payments
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_retry_batch_only_processes_due_rows():
    eng, Session = await _memory_session()
    fake = _FakeSvc(result={"status": "PENDING", "checkout_id": "chk_b"})
    now = datetime.now(timezone.utc)
    async with Session() as s:
        due = FailedPayment(
            amount=10, checkout_reference="DUE", status=FailedPaymentStatus.pending,
            is_recoverable=True, next_retry_at=now - timedelta(minutes=1),
        )
        future = FailedPayment(
            amount=10, checkout_reference="FUTURE", status=FailedPaymentStatus.pending,
            is_recoverable=True, next_retry_at=now + timedelta(hours=1),
        )
        s.add_all([due, future])
        await s.commit()
        due_id, future_id = due.id, future.id

    async with Session() as s:
        svc = FailedPaymentService(svc=fake)
        results = await svc.retry_failed_payments(s)
        assert len(results) == 1
        assert results[0]["failed_payment_id"] == str(due_id)

    async with Session() as s:
        due_row = await s.get(FailedPayment, due_id)
        future_row = await s.get(FailedPayment, future_id)
        assert due_row.status == FailedPaymentStatus.succeeded
        assert future_row.status == FailedPaymentStatus.pending  # untouched
    await eng.dispose()


@pytest.mark.anyio
async def test_retry_batch_noop_when_unconfigured():
    eng, Session = await _memory_session()
    fake = _FakeSvc(configured=False)
    now = datetime.now(timezone.utc)
    async with Session() as s:
        s.add(FailedPayment(
            amount=10, checkout_reference="DUE", status=FailedPaymentStatus.pending,
            is_recoverable=True, next_retry_at=now - timedelta(minutes=1),
        ))
        await s.commit()

    async with Session() as s:
        svc = FailedPaymentService(svc=fake)
        results = await svc.retry_failed_payments(s)
        assert results == []
        assert fake.calls == []  # never attempted
    await eng.dispose()


# ---------------------------------------------------------------------------
# Endpoints via ASGI
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

    from app.core.database import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=uid, username="mgr", email="mgr@v.fr",
        password_hash="x" * 60, role=UserRole.manager, is_active=True,
    )
    yield Session, uid
    app.dependency_overrides.clear()
    await eng.dispose()


@pytest.mark.anyio
async def test_retry_endpoint_404_for_unknown(app_ctx):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(f"/api/pos/payments/cb/retry/{uuid.uuid4()}")
        assert r.status_code == 404


@pytest.mark.anyio
async def test_retry_endpoint_success(app_ctx, monkeypatch):
    Session, _uid = app_ctx
    async with Session() as s:
        fp = FailedPayment(
            amount=15, checkout_reference="RX", status=FailedPaymentStatus.pending,
            is_recoverable=True,
        )
        s.add(fp)
        await s.commit()
        fp_id = fp.id

    async def fake_cc(self, **kwargs):
        return {"status": "PENDING", "checkout_id": "chk_manual", "mode": "checkout"}

    monkeypatch.setattr(
        "app.services.sumup_service.SumUpService.create_checkout", fake_cc
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(f"/api/pos/payments/cb/retry/{fp_id}")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "SUCCESS"

    async with Session() as s:
        row = await s.get(FailedPayment, fp_id)
        assert row.status == FailedPaymentStatus.succeeded


@pytest.mark.anyio
async def test_initiate_queues_failed_payment_on_recoverable_failure(app_ctx, monkeypatch):
    Session, _uid = app_ctx
    monkeypatch.setenv("SUMUP_API_KEY", "sup_sk_test")
    monkeypatch.setenv("SUMUP_MERCHANT_CODE", "MTEST")

    async def fake_cc(self, **kwargs):
        return {
            "checkout_id": "OFFLINE-R", "checkout_reference": "R",
            "amount": kwargs.get("amount"), "currency": "EUR",
            "status": "FAILED", "mode": "reader",
            "error_detail": "TPE hors ligne", "error_friendly": "TPE hors ligne",
            "recoverable": True,
        }

    monkeypatch.setattr(
        "app.services.sumup_service.SumUpService.create_checkout", fake_cc
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/pos/payments/cb/initiate", json={"amount": 42})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "FAILED"
        assert body["failed_payment_id"]

    async with Session() as s:
        rows = (await s.execute(select(FailedPayment))).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == FailedPaymentStatus.pending
        # And the authoritative PaymentAttempt still recorded the failure.
        attempts = (await s.execute(select(PaymentAttempt))).scalars().all()
        assert attempts[0].status == PaymentAttemptStatus.failed
