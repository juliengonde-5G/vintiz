"""Error boundary — un 500 doit renvoyer un JSON lisible, pas casser la socket.

Régression du bug « Failed to fetch » à la clôture de caisse (juin 2026) :
une exception non gérée dans un endpoint (ex. ``DBAPIError`` sur un enum
PostgreSQL désaligné) se propageait à travers la pile ``BaseHTTPMiddleware``,
corrompait le flux ASGI et réinitialisait la connexion → le navigateur
affichait « Failed to fetch » au lieu d'un 500.

Le boundary dans ``RequestIdMiddleware`` capture désormais l'exception et
renvoie un ``JSONResponse(500)`` portant le ``request_id`` ; ces tests
verrouillent ce comportement.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware.cors import CORSMiddleware

from app.core.middleware import (
    AuditContextMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _build_app() -> FastAPI:
    """Reproduit la pile middleware de production (même ordre que main.py)."""
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AuditContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/boom")
    async def boom():
        # Simule une erreur backend non gérée (ex. DBAPIError).
        raise RuntimeError("simulated backend failure")

    @app.get("/ok")
    async def ok():
        return {"status": "ok"}

    return app


@pytest.mark.anyio
async def test_unhandled_exception_returns_clean_500_json():
    app = _build_app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/boom")
    # Pas de connexion cassée : un vrai 500 JSON arrive.
    assert res.status_code == 500
    body = res.json()
    assert "detail" in body
    assert "request_id" in body and body["request_id"]
    assert body["error_type"] == "RuntimeError"
    # Le header de corrélation est présent.
    assert res.headers.get("x-request-id") == body["request_id"]


@pytest.mark.anyio
async def test_cors_header_present_even_on_500():
    """Le 500 doit porter les headers CORS (sinon le navigateur masque
    l'erreur réelle derrière un message CORS trompeur)."""
    app = _build_app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/boom", headers={"Origin": "http://localhost:3000"})
    assert res.status_code == 500
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.anyio
async def test_happy_path_still_works_and_stamps_request_id():
    app = _build_app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/ok")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert res.headers.get("x-request-id")
    # Les headers de sécurité sont toujours appliqués.
    assert res.headers.get("x-content-type-options") == "nosniff"
