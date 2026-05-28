"""Tests for the permanent (hard) delete of a wrongly-created product.

Drives the route coroutine directly on an in-memory aiosqlite session. The
``RoleChecker`` dependency is a FastAPI route concern (enforced over HTTP), so
calling the coroutine exercises the core logic: the fiscal guard (refuse when
the product was transacted) and the dependent-row cleanup + audited delete.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.inventory.router import permanently_delete_product
from app.core.audit_context import reset_current_user_id, set_current_user_id
from app.models import Base
from app.models.audit import AuditLog
from app.models.embeddings import ProductEmbedding
from app.models.events import EventLog
from app.models.inventory import Order, OrderItem, Supplier
from app.models.pos import Transaction, TransactionItem
from app.models.product import Category, Gender, Product, ProductPhoto, ProductStatus
from app.models.store import FurnitureItem, StoreZone, ZoneProduct, ZoneTag
from app.models.user import User
from app.services.audit import register_audit_listeners, unregister_audit_listeners


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Category.__table__,
        Product.__table__,
        ProductPhoto.__table__,
        ProductEmbedding.__table__,
        StoreZone.__table__,
        ZoneTag.__table__,
        FurnitureItem.__table__,
        ZoneProduct.__table__,
        Supplier.__table__,
        Order.__table__,
        OrderItem.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        EventLog.__table__,
        AuditLog.__table__,
    ]
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    register_audit_listeners()
    yield eng
    unregister_audit_listeners()
    await eng.dispose()


@pytest.fixture
async def session(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


@pytest.fixture(autouse=True)
def _reset_context():
    handle = set_current_user_id(None)
    yield
    reset_current_user_id(handle)


async def _make_product(session) -> Product:
    cat = Category(name="Robes", gender=Gender.femme)
    session.add(cat)
    await session.flush()
    p = Product(
        barcode=f"B-{uuid.uuid4().hex[:8]}",
        name="Doublon à supprimer",
        category_id=cat.id,
        status=ProductStatus.stock,
        sale_price=20,
        purchase_price=5,
    )
    session.add(p)
    await session.flush()
    return p


@pytest.mark.anyio
async def test_permanent_delete_removes_product_and_dependents(session):
    user = User(username=f"u-{uuid.uuid4().hex[:6]}", email=f"{uuid.uuid4().hex[:6]}@x.fr", password_hash="x")
    session.add(user)
    await session.flush()
    set_current_user_id(user.id)

    product = await _make_product(session)
    zone = StoreZone(name="Zone A", capacity=10)
    session.add(zone)
    await session.flush()
    session.add(ProductPhoto(product_id=product.id, url="http://x/p.jpg", order_index=0, is_primary=True))
    session.add(ZoneProduct(zone_id=zone.id, product_id=product.id))
    session.add(ProductEmbedding(product_id=product.id))
    await session.flush()
    pid = product.id

    resp = await permanently_delete_product(product_id=pid, db=session, current_user=user)
    assert resp["deleted"] is True
    assert resp["id"] == str(pid)

    # Product + all FK dependents are gone.
    assert (await session.execute(select(func.count()).select_from(Product).where(Product.id == pid))).scalar_one() == 0
    assert (await session.execute(select(func.count()).select_from(ProductPhoto).where(ProductPhoto.product_id == pid))).scalar_one() == 0
    assert (await session.execute(select(func.count()).select_from(ZoneProduct).where(ZoneProduct.product_id == pid))).scalar_one() == 0
    assert (await session.execute(select(func.count()).select_from(ProductEmbedding).where(ProductEmbedding.product_id == pid))).scalar_one() == 0

    # The deletion is recorded in the audit trail.
    audit = (
        await session.execute(
            select(AuditLog).where(AuditLog.entity == "product", AuditLog.action == "delete", AuditLog.entity_id == pid)
        )
    ).scalars().all()
    assert len(audit) == 1


@pytest.mark.anyio
async def test_permanent_delete_refused_when_transacted(session):
    product = await _make_product(session)
    # A sale line references this product → fiscal guard must refuse.
    session.add(
        TransactionItem(
            transaction_id=uuid.uuid4(),
            product_id=product.id,
            product_name="Doublon à supprimer",
            unit_price=20,
            line_total=20,
        )
    )
    await session.flush()

    with pytest.raises(HTTPException) as exc:
        await permanently_delete_product(product_id=product.id, db=session, current_user=None)
    assert exc.value.status_code == 409

    # Product is untouched.
    assert (
        await session.execute(select(func.count()).select_from(Product).where(Product.id == product.id))
    ).scalar_one() == 1
