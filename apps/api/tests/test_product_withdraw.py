"""Tests du retrait de vente : Retour centre de tri (returned) + Refuser (rejected).

Couvre l'endpoint withdraw (changement de statut + sortie du magasin) et le
fait que les pièces retournées/rejetées ne sont plus vendables au POS.
"""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.exceptions import ProductNotAvailable
from app.models import Base
from app.models.product import Category, Product, ProductStatus
from app.services.pos import PosService


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


async def _product(session, status=ProductStatus.displayed, zone_id=None):
    cat = Category(name="Robes")
    session.add(cat)
    await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}", name="Pièce",
        category_id=cat.id, sale_price=25.0, status=status, zone_id=zone_id,
    )
    session.add(p)
    await session.flush()
    return p


@pytest.mark.anyio
async def test_rejected_status_exists():
    assert ProductStatus.rejected.value == "rejected"


@pytest.mark.anyio
async def test_withdraw_returned_and_rejected(session):
    from app.api.inventory.router import WithdrawRequest, withdraw_product

    user = SimpleNamespace(id=uuid.uuid4())
    zone = uuid.uuid4()

    p1 = await _product(session, zone_id=zone)
    out1 = await withdraw_product(p1.id, WithdrawRequest(reason="returned"), session, user)
    assert out1["status"] == "returned"
    refreshed1 = (await session.execute(select(Product).where(Product.id == p1.id))).scalar_one()
    assert refreshed1.status == ProductStatus.returned
    assert refreshed1.zone_id is None  # retiré du magasin

    p2 = await _product(session, zone_id=zone)
    out2 = await withdraw_product(p2.id, WithdrawRequest(reason="rejected"), session, user)
    assert out2["status"] == "rejected"
    refreshed2 = (await session.execute(select(Product).where(Product.id == p2.id))).scalar_one()
    assert refreshed2.status == ProductStatus.rejected
    assert refreshed2.zone_id is None


@pytest.mark.anyio
async def test_withdraw_bad_reason_and_sold_guard(session):
    from fastapi import HTTPException

    from app.api.inventory.router import WithdrawRequest, withdraw_product

    user = SimpleNamespace(id=uuid.uuid4())

    p = await _product(session)
    with pytest.raises(HTTPException) as exc:
        await withdraw_product(p.id, WithdrawRequest(reason="banana"), session, user)
    assert exc.value.status_code == 400

    sold = await _product(session, status=ProductStatus.sold)
    with pytest.raises(HTTPException) as exc2:
        await withdraw_product(sold.id, WithdrawRequest(reason="returned"), session, user)
    assert exc2.value.status_code == 409


@pytest.mark.anyio
async def test_returned_and_rejected_not_sellable(session):
    user = uuid.uuid4()
    svc = PosService(session)

    for status in (ProductStatus.returned, ProductStatus.rejected):
        p = await _product(session, status=status)
        item = SimpleNamespace(
            product_id=p.id, name=None, quantity=1,
            unit_price=None, discount_percent=0,
        )
        with pytest.raises(ProductNotAvailable):
            await svc.create_transaction(
                user_id=user,
                items=[item],
                payments=[SimpleNamespace(method="cash", amount=25.0)],
            )
