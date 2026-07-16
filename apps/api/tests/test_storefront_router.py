"""Public storefront endpoints — catalogue exposé sur vintiz.fr.

Vérifie que ``/api/storefront/products`` ne renvoie que les pièces
``FLOOR_STATUSES`` (sur le rayon), que la map des catégories publiques
fonctionne, et que la fiche détail expose les photos + des pièces
similaires."""
from __future__ import annotations


import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.storefront.router import _public_category
from app.main import app
from app.models import Base
from app.models.product import Category, Product, ProductStatus


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def _setup_db(monkeypatch):
    """In-memory SQLite + override la DB session du module pour cette
    suite. On ne touche pas aux autres fixtures globales du projet."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async def _override():
        async with Session() as s:
            yield s

    from app.core.database import get_db

    app.dependency_overrides[get_db] = _override
    yield Session
    app.dependency_overrides.pop(get_db, None)
    await eng.dispose()


async def _seed_product(
    session_factory,
    *,
    name="Robe Sandro",
    brand="Sandro",
    barcode="VTZ100001",
    status=ProductStatus.displayed,
    category_name="Robes",
    price=95.0,
    description="Robe fluide en viscose, en parfait état.",
):
    async with session_factory() as s:
        # Catégorie (unique par nom)
        cat = Category(name=category_name)
        s.add(cat)
        await s.flush()
        p = Product(
            barcode=barcode,
            name=name,
            brand=brand,
            sale_price=price,
            status=status,
            category_id=cat.id,
            description=description,
        )
        s.add(p)
        await s.commit()
        await s.refresh(p)
        return p


@pytest.mark.anyio
async def test_category_mapping_handles_singular_plural_and_synonyms():
    assert _public_category("Robe") == "robe"
    assert _public_category("Robes") == "robe"
    assert _public_category("Manteau") == "veste"
    assert _public_category("Sneakers") == "chaussures"
    assert _public_category("Sac à main") == "sac"
    assert _public_category("Foulard en soie") == "accessoire"
    assert _public_category("Inconnu") is None
    assert _public_category("") is None


@pytest.mark.anyio
async def test_list_products_returns_only_floor_status(_setup_db):
    Session = _setup_db
    await _seed_product(Session, barcode="VTZ-DISPO", status=ProductStatus.displayed)
    await _seed_product(Session, barcode="VTZ-STOCK", status=ProductStatus.stock)
    await _seed_product(Session, barcode="VTZ-SOLD", status=ProductStatus.sold)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/storefront/products")
    assert res.status_code == 200
    slugs = {p["slug"] for p in res.json()}
    # Seul le ``displayed`` est exposé publiquement.
    assert "VTZ-DISPO" in slugs
    assert "VTZ-STOCK" not in slugs
    assert "VTZ-SOLD" not in slugs


@pytest.mark.anyio
async def test_get_product_detail_includes_related(_setup_db):
    Session = _setup_db
    main = await _seed_product(
        Session, barcode="VTZ-MAIN", name="Robe principale",
        brand="Sandro", category_name="Robes",
    )
    await _seed_product(
        Session, barcode="VTZ-SIBLING-1", name="Robe sœur 1",
        brand="Sézane", category_name="Robes",
    )
    await _seed_product(
        Session, barcode="VTZ-OTHER", name="Veste off-topic",
        brand="IRO", category_name="Vestes",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/storefront/products/{main.barcode}")
    assert res.status_code == 200
    body = res.json()
    assert body["slug"] == "VTZ-MAIN"
    assert body["category"] == "robe"
    assert body["available"] is True
    # On retrouve la pièce sœur (même catégorie publique) dans related, pas la veste.
    rel_slugs = {r["slug"] for r in body["related"]}
    assert "VTZ-SIBLING-1" in rel_slugs
    assert "VTZ-OTHER" not in rel_slugs


@pytest.mark.anyio
async def test_get_product_unknown_returns_404(_setup_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/storefront/products/NOPE")
    assert res.status_code == 404


@pytest.mark.anyio
async def test_categories_endpoint_groups_synonyms(_setup_db):
    Session = _setup_db
    await _seed_product(Session, barcode="VTZ-A", category_name="Robes")
    await _seed_product(Session, barcode="VTZ-B", category_name="Robe longue")  # variante
    await _seed_product(Session, barcode="VTZ-C", category_name="Manteau")     # → veste
    await _seed_product(Session, barcode="VTZ-D", category_name="Manteaux")    # → veste

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/storefront/categories")
    assert res.status_code == 200
    body = res.json()
    counts = {c["key"]: c["count"] for c in body["categories"]}
    assert counts.get("robe") == 2
    assert counts.get("veste") == 2
    assert body["total"] == 4
