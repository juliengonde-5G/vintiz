"""Tests for the multi-photo service (P1-008).

Verifies the service maintains the three invariants on every mutation:
1. Exactly one ProductPhoto per product has is_primary=True (or zero if no
   photos exist).
2. order_index is contiguous (0..N-1).
3. Product.photo_url mirrors the primary photo's URL.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.services.photo import PhotoService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(
                c,
                tables=[
                    Category.__table__,
                    Product.__table__,
                    ProductPhoto.__table__,
                ],
            )
        )
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


async def _make_product(session: AsyncSession, photo_url: str | None = None) -> Product:
    cat = Category(name="Robes")
    session.add(cat)
    await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name="Robe",
        category_id=cat.id,
        sale_price=49.0,
        status=ProductStatus.stock,
        photo_url=photo_url,
    )
    session.add(p)
    await session.flush()
    return p


def _assert_invariants(photos: list[dict], product: Product) -> None:
    """Common invariant assertions."""
    if not photos:
        assert product.photo_url is None
        return
    primaries = [p for p in photos if p["is_primary"]]
    assert len(primaries) == 1, f"Expected exactly one primary, got {len(primaries)}"
    assert product.photo_url == primaries[0]["url"]
    indices = sorted(p["order_index"] for p in photos)
    assert indices == list(range(len(photos))), f"order not contiguous: {indices}"


# ---------------------------------------------------------------------------
# add_photo
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_first_photo_becomes_primary_and_sets_product_photo_url(session):
    p = await _make_product(session)
    svc = PhotoService(session)

    await svc.add_photo(p.id, "https://cdn/a.jpg")
    photos = await svc.list_photos(p.id)

    assert len(photos) == 1
    assert photos[0]["is_primary"] is True
    assert photos[0]["order_index"] == 0
    await session.refresh(p)
    assert p.photo_url == "https://cdn/a.jpg"
    _assert_invariants(photos, p)


@pytest.mark.anyio
async def test_second_photo_does_not_replace_primary(session):
    p = await _make_product(session)
    svc = PhotoService(session)

    await svc.add_photo(p.id, "https://cdn/a.jpg")
    await svc.add_photo(p.id, "https://cdn/b.jpg")
    photos = await svc.list_photos(p.id)

    assert [ph["url"] for ph in photos] == ["https://cdn/a.jpg", "https://cdn/b.jpg"]
    assert photos[0]["is_primary"] is True
    assert photos[1]["is_primary"] is False
    await session.refresh(p)
    _assert_invariants(photos, p)


@pytest.mark.anyio
async def test_empty_url_rejected(session):
    from fastapi import HTTPException

    p = await _make_product(session)
    with pytest.raises(HTTPException) as exc:
        await PhotoService(session).add_photo(p.id, "   ")
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_add_photo_unknown_product_404(session):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await PhotoService(session).add_photo(uuid.uuid4(), "https://x")
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# set_primary
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_set_primary_promotes_photo_and_remaps_indices(session):
    p = await _make_product(session)
    svc = PhotoService(session)
    await svc.add_photo(p.id, "https://cdn/a.jpg")
    await svc.add_photo(p.id, "https://cdn/b.jpg")
    c = await svc.add_photo(p.id, "https://cdn/c.jpg")

    await svc.set_primary(p.id, c.id)
    photos = await svc.list_photos(p.id)

    # c is now first; a and b follow in their previous relative order
    assert photos[0]["url"] == "https://cdn/c.jpg"
    assert photos[0]["is_primary"] is True
    assert {photos[1]["url"], photos[2]["url"]} == {
        "https://cdn/a.jpg",
        "https://cdn/b.jpg",
    }
    await session.refresh(p)
    assert p.photo_url == "https://cdn/c.jpg"
    _assert_invariants(photos, p)


@pytest.mark.anyio
async def test_set_primary_unknown_photo_404(session):
    from fastapi import HTTPException

    p = await _make_product(session)
    with pytest.raises(HTTPException) as exc:
        await PhotoService(session).set_primary(p.id, uuid.uuid4())
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# delete_photo
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_deleting_primary_promotes_next_one(session):
    p = await _make_product(session)
    svc = PhotoService(session)
    a = await svc.add_photo(p.id, "https://cdn/a.jpg")
    await svc.add_photo(p.id, "https://cdn/b.jpg")

    await svc.delete_photo(p.id, a.id)
    photos = await svc.list_photos(p.id)

    assert len(photos) == 1
    assert photos[0]["url"] == "https://cdn/b.jpg"
    assert photos[0]["is_primary"] is True
    await session.refresh(p)
    assert p.photo_url == "https://cdn/b.jpg"
    _assert_invariants(photos, p)


@pytest.mark.anyio
async def test_deleting_last_photo_clears_product_photo_url(session):
    p = await _make_product(session, photo_url="https://cdn/legacy.jpg")
    svc = PhotoService(session)
    a = await svc.add_photo(p.id, "https://cdn/a.jpg")

    await svc.delete_photo(p.id, a.id)
    photos = await svc.list_photos(p.id)

    assert photos == []
    await session.refresh(p)
    assert p.photo_url is None
    _assert_invariants(photos, p)


# ---------------------------------------------------------------------------
# reorder
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_reorder_applies_new_order_and_updates_primary(session):
    p = await _make_product(session)
    svc = PhotoService(session)
    a = await svc.add_photo(p.id, "https://cdn/a.jpg")
    b = await svc.add_photo(p.id, "https://cdn/b.jpg")
    c = await svc.add_photo(p.id, "https://cdn/c.jpg")

    photos = await svc.reorder(p.id, [b.id, c.id, a.id])

    urls = [ph["url"] for ph in photos]
    assert urls == ["https://cdn/b.jpg", "https://cdn/c.jpg", "https://cdn/a.jpg"]
    assert photos[0]["is_primary"] is True
    await session.refresh(p)
    assert p.photo_url == "https://cdn/b.jpg"
    _assert_invariants(photos, p)


@pytest.mark.anyio
async def test_reorder_with_wrong_ids_rejected(session):
    from fastapi import HTTPException

    p = await _make_product(session)
    svc = PhotoService(session)
    a = await svc.add_photo(p.id, "https://cdn/a.jpg")
    await svc.add_photo(p.id, "https://cdn/b.jpg")

    # Missing one id
    with pytest.raises(HTTPException) as exc:
        await svc.reorder(p.id, [a.id])
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# AI fields are persisted
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ai_fields_persist(session):
    from datetime import datetime, timezone

    p = await _make_product(session)
    now = datetime(2026, 4, 26, 10, 0, 0, tzinfo=timezone.utc)
    photo = await PhotoService(session).add_photo(
        p.id, "https://cdn/x.jpg", ai_analyzed_at=now, ai_confidence=0.92
    )
    # SQLite drops tzinfo; assert on the naive equivalent.
    assert photo.ai_analyzed_at.replace(tzinfo=None) == now.replace(tzinfo=None)
    assert photo.ai_confidence == 0.92


# ---------------------------------------------------------------------------
# Storefront (background-removed) copy mirroring
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_add_photo_mirrors_processed_url_to_product(session):
    p = await _make_product(session)
    svc = PhotoService(session)

    photo = await svc.add_photo(
        p.id,
        "https://cdn/a.jpg",
        processed_url="https://cdn/a_storefront.png",
        processing_status="done",
    )
    assert photo.processed_url == "https://cdn/a_storefront.png"
    assert photo.processing_status == "done"
    await session.refresh(p)
    assert p.storefront_photo_url == "https://cdn/a_storefront.png"

    serialized = (await svc.list_photos(p.id))[0]
    assert serialized["processed_url"] == "https://cdn/a_storefront.png"
    assert serialized["processing_status"] == "done"


@pytest.mark.anyio
async def test_set_processed_updates_and_mirrors(session):
    p = await _make_product(session)
    svc = PhotoService(session)
    a = await svc.add_photo(p.id, "https://cdn/a.jpg", processing_status="skipped")
    await session.refresh(p)
    assert p.storefront_photo_url is None

    await svc.set_processed(p.id, a.id, "https://cdn/a_storefront.png", "done")
    await session.refresh(p)
    assert p.storefront_photo_url == "https://cdn/a_storefront.png"


@pytest.mark.anyio
async def test_storefront_url_follows_primary(session):
    p = await _make_product(session)
    svc = PhotoService(session)
    await svc.add_photo(
        p.id, "https://cdn/a.jpg", processed_url="https://cdn/a_sf.png", processing_status="done"
    )
    b = await svc.add_photo(
        p.id, "https://cdn/b.jpg", processed_url="https://cdn/b_sf.png", processing_status="done"
    )
    await session.refresh(p)
    assert p.storefront_photo_url == "https://cdn/a_sf.png"

    # Promote b → primary; storefront mirror must follow.
    await svc.set_primary(p.id, b.id)
    await session.refresh(p)
    assert p.storefront_photo_url == "https://cdn/b_sf.png"

    # Delete the (now primary) b → falls back to a's storefront copy.
    await svc.delete_photo(p.id, b.id)
    await session.refresh(p)
    assert p.storefront_photo_url == "https://cdn/a_sf.png"
