"""Go-live reset — l'inventaire est conservé, l'opérationnel est vidé.

Vérifie le contrat du script ``scripts/go_live_reset.py`` : après exécution,
les ventes / clients / fidélité / Z-reports sont à zéro, mais les produits,
catégories et zones restent intacts. Tourne sur SQLite (chemin DELETE).
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import Client, LoyaltyAccount
from app.models.events import EventLog, EventSource, EventType
from app.models.product import Category, Product, ProductStatus
from app.models.pos import Transaction, TransactionType
from app.models.user import User, UserRole


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _load_reset_module(engine):
    """Charge go_live_reset.py en injectant le moteur de test à la place du
    moteur applicatif (le script lit ``app.core.database.engine``)."""
    import app.core.database as db_mod

    db_mod.engine = engine  # monkeypatch le moteur partagé
    # tests/ → api/ → apps/ → <repo root>/scripts/go_live_reset.py
    path = (
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "go_live_reset.py"
    )
    spec = importlib.util.spec_from_file_location("go_live_reset", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
async def seeded_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        # Inventaire (à conserver)
        cat = Category(name="Robes")
        s.add(cat)
        await s.flush()
        for i in range(3):
            s.add(Product(
                barcode=f"VTZ{i:05d}", name=f"Robe {i}", sale_price=50,
                status=ProductStatus.displayed, category_id=cat.id,
            ))
        # Opérationnel (à effacer)
        user = User(username="u", email="u@t.fr", password_hash="x" * 60,
                    role=UserRole.manager, is_active=True)
        s.add(user)
        await s.flush()
        client = Client(first_name="Marie", last_name="D", email="m@t.fr")
        s.add(client)
        await s.flush()
        s.add(LoyaltyAccount(client_id=client.id, points=10,
                             membership_number="V000001"))
        s.add(Transaction(
            transaction_number=1, transaction_type=TransactionType.sale,
            total_ht=40, total_tva=10, total_ttc=50, hash_chain="a" * 64,
            user_id=user.id,
        ))
        # Events log : mix de ``product.created`` (à conserver) + de bruit
        # opérationnel (customer.visited / cashier_session_closed) à effacer.
        # On a 3 product.created (un par produit) + 2 traces opérationnelles.
        from sqlalchemy import select
        now = datetime.now(timezone.utc)
        prod_rows = (await s.execute(select(Product))).scalars().all()
        for p in prod_rows:
            s.add(EventLog(
                occurred_at=now,
                event_type=EventType.product_created,
                source=EventSource.admin,
                product_id=p.id,
                user_id=user.id,
            ))
        s.add(EventLog(
            occurred_at=now,
            event_type=EventType.customer_visited,
            source=EventSource.site,
            customer_id=client.id,
        ))
        s.add(EventLog(
            occurred_at=now,
            event_type=EventType.cashier_session_closed,
            source=EventSource.pos,
            user_id=user.id,
        ))
        await s.commit()
    yield engine
    await engine.dispose()


async def _count(engine, table: str) -> int:
    async with AsyncSession(engine) as s:
        return int((await s.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one())


async def _count_where(engine, table: str, where: str) -> int:
    async with AsyncSession(engine) as s:
        return int(
            (
                await s.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"))
            ).scalar_one()
        )


@pytest.mark.anyio
async def test_dry_run_changes_nothing(seeded_engine):
    mod = _load_reset_module(seeded_engine)
    rc = await mod.main(confirm=False, dry_run=True)
    assert rc == 0
    assert await _count(seeded_engine, "transactions") == 1
    assert await _count(seeded_engine, "clients") == 1
    assert await _count(seeded_engine, "products") == 3
    # events_log intact en dry-run
    assert await _count(seeded_engine, "events_log") == 5


@pytest.mark.anyio
async def test_live_wipes_operational_keeps_inventory(seeded_engine):
    mod = _load_reset_module(seeded_engine)
    rc = await mod.main(confirm=True, dry_run=False)
    assert rc == 0
    # Opérationnel vidé
    assert await _count(seeded_engine, "transactions") == 0
    assert await _count(seeded_engine, "clients") == 0
    assert await _count(seeded_engine, "loyalty_accounts") == 0
    # Inventaire INTACT
    assert await _count(seeded_engine, "products") == 3
    assert await _count(seeded_engine, "categories") == 1
    # events_log : seuls les ``product.created`` survivent (carve-out audit).
    assert await _count(seeded_engine, "events_log") == 3
    assert (
        await _count_where(
            seeded_engine, "events_log", "event_type = 'product.created'"
        )
        == 3
    )
    assert (
        await _count_where(
            seeded_engine, "events_log", "event_type != 'product.created'"
        )
        == 0
    )


@pytest.mark.anyio
async def test_requires_confirm_or_dry_run(seeded_engine):
    mod = _load_reset_module(seeded_engine)
    rc = await mod.main(confirm=False, dry_run=False)
    assert rc == 2
    # Rien touché
    assert await _count(seeded_engine, "transactions") == 1
