"""Prix de vente manuel au POS (bouton € — prix rond).

Règles couvertes :
- prix manuel < étiquette : le prix étiquette reste ``unit_price`` et l'écart
  (unit_price × qté − line_total) entre dans les remises du jour ;
- prix manuel > étiquette : ``unit_price`` devient le prix manuel (pas de
  remise négative dans les rapports) ;
- jamais de points de fidélité sur une ligne à prix manuel (promotional) ;
- historisation dans la fiche produit (audit_logs, action pos.price_override) ;
- un prix manuel est un prix ferme : exclu de la remise Solde ;
- un prix manuel non rond est refusé.
"""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.exceptions import InvalidOperation
from app.models import Base
from app.models.audit import AuditLog
from app.models.client import Client, LoyaltyAccount
from app.models.offer import Offer, OfferType
from app.models.pos import TransactionItem
from app.models.product import Category, Product, ProductStatus
from app.models.user import User, UserRole
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


async def _user(session):
    u = User(
        username="cashier", email="c@vintiz.fr",
        password_hash="x" * 60, role=UserRole.manager, is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


async def _product(session, price, status=ProductStatus.display):
    cat = Category(name=f"Cat-{uuid.uuid4().hex[:6]}")
    session.add(cat)
    await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}", name="Pièce",
        category_id=cat.id, sale_price=price, status=status,
    )
    session.add(p)
    await session.flush()
    return p


def _ci(product, qty=1, discount=0, manual_price=None):
    return SimpleNamespace(
        product_id=product.id, name=None, quantity=qty,
        unit_price=float(product.sale_price), discount_percent=discount,
        manual_unit_price=manual_price,
    )


def _pay(method, amount):
    return SimpleNamespace(method=method, amount=amount)


async def _items_of(session, tx):
    return (
        await session.execute(
            select(TransactionItem).where(TransactionItem.transaction_id == tx.id)
        )
    ).scalars().all()


@pytest.mark.anyio
async def test_manual_price_below_label(session):
    user = await _user(session)
    product = await _product(session, 23.0)

    svc = PosService(session)
    tx = await svc.create_transaction(
        user_id=user.id,
        items=[_ci(product, manual_price=20)],
        payments=[_pay("cash", 20.0)],
    )
    assert float(tx.total_ttc) == pytest.approx(20.0)

    (item,) = await _items_of(session, tx)
    # Le prix étiquette reste sur la ligne → l'écart de 3 € compte dans les
    # remises du jour (unit_price × qté − line_total).
    assert float(item.unit_price) == pytest.approx(23.0)
    assert float(item.line_total) == pytest.approx(20.0)
    assert item.promotional is True

    # Historisation dans la fiche produit.
    logs = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.entity == "product",
                AuditLog.entity_id == product.id,
                AuditLog.action == "pos.price_override",
            )
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].data["label_price"] == pytest.approx(23.0)
    assert logs[0].data["manual_price"] == pytest.approx(20.0)
    assert logs[0].data["difference"] == pytest.approx(3.0)
    assert logs[0].data["transaction_number"] == tx.transaction_number


@pytest.mark.anyio
async def test_manual_price_above_label(session):
    user = await _user(session)
    product = await _product(session, 23.0)

    svc = PosService(session)
    tx = await svc.create_transaction(
        user_id=user.id,
        items=[_ci(product, manual_price=30)],
        payments=[_pay("cash", 30.0)],
    )
    assert float(tx.total_ttc) == pytest.approx(30.0)

    (item,) = await _items_of(session, tx)
    # Pas de « remise négative » : le prix manuel devient le prix de ligne.
    assert float(item.unit_price) == pytest.approx(30.0)
    assert float(item.discount_percent) == pytest.approx(0.0)
    assert float(item.line_total) == pytest.approx(30.0)
    # Mais toujours pas de points de fidélité.
    assert item.promotional is True


@pytest.mark.anyio
async def test_manual_price_earns_no_loyalty_points(session):
    user = await _user(session)
    client = Client(first_name="Léa", last_name="M", email="lea@x.fr")
    session.add(client)
    await session.flush()
    session.add(
        LoyaltyAccount(client_id=client.id, points=0, membership_number="V000321")
    )
    await session.flush()

    product = await _product(session, 60.0)
    svc = PosService(session)
    tx = await svc.create_transaction(
        user_id=user.id,
        items=[_ci(product, manual_price=50)],
        payments=[_pay("cash", 50.0)],
        client_id=client.id,
    )
    await svc._credit_loyalty_and_emit_milestones(tx)

    acct = (
        await session.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.client_id == client.id)
        )
    ).scalar_one()
    assert acct.points == 0


@pytest.mark.anyio
async def test_manual_price_excluded_from_solde(session):
    user = await _user(session)
    offer = Offer(name="Soldes", type=OfferType.solde, active=True, config={})
    session.add(offer)
    await session.flush()

    # Paire éligible Solde : sans prix manuel, la moins chère prendrait -30 %.
    cheap = await _product(session, 10.0)
    dear = await _product(session, 40.0)

    svc = PosService(session)
    tx = await svc.create_transaction(
        user_id=user.id,
        # La pièce la moins chère passe à prix manuel 8 € → exclue du Solde ;
        # il ne reste qu'une pièce éligible → pas de paire → pas de remise.
        items=[_ci(cheap, manual_price=8), _ci(dear)],
        payments=[_pay("cash", 48.0)],
    )
    assert float(tx.total_ttc) == pytest.approx(8.0 + 40.0)

    items = await _items_of(session, tx)
    by_total = {round(float(i.line_total), 2): i for i in items}
    assert by_total[8.0].promotional is True      # prix manuel
    assert by_total[40.0].promotional is False    # plein tarif, pas de solde


@pytest.mark.anyio
async def test_manual_price_must_be_round(session):
    user = await _user(session)
    product = await _product(session, 23.0)
    svc = PosService(session)
    with pytest.raises(InvalidOperation):
        await svc.create_transaction(
            user_id=user.id,
            items=[_ci(product, manual_price=19.9)],
            payments=[_pay("cash", 19.9)],
        )
