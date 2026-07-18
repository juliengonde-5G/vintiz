"""Tests de l'historique des lectures douchette (product_scan_logs).

Couvre :
- un scan hit crée une ligne ``matched=true`` avec nom/prix dénormalisés ;
- un scan miss crée une ligne ``matched=false`` **malgré le 404** (la ligne
  est commitée avant le raise, elle doit survivre au rollback de get_db) ;
- ``GET /api/admin/scan-logs`` liste et filtre (manager only) ;
- la purge quotidienne supprime les lignes > 7 jours et garde les récentes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base
from app.models.product import Category, Product, ProductStatus
from app.models.scan_log import ProductScanLog
from app.models.user import User, UserRole


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def app_ctx():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as s:
        u = User(
            username="mgr", email="mgr@v.fr", password_hash="x" * 60,
            role=UserRole.manager, is_active=True,
        )
        cat = Category(name="Robes")
        s.add_all([u, cat])
        await s.flush()
        p = Product(
            barcode="VTZ-2026-000001",
            name="Robe fleurie",
            category_id=cat.id,
            sale_price=19.90,
            status=ProductStatus.display,
        )
        s.add(p)
        await s.commit()
        uid, pid = u.id, p.id

    async def _override_db():
        async with Session() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    from app.api.admin.router import manager_only as admin_manager_only
    from app.core.database import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=uid, username="mgr", email="mgr@v.fr",
        password_hash="x" * 60, role=UserRole.manager, is_active=True,
    )
    app.dependency_overrides[admin_manager_only] = lambda: None
    yield Session, eng, uid, pid
    app.dependency_overrides.clear()
    await eng.dispose()


@pytest.mark.anyio
async def test_scan_hit_creates_matched_row(app_ctx):
    Session, _eng, uid, pid = app_ctx
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/inventory/products/by-barcode/VTZ-2026-000001")
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Robe fleurie"

    async with Session() as s:
        rows = (await s.execute(select(ProductScanLog))).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.matched is True
        assert row.barcode_raw == "VTZ-2026-000001"
        assert row.barcode_normalized == "VTZ-2026-000001"
        assert row.product_id == pid
        assert row.product_name == "Robe fleurie"
        assert float(row.sale_price) == pytest.approx(19.90)
        assert row.user_id == uid


@pytest.mark.anyio
async def test_scan_miss_creates_row_despite_404(app_ctx):
    Session, _eng, uid, _pid = app_ctx
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/inventory/products/by-barcode/INCONNU-999")
        assert r.status_code == 404, r.text

    # La ligne survit au rollback déclenché par le 404 (commit avant raise).
    async with Session() as s:
        rows = (await s.execute(select(ProductScanLog))).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.matched is False
        assert row.barcode_normalized == "INCONNU-999"
        assert row.product_id is None
        assert row.product_name is None
        assert row.user_id == uid


@pytest.mark.anyio
async def test_admin_scan_logs_lists_and_filters(app_ctx):
    _Session, _eng, _uid, _pid = app_ctx
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Un hit + un miss via le endpoint réel.
        await ac.get("/api/inventory/products/by-barcode/VTZ-2026-000001")
        await ac.get("/api/inventory/products/by-barcode/INCONNU-999")

        r = await ac.get("/api/admin/scan-logs")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] == 2

        r2 = await ac.get("/api/admin/scan-logs?matched=false")
        assert r2.json()["count"] == 1
        assert r2.json()["scans"][0]["barcode_normalized"] == "INCONNU-999"

        r3 = await ac.get("/api/admin/scan-logs?q=fleurie")
        assert r3.json()["count"] == 1
        assert r3.json()["scans"][0]["product_name"] == "Robe fleurie"


@pytest.mark.anyio
async def test_purge_deletes_old_rows_keeps_recent(app_ctx, monkeypatch):
    Session, eng, _uid, _pid = app_ctx
    now = datetime.now(timezone.utc)
    async with Session() as s:
        s.add_all([
            ProductScanLog(
                barcode_raw="OLD", barcode_normalized="OLD", matched=False,
                created_at=now - timedelta(days=10),
            ),
            ProductScanLog(
                barcode_raw="FRESH", barcode_normalized="FRESH", matched=False,
                created_at=now - timedelta(hours=1),
            ),
        ])
        await s.commit()

    # Le job ouvre sa propre session sur app.jobs.engine → on le pointe
    # sur l'engine de test.
    import app.jobs as jobs

    monkeypatch.setattr(jobs, "engine", eng)
    await jobs.run_daily_scan_log_purge()

    async with Session() as s:
        rows = (await s.execute(select(ProductScanLog))).scalars().all()
        assert [r.barcode_normalized for r in rows] == ["FRESH"]
