"""Versioning safety net: every route registered under /api/* must also
exist under /api/v1/*. Guarantees backwards compatibility while web
clients haven't migrated, and proves /api/v1/* is the canonical surface
the Android app will consume.

Once both apps/web and apps/site migrate to /api/v1/*, the legacy
include_router block in app/main.py can be removed and this test will
catch any forgotten /api/* hard-codes.

Tests are marked anyio so the autouse async fixture in conftest.py
(_create_tables) can run without a pytest deprecation warning, even
though these checks are pure-Python introspection.
"""
import pytest

from app.main import app


def _route_paths() -> tuple[set[str], set[str]]:
    v1_paths: set[str] = set()
    legacy_paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api/v1/"):
            v1_paths.add(path.removeprefix("/api/v1"))
        elif path.startswith("/api/"):
            legacy_paths.add(path.removeprefix("/api"))
    return v1_paths, legacy_paths


@pytest.mark.anyio
async def test_every_legacy_route_has_v1_counterpart():
    v1, legacy = _route_paths()
    missing_v1 = legacy - v1
    assert not missing_v1, (
        "Legacy /api/* routes without /api/v1/* counterpart: "
        f"{sorted(missing_v1)}"
    )


@pytest.mark.anyio
async def test_v1_is_canonical_surface():
    v1, _ = _route_paths()
    assert "/health" in v1, "v1 health endpoint missing"
    assert any(p.startswith("/auth/") for p in v1), "auth router not mounted under /api/v1/"
    assert any(p.startswith("/pos/") for p in v1), "pos router not mounted under /api/v1/"
    assert any(p.startswith("/inventory/") for p in v1), "inventory router not mounted under /api/v1/"


@pytest.mark.anyio
async def test_openapi_schema_only_exposes_v1():
    """OpenAPI spec is the contract the Android client generator reads.
    Legacy /api/* routes are mounted with include_in_schema=False so
    they don't pollute the surface seen by client codegen.
    """
    schema = app.openapi()
    paths = schema.get("paths", {})
    legacy_in_schema = [p for p in paths if p.startswith("/api/") and not p.startswith("/api/v1/")]
    assert not legacy_in_schema, (
        "Legacy /api/* routes leaking into OpenAPI schema: "
        f"{sorted(legacy_in_schema)}"
    )
