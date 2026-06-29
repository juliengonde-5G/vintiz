"""Tests Solde (remise multi-articles) + cagnotte fidélité (chèque cadeau).

Couvre :
- la règle Solde par paquets (6 → 3 moins chers à -50 %, paires → -30 %) ;
- l'application en caisse (remise + flag promotionnel + total) ;
- la fidélité : articles promo ne cotisent pas de points ;
- la génération automatique du chèque cadeau de 5 € au palier 100 pts
  (régression : NameError ``LOYALTY_VOUCHER_VALUE`` qui empêchait l'émission).
"""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import Client, LoyaltyAccount
from app.models.coupon import Coupon, CouponDiscountType, CouponSource
from app.models.offer import Offer, OfferType
from app.models.pos import TransactionItem
from app.models.product import Category, Product, ProductStatus
from app.models.user import User, UserRole
from app.services.pos import PosService
from app.services.solde_engine import compute_solde_rates


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


# ---------------------------------------------------------------------------
# Règle Solde — fonction pure
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_solde_rates_matches_examples():
    # 2 → 1 moins chère à -30 %
    assert sorted(compute_solde_rates([10, 20])) == [0.0, 30.0]
    # 3 → 1 moins chère à -30 %
    assert sorted(compute_solde_rates([10, 20, 30])) == [0.0, 0.0, 30.0]
    # 4 → 2 moins chères à -30 %
    assert sorted(compute_solde_rates([10, 20, 30, 40])) == [0.0, 0.0, 30.0, 30.0]
    # 6 → 3 moins chères à -50 %
    assert sorted(compute_solde_rates([10, 20, 30, 40, 50, 60])) == [
        0.0, 0.0, 0.0, 50.0, 50.0, 50.0,
    ]
    # 8 → 3 moins chères à -50 % + 1 à -30 %
    r8 = sorted(compute_solde_rates([10, 20, 30, 40, 50, 60, 70, 80]))
    assert r8 == [0.0, 0.0, 0.0, 0.0, 30.0, 50.0, 50.0, 50.0]
    # 12 → 6 moins chères à -50 %
    r12 = compute_solde_rates(list(range(1, 13)))
    assert r12.count(50.0) == 6 and r12.count(30.0) == 0


@pytest.mark.anyio
async def test_solde_targets_cheapest_first():
    # Les pièces les moins chères reçoivent le meilleur taux (-50 %).
    rates = compute_solde_rates([100, 5, 50, 10, 80, 7])  # n=6 → 3 cheapest @50
    by_price = sorted(zip([100, 5, 50, 10, 80, 7], rates))
    # 5, 7, 10 → 50 % ; 50, 80, 100 → 0
    assert [r for _, r in by_price] == [50.0, 50.0, 50.0, 0.0, 0.0, 0.0]


@pytest.mark.anyio
async def test_solde_single_item_no_discount():
    assert compute_solde_rates([42.0]) == [0.0]
    assert compute_solde_rates([]) == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _user(session):
    u = User(
        username="cashier", email="c@vintiz.fr",
        password_hash="x" * 60, role=UserRole.manager, is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


async def _product(session, price, status=ProductStatus.display):
    cat = Category(name="Robes")
    session.add(cat)
    await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}", name="Pièce",
        category_id=cat.id, sale_price=price, status=status,
    )
    session.add(p)
    await session.flush()
    return p


def _ci(product, qty=1, discount=0):
    return SimpleNamespace(
        product_id=product.id, name=None, quantity=qty,
        unit_price=float(product.sale_price), discount_percent=discount,
    )


def _pay(method, amount):
    return SimpleNamespace(method=method, amount=amount)


async def _active_solde(session):
    offer = Offer(name="Soldes d'été", type=OfferType.solde, active=True, config={})
    session.add(offer)
    await session.flush()
    return offer


# ---------------------------------------------------------------------------
# Application Solde en caisse
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_transaction_applies_solde(session):
    user = await _user(session)
    await _active_solde(session)
    prices = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]  # n=6 → 3 cheapest @50%
    products = [await _product(session, p) for p in prices]

    # Total attendu : 10*.5 + 20*.5 + 30*.5 + 40 + 50 + 60 = 30 + 150 = 180
    svc = PosService(session)
    tx = await svc.create_transaction(
        user_id=user.id,
        items=[_ci(p) for p in products],
        payments=[_pay("cash", 180.0)],
    )
    assert float(tx.total_ttc) == pytest.approx(180.0)

    items = (
        await session.execute(
            select(TransactionItem).where(TransactionItem.transaction_id == tx.id)
        )
    ).scalars().all()
    promo = [i for i in items if i.promotional]
    assert len(promo) == 3
    # Les 3 pièces remisées sont les 3 moins chères (10/20/30) à -50 %.
    for it in promo:
        assert float(it.discount_percent) == pytest.approx(50.0)
        assert float(it.unit_price) in (10.0, 20.0, 30.0)


@pytest.mark.anyio
async def test_no_solde_no_discount(session):
    user = await _user(session)
    # Pas d'opération Solde active.
    products = [await _product(session, p) for p in (10.0, 20.0)]
    svc = PosService(session)
    tx = await svc.create_transaction(
        user_id=user.id,
        items=[_ci(p) for p in products],
        payments=[_pay("cash", 30.0)],
    )
    assert float(tx.total_ttc) == pytest.approx(30.0)
    items = (
        await session.execute(
            select(TransactionItem).where(TransactionItem.transaction_id == tx.id)
        )
    ).scalars().all()
    assert all(not i.promotional for i in items)


# ---------------------------------------------------------------------------
# Cagnotte fidélité — chèque cadeau 5 € + exclusion promo
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_loyalty_voucher_generated_and_promo_excluded(session):
    user = await _user(session)
    client = Client(first_name="Léa", last_name="M", email="lea@x.fr")
    session.add(client)
    await session.flush()
    # Cliente à 50 pts.
    session.add(LoyaltyAccount(client_id=client.id, points=50, membership_number="V000123"))
    await session.flush()

    # Article plein 60 € + article démarqué (promotionnel) 50 €.
    full = await _product(session, 60.0)
    marked = await _product(session, 50.0, status=ProductStatus.discounted)

    svc = PosService(session)
    tx = await svc.create_transaction(
        user_id=user.id,
        items=[_ci(full), _ci(marked)],
        payments=[_pay("cash", 110.0)],
        client_id=client.id,
    )
    # Le markdown ne réduit pas le prix ici (déjà dans sale_price) mais marque
    # la ligne promotionnelle → exclue des points.
    items = (
        await session.execute(
            select(TransactionItem).where(TransactionItem.transaction_id == tx.id)
        )
    ).scalars().all()
    assert {i.promotional for i in items} == {True, False}

    # Créditer la fidélité (ce que fait finalize_sale après signature).
    await svc._credit_loyalty_and_emit_milestones(tx)

    acct = (
        await session.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.client_id == client.id)
        )
    ).scalar_one()
    # Seuls les 60 € non promo cotisent → +60 pts → 110 pts (franchit 100).
    assert acct.points == 110

    # Un chèque cadeau fidélité de 5 € a été généré (régression NameError).
    coupons = (
        await session.execute(
            select(Coupon).where(
                Coupon.client_id == client.id,
                Coupon.source == CouponSource.loyalty_milestone,
            )
        )
    ).scalars().all()
    assert len(coupons) == 1
    assert float(coupons[0].discount_value) == pytest.approx(5.0)
    assert coupons[0].discount_type == CouponDiscountType.amount
