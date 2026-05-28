"""Tests for the product-level gender field (creation + zone assignment).

Gender becomes a first-class Product attribute (proposed by image detection at
step 2 of the add wizard) and the BASIS for automatic zone assignment. These
tests prove:
  - the product gender overrides the category gender in suggest_zone;
  - when the product has no gender (existing rows), suggest_zone falls back to
    the category gender (so nothing regresses);
  - the router coerces/validates the incoming gender string.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.inventory.router import _coerce_gender
from app.models import Base
from app.models.product import Category, Gender, Product, ProductPhoto, ProductStatus
from app.models.store import FurnitureItem, StoreZone, ZoneProduct, ZoneTag
from app.models.user import User
from app.services.merchandising import MerchandisingService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Category.__table__,
        StoreZone.__table__,
        ZoneTag.__table__,
        ZoneProduct.__table__,
        FurnitureItem.__table__,
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


async def _zone(session, *, name, genders, priority) -> StoreZone:
    z = StoreZone(
        name=name, capacity=30, match_genders=genders,
        assignment_priority=priority, auto_assign=True, display_order=priority,
    )
    session.add(z)
    await session.flush()
    return z


async def _product(session, *, category_gender, product_gender) -> Product:
    cat = Category(name="Pulls", gender=category_gender)
    session.add(cat)
    await session.flush()
    p = Product(
        barcode=f"B-{uuid.uuid4().hex[:8]}",
        name="Pull",
        category_id=cat.id,
        status=ProductStatus.displayed,
        sale_price=20,
        purchase_price=5,
        gender=product_gender,
    )
    session.add(p)
    await session.flush()
    return p


# ---------------------------------------------------------------------------
# _coerce_gender (router validation)
# ---------------------------------------------------------------------------


def test_coerce_gender_valid_values():
    assert _coerce_gender("homme") == Gender.homme
    assert _coerce_gender("femme") == Gender.femme
    assert _coerce_gender("enfant") == Gender.enfant
    assert _coerce_gender("mixte") == Gender.mixte


def test_coerce_gender_empty_is_none():
    assert _coerce_gender(None) is None
    assert _coerce_gender("") is None


def test_coerce_gender_invalid_raises_400():
    with pytest.raises(HTTPException) as exc:
        _coerce_gender("alien")
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# suggest_zone uses the product gender as the basis
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_product_gender_overrides_category_for_zone(session):
    # Category says homme, but the operator/Vision tagged the product femme.
    await _zone(session, name="Zone Homme", genders=["homme"], priority=10)
    zone_femme = await _zone(session, name="Zone Femme", genders=["femme"], priority=20)
    product = await _product(
        session, category_gender=Gender.homme, product_gender=Gender.femme
    )

    suggestion = await MerchandisingService(session).suggest_zone(product)
    # Product gender (femme) wins → the femme zone is suggested.
    assert suggestion.primary_zone_id == str(zone_femme.id)


@pytest.mark.anyio
async def test_zone_falls_back_to_category_gender_when_product_has_none(session):
    zone_homme = await _zone(session, name="Zone Homme", genders=["homme"], priority=10)
    await _zone(session, name="Zone Femme", genders=["femme"], priority=20)
    # Existing-style row: no product gender → category gender (homme) is used.
    product = await _product(
        session, category_gender=Gender.homme, product_gender=None
    )

    suggestion = await MerchandisingService(session).suggest_zone(product)
    assert suggestion.primary_zone_id == str(zone_homme.id)
