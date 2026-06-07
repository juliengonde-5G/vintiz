"""Garde-fou ouverture caisse : une seconde ouverture alors qu'une caisse est
déjà ouverte renvoie 409 (et non un 500 avalé côté tablette)."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base
from app.models.user import User, UserRole


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def setup():
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
        # Reproduit get_db : commit en fin de requête réussie.
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
    yield
    app.dependency_overrides.clear()
    await eng.dispose()


@pytest.mark.anyio
async def test_second_open_returns_409(setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.post("/api/pos/drawer/open", json={"opening_amount": 100})
        assert r1.status_code == 200, r1.text

        r2 = await ac.post("/api/pos/drawer/open", json={"opening_amount": 50})
        assert r2.status_code == 409
        assert "déjà ouverte" in r2.json()["detail"].lower()


@pytest.mark.anyio
async def test_drawer_current_returns_open_after_open(setup):
    """Régression : /drawer/current 500-ait quand une caisse était OUVERTE
    (imports fantômes app.models.payment/transaction) → le POS retombait sur
    « fermée ». On vérifie qu'il renvoie bien open=true + le compteur."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/pos/drawer/open", json={"opening_amount": 100})
        assert r.status_code == 200, r.text

        cur = await ac.get("/api/pos/drawer/current")
        assert cur.status_code == 200, cur.text
        body = cur.json()
        assert body["open"] is True
        assert body["expected_cash"] == 100.0
