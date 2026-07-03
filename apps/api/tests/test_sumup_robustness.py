"""Tests robustesse paiement SumUp (P1 + P2).

Couvre les correctifs « les appels vers le TPE n'aboutissent pas » :

- timeouts relevés (30 s write / 20 s status) ;
- retry avec backoff exponentiel sur erreurs réseau transitoires, avec la
  garantie de sécurité : on ne rejoue JAMAIS un POST susceptible d'avoir déjà
  atteint le terminal (pas de double débit) ;
- classification des erreurs 422 reader (READER_BUSY / READER_OFFLINE
  récupérables vs définitives) ;
- pré-vol du statut TPE avant push + repli automatique vers un lien de
  paiement quand l'erreur est récupérable.

Tout passe par un ``httpx.MockTransport`` injecté dans ``SumUpService._transport``
— aucun appel réseau réel, aucune base de données.
"""

from __future__ import annotations

import httpx
import pytest

import app.services.sumup_service as svc_mod
from app.services.sumup_service import SumUpService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    """Zero the backoff waits so retry tests don't actually sleep."""
    monkeypatch.setattr(svc_mod, "RETRY_WAIT_MULTIPLIER", 0.0)
    monkeypatch.setattr(svc_mod, "RETRY_WAIT_MIN", 0.0)
    monkeypatch.setattr(svc_mod, "RETRY_WAIT_MAX", 0.0)


def _make_service(handler, *, reader: bool = False) -> SumUpService:
    """A configured service whose HTTP goes through ``handler`` (MockTransport)."""
    s = SumUpService()
    s.api_key = "sup_sk_test_abc123"
    s.merchant_code = "MTEST"
    s.reader_id = "reader-1" if reader else ""
    s._transport = httpx.MockTransport(handler)
    return s


class _Router:
    """Records calls and answers by (method, path-suffix)."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# P1.1 — timeouts
# ---------------------------------------------------------------------------


def test_timeout_constants_raised():
    assert svc_mod.CHECKOUT_TIMEOUT == 30.0
    assert svc_mod.STATUS_TIMEOUT == 20.0
    assert svc_mod.PING_TIMEOUT == 5.0


# ---------------------------------------------------------------------------
# P1.3 — retry with exponential backoff
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_send_retries_transient_connect_error_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json={"ok": True})

    s = _make_service(handler)
    async with s._client(5) as client:
        resp = await s._send(client, "get_status", "GET", "https://api.sumup.com/v0.1/x")
    assert resp.status_code == 200
    assert calls["n"] == 3
    rec = s.exchanges[-1]
    assert rec["ok"] is True
    assert rec["retry_count"] == 2  # 2 retries before the winning 3rd try


@pytest.mark.anyio
async def test_send_exhausts_retries_and_records_error_type():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("down", request=request)

    s = _make_service(handler)
    with pytest.raises(httpx.ConnectError):
        async with s._client(5) as client:
            await s._send(client, "get_status", "GET", "https://api.sumup.com/v0.1/x")
    assert calls["n"] == svc_mod.RETRY_MAX_ATTEMPTS == 3
    rec = s.exchanges[-1]
    assert rec["is_error"] is True
    assert rec["error_type"] == "ConnectError"
    assert rec["retry_count"] == 2


@pytest.mark.anyio
async def test_post_read_timeout_is_not_retried():
    """A POST that may already have reached the terminal must NOT be replayed."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("slow", request=request)

    s = _make_service(handler)
    with pytest.raises(httpx.ReadTimeout):
        async with s._client(5) as client:
            await s._send(client, "reader_push", "POST", "https://api.sumup.com/v0.1/x")
    assert calls["n"] == 1  # no replay of the non-idempotent POST
    assert s.exchanges[-1]["retry_count"] == 0


@pytest.mark.anyio
async def test_get_read_timeout_is_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"ok": True})

    s = _make_service(handler)
    async with s._client(5) as client:
        resp = await s._send(client, "get_status", "GET", "https://api.sumup.com/v0.1/x")
    assert resp.status_code == 200
    assert calls["n"] == 2


# ---------------------------------------------------------------------------
# P2.1 — recoverable vs definitive reader errors
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_push_to_reader_busy_is_recoverable_with_retry_after():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"error_code": "READER_BUSY"})

    s = _make_service(handler, reader=True)
    result = await s._push_to_reader(10.0, "EUR", "Vente", "REF1")
    assert result["status"] == "FAILED"
    assert result["recoverable"] is True
    assert result["retry_after"] == 5
    assert result["error_code"] == "READER_BUSY"
    assert "terminal" in result["error_friendly"].lower()


@pytest.mark.anyio
async def test_push_to_reader_offline_is_recoverable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"error_code": "READER_OFFLINE"})

    s = _make_service(handler, reader=True)
    result = await s._push_to_reader(10.0, "EUR", "Vente", "REF1")
    assert result["recoverable"] is True
    assert result["error_code"] == "READER_OFFLINE"


@pytest.mark.anyio
async def test_push_to_reader_bad_key_is_definitive():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error_code": "UNAUTHORIZED"})

    s = _make_service(handler, reader=True)
    result = await s._push_to_reader(10.0, "EUR", "Vente", "REF1")
    assert result["status"] == "FAILED"
    assert result["recoverable"] is False


@pytest.mark.anyio
async def test_push_to_reader_network_error_recoverable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no net", request=request)

    s = _make_service(handler, reader=True)
    result = await s._push_to_reader(10.0, "EUR", "Vente", "REF1")
    assert result["status"] == "FAILED"
    assert result["recoverable"] is True


# ---------------------------------------------------------------------------
# P1.2 + P2.2 — preflight ping + automatic link fallback
# ---------------------------------------------------------------------------


def _reader_router(*, live_status: str, push):
    """Build a handler that answers ping (pairing+live) and reader push/link.

    ``push`` is a callable(request) -> Response for the reader-push endpoint,
    and ``/checkouts`` always returns a PENDING link checkout.
    """
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(f"{request.method} {path}")
        if path.endswith("/status"):
            return httpx.Response(200, json={"data": {"status": live_status}})
        if path.endswith("/checkout"):
            return push(request)
        if path.endswith("/checkouts"):
            return httpx.Response(200, json={"id": "chk_link_1", "status": "PENDING"})
        if "/readers/" in path:  # pairing probe
            return httpx.Response(200, json={"status": "paired", "name": "Solo"})
        return httpx.Response(404, json={})

    handler.calls = calls  # type: ignore[attr-defined]
    return handler


@pytest.mark.anyio
async def test_create_checkout_preflight_offline_falls_back_to_link():
    handler = _reader_router(
        live_status="OFFLINE",
        push=lambda r: httpx.Response(200, json={"data": {"client_transaction_id": "x"}}),
    )
    s = _make_service(handler, reader=True)
    result = await s.create_checkout(10.0, description="Vente")
    assert result["fallback_mode"] is True
    assert result["mode"] == "checkout"
    assert result["status"] == "PENDING"
    assert "reader_error" in result
    # The reader push must never have been attempted (TPE was offline).
    assert not any(c.endswith("/checkout") for c in handler.calls)  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_create_checkout_recoverable_reader_push_falls_back_to_link():
    handler = _reader_router(
        live_status="ONLINE",
        push=lambda r: httpx.Response(422, json={"error_code": "READER_BUSY"}),
    )
    s = _make_service(handler, reader=True)
    result = await s.create_checkout(10.0, description="Vente")
    assert result["fallback_mode"] is True
    assert result["mode"] == "checkout"
    assert result["status"] == "PENDING"
    assert any(c.endswith("/checkout") for c in handler.calls)  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_create_checkout_definitive_reader_error_does_not_fall_back():
    handler = _reader_router(
        live_status="ONLINE",
        push=lambda r: httpx.Response(401, json={"error_code": "UNAUTHORIZED"}),
    )
    s = _make_service(handler, reader=True)
    result = await s.create_checkout(10.0, description="Vente")
    assert result["status"] == "FAILED"
    assert result.get("recoverable") is False
    assert "fallback_mode" not in result
    # No link checkout was created for a definitive error.
    assert not any(c.endswith("/checkouts") for c in handler.calls)  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_create_checkout_reader_success():
    handler = _reader_router(
        live_status="ONLINE",
        push=lambda r: httpx.Response(
            200, json={"data": {"client_transaction_id": "ctid-9"}}
        ),
    )
    s = _make_service(handler, reader=True)
    result = await s.create_checkout(10.0, description="Vente")
    assert result["status"] == "PENDING"
    assert result["mode"] == "reader"
    assert result["checkout_id"] == "reader:ctid-9"


@pytest.mark.anyio
async def test_create_checkout_prefer_link_skips_reader_and_ping():
    handler = _reader_router(
        live_status="ONLINE",
        push=lambda r: httpx.Response(500, json={}),  # would fail if hit
    )
    s = _make_service(handler, reader=True)
    result = await s.create_checkout(10.0, description="Retry", prefer_link=True)
    assert result["mode"] == "checkout"
    assert result["status"] == "PENDING"
    # prefer_link must bypass both the ping and the reader push entirely.
    assert all("/readers/" not in c for c in handler.calls)  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_create_checkout_not_configured_returns_failed():
    s = SumUpService()
    s.api_key = ""
    result = await s.create_checkout(10.0)
    assert result["status"] == "FAILED"
    assert result["checkout_id"].startswith("NOKEY-")
