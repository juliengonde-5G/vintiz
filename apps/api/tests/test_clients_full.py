"""Tests for GET /api/crm/clients/{id}/full (PR4 admin client detail).

The endpoint aggregates 6 sections (client, loyalty, taste, transactions,
consents, audit). Authentication is required, so the http-level test
just covers the auth gate; the data-shape contract is enforced by the
inline aggregation pulling on already-tested service modules
(``customer_brief``, etc.).
"""

import uuid

import pytest


@pytest.mark.anyio
async def test_full_endpoint_requires_auth(client):
    res = await client.get(f"/api/crm/clients/{uuid.uuid4()}/full")
    assert res.status_code == 401


@pytest.mark.anyio
async def test_full_endpoint_route_registered():
    """Route is wired into the router so deploy doesn't 404 it."""
    from app.main import app

    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/crm/clients/{client_id}/full" in paths
