"""Lier / délier une cliente à une transaction déjà réalisée.

POST /api/pos/transactions/{id}/client — n'altère pas la chaîne NF525
(client_id hors hash), trace le changement, gère 404 cliente.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base
from app.models.client import Client
from app.models.pos import Payment, PaymentMethod, Transaction, TransactionType
from app.models.user import User, UserRole


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def setup(monkeypatch):
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as s:
        manager = User(
            username="mgr", email="mgr@v.fr", password_hash="x" * 60,
            role=UserRole.manager, is_active=True,
        )
        s.add(manager)
        await s.flush()
        client = Client(first_name="Léa", last_name="Martin", email="lea@v.fr")
        s.add(client)
        tx = Transaction(
            transaction_number=1,
            transaction_type=TransactionType.sale,
            user_id=manager.id,
            total_ht=25.0, total_tva=5.0, total_ttc=30.0,
            hash_chain="h1",
        )
        s.add(tx)
        await s.flush()
        s.add(Payment(transaction_id=tx.id, method=PaymentMethod.cash, amount=30.0))
        await s.commit()
        ids = {"manager": manager.id, "client": str(client.id), "tx": str(tx.id)}

    async def _override_db():
        async with Session() as s:
            yield s

    from app.api.pos.router import manager_only
    from app.core.database import get_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[manager_only] = lambda: User(
        id=ids["manager"], username="mgr", email="mgr@v.fr",
        password_hash="x" * 60, role=UserRole.manager, is_active=True,
    )
    yield ids, Session
    app.dependency_overrides.clear()
    await eng.dispose()


@pytest.mark.anyio
async def test_link_then_unlink_client(setup):
    ids, _ = setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Lier
        res = await ac.post(
            f"/api/pos/transactions/{ids['tx']}/client",
            json={"client_id": ids["client"]},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["client"] is not None
        assert body["client"]["id"] == ids["client"]
        # hash inchangé → chaîne NF525 intacte
        assert body["hash_chain"] == "h1"

        # Délier
        res = await ac.post(
            f"/api/pos/transactions/{ids['tx']}/client",
            json={"client_id": None},
        )
        assert res.status_code == 200
        assert res.json()["client"] is None


@pytest.mark.anyio
async def test_link_unknown_client_404(setup):
    ids, _ = setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            f"/api/pos/transactions/{ids['tx']}/client",
            json={"client_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert res.status_code == 404
