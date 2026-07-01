"""Test de l'impact des remises dans le cahier journalier.

Vérifie compute_discounts_impact : réductions de ligne (soldes/opérations vs
manuelles) + bons affectés en paiement (chèque cadeau fidélité), et le taux de
remise sur le CA brut.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import Client, LoyaltyAccount
from app.models.coupon import Coupon, CouponDiscountType, CouponSource
from app.models.pos import (
    Payment,
    PaymentMethod,
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.services import cahier_service as svc


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


@pytest.mark.anyio
async def test_discounts_impact_breakdown(session):
    report_date = svc.today_paris()
    # Milieu de la journée Paris pour tomber dans la fenêtre quelle que soit
    # l'heure serveur.
    created = datetime.combine(
        report_date, datetime.min.time(), tzinfo=timezone.utc
    ) + timedelta(hours=12)

    client = Client(first_name="Test", last_name="Cliente")
    session.add(client)
    await session.flush()
    session.add(LoyaltyAccount(client_id=client.id, points=0, membership_number="V000777"))

    tx = Transaction(
        transaction_number=1,
        transaction_type=TransactionType.sale,
        user_id=uuid.uuid4(),
        client_id=client.id,
        total_ht=30.83,
        total_tva=6.17,
        total_ttc=37.0,
        hash_chain="",
        created_at=created,
    )
    session.add(tx)
    await session.flush()

    # Ligne en solde : 20 € → -50 % → 10 € (réduction opération 10 €).
    session.add(TransactionItem(
        transaction_id=tx.id, product_name="Robe soldée", quantity=1,
        unit_price=20.0, discount_percent=50.0, line_total=10.0, promotional=True,
    ))
    # Ligne remise manuelle : 30 € → -10 % → 27 € (réduction manuelle 3 €).
    session.add(TransactionItem(
        transaction_id=tx.id, product_name="Pull", quantity=1,
        unit_price=30.0, discount_percent=10.0, line_total=27.0, promotional=False,
    ))
    # Chèque cadeau fidélité affecté au paiement : 5 €.
    session.add(Payment(
        transaction_id=tx.id, method=PaymentMethod.voucher, amount=5.0,
    ))
    session.add(Payment(
        transaction_id=tx.id, method=PaymentMethod.cash, amount=32.0,
    ))
    coupon = Coupon(
        code="LOYAL-ABC123",
        client_id=client.id,
        discount_type=CouponDiscountType.amount,
        discount_value=5.0,
        source=CouponSource.loyalty_milestone,
        valid_from=created - timedelta(days=1),
        valid_until=created + timedelta(days=30),
        is_active=True,
        redeemed_at=created,
        redeemed_transaction_id=tx.id,
    )
    session.add(coupon)
    await session.flush()

    impact = await svc.compute_discounts_impact(session, report_date)

    assert impact["remises_soldes_operations"] == pytest.approx(10.0)
    assert impact["remises_manuelles"] == pytest.approx(3.0)
    assert impact["total_remises_caisse"] == pytest.approx(13.0)
    assert impact["avantage_fidelite"] == pytest.approx(5.0)
    assert impact["bons_evenementiels"] == pytest.approx(0.0)
    assert impact["total_avantages"] == pytest.approx(18.0)
    # CA net 37 + remises caisse 13 = CA brut 50 → taux 26 %.
    assert impact["ca_brut"] == pytest.approx(50.0)
    assert impact["taux_remise_pct"] == pytest.approx(26.0)


@pytest.mark.anyio
async def test_discounts_impact_empty_day(session):
    impact = await svc.compute_discounts_impact(session, svc.today_paris())
    assert impact["total_remises_caisse"] == 0.0
    assert impact["total_avantages"] == 0.0
    assert impact["taux_remise_pct"] == 0.0
