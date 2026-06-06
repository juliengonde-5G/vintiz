"""Tests du monitoring services externes (/api/admin/monitoring).

- la route est montée (pas de 404 au déploiement) ;
- le garde manager rejette l'anonyme (401) ;
- sans aucune clé configurée, le rapport est « tout vert » (DB OK, les
  services externes non configurés sont sains, aucun appel réseau).

Autonome sur SQLite (comme test_database_backup) — n'utilise pas l'engine
partagé qui pointe sur le PostgreSQL de dev.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as s:
        yield s
    await eng.dispose()


@pytest.mark.anyio
async def test_monitoring_route_registered():
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/admin/monitoring" in paths


@pytest.mark.anyio
async def test_monitoring_auth_gate():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/admin/monitoring")
    # 401 (auth) résolu avant tout accès DB.
    assert res.status_code == 401


@pytest.mark.anyio
async def test_monitoring_all_healthy_when_unconfigured(session, monkeypatch):
    # Pas de clés → aucun appel réseau, services externes « Non configuré ».
    monkeypatch.delenv("SUMUP_API_KEY", raising=False)
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    monkeypatch.setattr("app.services.app_config.get_section", lambda *a, **k: {})

    from app.services.monitoring_service import SERVICES, MonitoringService

    report = await MonitoringService(session).check_all()

    names = {svc.name for svc in report.services}
    assert names == set(SERVICES)
    db = next(svc for svc in report.services if svc.name == "db")
    assert db.healthy is True
    # Aucun service KO → rapport global sain.
    assert report.all_healthy is True
