"""Smoke tests for new admin endpoints (audits C11 + C12).

The business logic is covered by `test_cash_reporting.py` and
`test_embeddings_cleanup.py`. These tests just confirm:
- the routes are registered (deploy doesn't 404 them)
- the manager-only guard rejects unauthenticated calls (401)
"""

import pytest


NEW_ADMIN_ROUTES = [
    ("GET", "/api/admin/cash-reporting/monthly?year=2026&month=5"),
    ("GET", "/api/admin/cash-reporting/last-12?n_months=3"),
    ("GET", "/api/admin/embeddings/cleanup/preview"),
    ("POST", "/api/admin/embeddings/cleanup/run"),
]


@pytest.mark.anyio
async def test_routes_registered():
    """All four new admin endpoints are mounted in the FastAPI app."""
    from app.main import app

    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/admin/cash-reporting/monthly" in paths
    assert "/api/admin/cash-reporting/last-12" in paths
    assert "/api/admin/embeddings/cleanup/preview" in paths
    assert "/api/admin/embeddings/cleanup/run" in paths


@pytest.mark.anyio
@pytest.mark.parametrize("method,path", NEW_ADMIN_ROUTES)
async def test_auth_gate(client, method, path):
    """Unauthenticated calls return 401, not 404 / 500."""
    res = await client.request(method, path)
    assert res.status_code == 401
