"""Tests for the public storefront highlights endpoint (landing page).

Ce qui doit être garanti :
- jamais de placeholder : si rien de vendable, renvoie ``items=[]`` (la
  landing masque alors la section) ;
- curation manager prise d'abord, dans l'ordre saisi ;
- complétion par trend_score décroissant si la curation ne suffit pas ;
- dédup curation / trend ;
- filtres : seuls les statuts rayon (display/displayed/discounted/
  deep_discounted), exclut les produits vendus / test.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.crm.router import storefront_highlights
from app.models import Base
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.services import app_config


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        Category.__table__,
        Product.__table__,
        ProductPhoto.__table__,
    ]
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


@pytest.fixture(autouse=True)
def isolate_curation_picks(monkeypatch):
    """Each test starts with no curation picks unless it sets some.

    Stubs ``app_config.get_section`` rather than ``DEFAULT_PATH`` because the
    latter is captured at function-definition time in ``load_config(path=
    DEFAULT_PATH)`` so a setattr patch wouldn't affect already-bound calls.
    ``get_section`` is re-imported inside the endpoint via ``from ... import
    get_section`` so a module-level patch is honored at every call.
    """
    state: dict[str, dict] = {"curation_picks": {"items": [], "curator_note": ""}}

    def _fake_get_section(name: str, **_kwargs):
        return dict(state.get(name, {}))

    def _set_curation(items, curator_note=""):
        state["curation_picks"] = {"items": items, "curator_note": curator_note}

    monkeypatch.setattr(app_config, "get_section", _fake_get_section)
    return _set_curation


async def _make_floor_product(
    session, *, name, score=50.0, status=ProductStatus.displayed,
    sale_price=30.0, is_test=False,
) -> Product:
    cat = Category(name="Robes")
    session.add(cat)
    await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name=name,
        category_id=cat.id,
        sale_price=sale_price,
        status=status,
        trend_score=score,
        is_test=is_test,
        photo_url=f"/uploads/{name.lower().replace(' ', '_')}.jpg",
    )
    session.add(p)
    await session.flush()
    return p


@pytest.mark.anyio
async def test_empty_when_no_floor_products(session):
    """Pas de boutique → pas de demo → section masquée côté landing."""
    payload = await storefront_highlights(db=session, limit=4)
    assert payload == {"items": [], "curator_note": ""}


@pytest.mark.anyio
async def test_falls_back_to_top_trending_when_no_curation(session):
    a = await _make_floor_product(session, name="Robe A", score=90)
    await _make_floor_product(session, name="Robe B", score=50)
    c = await _make_floor_product(session, name="Robe C", score=80)
    await _make_floor_product(session, name="Robe D", score=20)

    payload = await storefront_highlights(db=session, limit=2)
    names = [it["name"] for it in payload["items"]]
    assert names == ["Robe A", "Robe C"]
    assert payload["items"][0]["id"] == str(a.id)
    assert payload["items"][1]["id"] == str(c.id)
    # No reason set when piece comes from auto trend-fill.
    assert payload["items"][0]["reason"] is None


@pytest.mark.anyio
async def test_curation_takes_priority_and_preserves_order(session, isolate_curation_picks):
    high = await _make_floor_product(session, name="Top trend", score=99)
    pick1 = await _make_floor_product(session, name="Pick 1", score=10)
    pick2 = await _make_floor_product(session, name="Pick 2", score=20)
    await _make_floor_product(session, name="Other", score=70)

    isolate_curation_picks(
        [
            {"product_id": str(pick1.id), "reason": "Tendance bohème"},
            {"product_id": str(pick2.id), "reason": "Petit prix"},
        ],
        curator_note="Sélection de la semaine",
    )

    payload = await storefront_highlights(db=session, limit=3)
    names = [it["name"] for it in payload["items"]]
    # Curated first, in the manager's order, then top-trend padding.
    assert names == ["Pick 1", "Pick 2", "Top trend"]
    assert payload["items"][0]["reason"] == "Tendance bohème"
    assert payload["items"][1]["reason"] == "Petit prix"
    assert payload["curator_note"] == "Sélection de la semaine"
    # Top-trend padding has no reason.
    assert payload["items"][2]["reason"] is None
    assert payload["items"][2]["id"] == str(high.id)


@pytest.mark.anyio
async def test_curated_picks_not_on_floor_are_silently_dropped(session, isolate_curation_picks):
    sold = await _make_floor_product(session, name="Sold pick", score=99)
    sold.status = ProductStatus.sold
    await session.flush()
    backup = await _make_floor_product(session, name="Backup", score=60)

    isolate_curation_picks([{"product_id": str(sold.id), "reason": "Coup de cœur"}])

    payload = await storefront_highlights(db=session, limit=2)
    # The sold curated pick is dropped ; padding fills the slot.
    assert [it["name"] for it in payload["items"]] == ["Backup"]
    assert payload["items"][0]["id"] == str(backup.id)


@pytest.mark.anyio
async def test_filters_out_sold_and_test_products(session):
    keep = await _make_floor_product(session, name="Keep", score=50)
    sold = await _make_floor_product(session, name="Sold", score=99)
    sold.status = ProductStatus.sold
    await _make_floor_product(session, name="Test", score=99, is_test=True)
    await session.flush()

    payload = await storefront_highlights(db=session, limit=4)
    names = {it["name"] for it in payload["items"]}
    assert names == {"Keep"}
    assert payload["items"][0]["id"] == str(keep.id)


@pytest.mark.anyio
async def test_payload_shape(session):
    p = await _make_floor_product(session, name="Robe noire", score=80, sale_price=49.50)
    p.brand = "Sandro"
    p.size = "M"
    p.color = "noir"
    p.storefront_photo_url = "/uploads/storefront/robe.jpg"
    await session.flush()

    payload = await storefront_highlights(db=session, limit=1)
    item = payload["items"][0]
    assert item["name"] == "Robe noire"
    assert item["brand"] == "Sandro"
    assert item["size"] == "M"
    assert item["color"] == "noir"
    assert item["sale_price"] == 49.50
    assert item["price_cents"] == 4950
    # storefront_photo_url preferred over photo_url for editorial consistency.
    assert item["photo_url"] == "/uploads/storefront/robe.jpg"
