"""End-to-end (service level) for the loyalty gift-cheque feature.

Proves the FULL chain that the POS router runs (create_transaction ->
finalize_sale) actually:
  1. credits loyalty points (1 € = 1 pt);
  2. auto-generates a « chèque cadeau » Coupon (source=loyalty_milestone) when
     crossing a 100-pt milestone, with the configured value + validity;
  3. lets that gift cheque be used as a PaymentMethod.voucher on a later sale
     (validated + redeemed).
"""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import Client, LoyaltyAccount
from app.models.coupon import Coupon, CouponSource
from app.models.product import Category, Product, ProductStatus
from app.models.user import User, UserRole
from app.services.loyalty_config import get_earning_config
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
    u = User(username="mgr", email="m@v.fr", password_hash="x" * 60,
             role=UserRole.manager, is_active=True)
    session.add(u)
    await session.flush()
    return u


async def _product(session, price):
    cat = Category(name=f"Cat-{uuid.uuid4().hex[:4]}")
    session.add(cat)
    await session.flush()
    p = Product(barcode=f"P-{uuid.uuid4().hex[:8]}", name="Pièce",
                category_id=cat.id, sale_price=price, status=ProductStatus.display)
    session.add(p)
    await session.flush()
    return p


def _ci(product, qty=1):
    return SimpleNamespace(product_id=product.id, name=None, quantity=qty,
                           unit_price=float(product.sale_price), discount_percent=0)


def _pay(method, amount, voucher_code=None):
    return SimpleNamespace(method=method, amount=amount, voucher_code=voucher_code)


@pytest.mark.anyio
async def test_giftcheque_generated_then_used_as_payment(session):
    user = await _user(session)
    client = Client(first_name="Léa", last_name="M", email="lea@x.fr")
    session.add(client)
    await session.flush()

    cfg = await get_earning_config(session)
    svc = PosService(session)

    # --- SALE 1: 100 € -> +100 pts -> crosses the 100-pt milestone ---
    p100 = await _product(session, 100.0)
    tx1 = await svc.create_transaction(
        user_id=user.id, items=[_ci(p100)],
        payments=[_pay("cash", 100.0)], client_id=client.id,
    )
    # finalize_sale is what the router calls post-signature — it credits loyalty.
    await svc.finalize_sale(tx1, coupon_code=None, user_id=user.id)

    acct = (await session.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.client_id == client.id)
    )).scalar_one()
    assert acct.points == 100  # 1 € = 1 pt, décompte actif

    cheques = (await session.execute(
        select(Coupon).where(
            Coupon.client_id == client.id,
            Coupon.source == CouponSource.loyalty_milestone,
        )
    )).scalars().all()
    assert len(cheques) == 1
    cheque = cheques[0]
    assert float(cheque.discount_value) == pytest.approx(cfg.voucher_value_cents / 100.0)
    # voucher_valid_days == 0 (défaut) → chèque cadeau SANS expiration.
    if cfg.voucher_valid_days == 0:
        assert cheque.valid_until is None
    else:
        assert (cheque.valid_until - cheque.valid_from).days == cfg.voucher_valid_days
    assert cheque.redeemed_at is None  # not yet used

    # --- POS visibility: the cheque shows in the client's voucher list with
    # the affectable value the caisse chip renders ("Affecter 5,00 €"). This is
    # exactly what GET /pos/clients/{id}/vouchers returns to the POS. ---
    from app.services.coupon import compute_voucher_discount
    from app.services.event_vouchers import list_client_vouchers

    active = await list_client_vouchers(session, client.id, only_active=True)
    assert any(v.code == cheque.code for v in active), "gift cheque not usable in POS"
    # 20 € cart → the whole 5 € cheque is affectable.
    assert compute_voucher_discount(cheque, 20.0) == pytest.approx(5.0)

    # --- SALE 2: 20 € paid with the gift cheque (value) + cash remainder ---
    value = float(cheque.discount_value)
    p20 = await _product(session, 20.0)
    tx2 = await svc.create_transaction(
        user_id=user.id, items=[_ci(p20)],
        payments=[
            _pay("voucher", value, voucher_code=cheque.code),
            _pay("cash", 20.0 - value),
        ],
        client_id=client.id,
    )
    assert tx2 is not None

    # The gift cheque is now redeemed (consumed), linked to sale 2.
    await session.refresh(cheque)
    assert cheque.redeemed_at is not None


@pytest.mark.anyio
async def test_multiple_milestones_in_one_sale(session):
    """A single big sale crossing 200 pts issues TWO gift cheques."""
    user = await _user(session)
    client = Client(first_name="A", last_name="B", email="ab@x.fr")
    session.add(client)
    await session.flush()

    svc = PosService(session)
    p = await _product(session, 250.0)
    tx = await svc.create_transaction(
        user_id=user.id, items=[_ci(p)],
        payments=[_pay("cash", 250.0)], client_id=client.id,
    )
    await svc.finalize_sale(tx, coupon_code=None, user_id=user.id)

    acct = (await session.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.client_id == client.id)
    )).scalar_one()
    assert acct.points == 250
    cheques = (await session.execute(
        select(Coupon).where(
            Coupon.client_id == client.id,
            Coupon.source == CouponSource.loyalty_milestone,
        )
    )).scalars().all()
    assert len(cheques) == 2  # crossed 100 and 200
