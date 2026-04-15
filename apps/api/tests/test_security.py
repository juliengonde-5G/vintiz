"""Regression tests for the security fixes shipped in claude/app-testing-audit-fixes-31Iez."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import rate_limit
from app.core.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    """Make sure each test starts from a clean rate-limit state."""
    rate_limit._buckets.clear()
    yield
    rate_limit._buckets.clear()


@pytest.mark.anyio
async def test_login_invalid_credentials_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/login",
            data={"username": "nope", "password": "wrong"},
        )
        assert resp.status_code == 401


@pytest.mark.anyio
async def test_login_rate_limit_kicks_in_after_max_attempts():
    """After LOGIN_RATE_LIMIT_ATTEMPTS bad attempts the next call must return 429."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(settings.LOGIN_RATE_LIMIT_ATTEMPTS):
            await client.post(
                "/api/auth/login",
                data={"username": "nope", "password": "wrong"},
            )
        resp = await client.post(
            "/api/auth/login",
            data={"username": "nope", "password": "wrong"},
        )
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers


@pytest.mark.anyio
async def test_create_tables_requires_admin_bootstrap_key(monkeypatch):
    """Old behaviour aliased SECRET_KEY — verify the new env var is required."""
    monkeypatch.delenv("ADMIN_BOOTSTRAP_KEY", raising=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/admin/create-tables",
            headers={"X-Admin-Key": "anything"},
        )
        assert resp.status_code == 503  # not configured


@pytest.mark.anyio
async def test_create_tables_rejects_wrong_key(monkeypatch):
    monkeypatch.setenv("ADMIN_BOOTSTRAP_KEY", "right-key")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/admin/create-tables",
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert resp.status_code == 403


@pytest.mark.anyio
async def test_security_headers_present_on_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert "x-request-id" in resp.headers


@pytest.mark.anyio
async def test_lookup_client_invalid_email_returns_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/crm/clients/lookup", params={"email": "not-an-email"})
        assert resp.status_code == 400
