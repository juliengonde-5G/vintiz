"""Tests for event-opening gift vouchers (bons cadeau d'ouverture).

Couvre le catalogue + l'émission (crédit sur fiche client), le calcul de la
valeur (montant / pourcentage / article offert) et surtout le **débit comme
moyen de paiement** : le bon devient une ligne de règlement (PaymentMethod.voucher)
au sein de PosService.create_transaction.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.exceptions import InvalidOperation
from app.models import Base
from app.models.audit import Settings
from app.models.client import (
    AvoirTransaction,
    Client,
    Consent,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.coupon import Coupon, CouponDiscountType, CouponSource
from app.models.offer import Offer
from app.models.pos import Payment, PaymentMethod, Receipt, Transaction, TransactionItem
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.user import User, UserRole
from app.services import event_vouchers as ev
from app.services.coupon import compute_voucher_discount
from app.services.pos import PosService


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
        Client.__table__,
        Consent.__table__,
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        AvoirTransaction.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        Payment.__table__,
        Receipt.__table__,
        Coupon.__table__,
        Settings.__table__,
        Offer.__table__,
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


async def _client(session) -> Client:
    c = Client(first_name="Marie", last_name="Durand", email=f"{uuid.uuid4().hex[:6]}@x.fr")
    session.add(c)
    await session.flush()
    return c


async def _user(session) -> User:
    u = User(username=f"u{uuid.uuid4().hex[:6]}", email=f"{uuid.uuid4().hex[:6]}@x.fr",
             password_hash="x" * 60, role=UserRole.collaborateur, is_active=True)
    session.add(u)
    await session.flush()
    return u


async def _product(session, *, name="Robe", price=10.0, category_name="Robes") -> Product:
    cat = Category(name=category_name)
    session.add(cat)
    await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}", name=name, category_id=cat.id,
        sale_price=price, status=ProductStatus.display,
    )
    session.add(p)
    await session.flush()
    return p


def _cart_item(product, qty=1):
    return SimpleNamespace(
        product_id=product.id, name=None, quantity=qty,
        unit_price=float(product.sale_price), discount_percent=0,
    )


# ---------------------------------------------------------------------------
# Catalogue + émission
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_catalog_has_required_defaults(session):
    catalog = await ev.get_catalog(session)
    keys = {v["key"] for v in catalog}
    # Catalogue par défaut : « prochains achats » + « immédiats »
    assert {
        "bon_1e", "remise_5", "remise_10", "remise_15", "foulard",
        "imm_1e", "imm_2e", "imm_remise_10", "imm_foulard",
    } <= keys
    foulard = next(v for v in catalog if v["key"] == "foulard")
    assert foulard["discount_type"] == "free_item"
    assert foulard["free_item_label"] == "foulard"
    # Les entrées immédiates portent la flag
    assert next(v for v in catalog if v["key"] == "imm_1e")["immediate"] is True
    assert next(v for v in catalog if v["key"] == "bon_1e")["immediate"] is False


@pytest.mark.anyio
async def test_issue_voucher_credits_client(session):
    client = await _client(session)
    coupon = await ev.issue_voucher(session, client_id=client.id, type_key="bon_1e")
    assert coupon.source == CouponSource.event_opening
    assert coupon.discount_type == CouponDiscountType.amount
    assert float(coupon.discount_value) == 1.0
    assert coupon.client_id == client.id
    assert coupon.code.startswith("BON-")

    active = await ev.list_client_vouchers(session, client.id)
    assert len(active) == 1 and active[0].code == coupon.code


@pytest.mark.anyio
async def test_issue_unknown_type_raises(session):
    from app.services.coupon import CouponError

    client = await _client(session)
    with pytest.raises(CouponError):
        await ev.issue_voucher(session, client_id=client.id, type_key="nope")


@pytest.mark.anyio
async def test_issue_voucher_rejects_duplicate_for_same_client(session):
    """1 bon d'ouverture par personne — interdiction d'en émettre un 2e."""
    from app.services.coupon import CouponError

    client = await _client(session)
    await ev.issue_voucher(session, client_id=client.id, type_key="bon_1e")
    with pytest.raises(CouponError) as exc:
        await ev.issue_voucher(session, client_id=client.id, type_key="bon_1e")
    assert str(exc.value) == "already_issued"


@pytest.mark.anyio
async def test_voucher_redeem_rejected_on_issuance_day(session):
    """Bon d'ouverture utilisé le jour même = refusé (utilisable dès demain)."""
    from app.services.coupon import CouponError, validate_coupon

    client = await _client(session)
    coupon = await ev.issue_voucher(session, client_id=client.id, type_key="bon_1e")
    # Ne pas back-dater : created_at = aujourd'hui.
    with pytest.raises(CouponError) as exc:
        await validate_coupon(
            session, code=coupon.code, cart_total=10.0, client_id=client.id,
        )
    assert str(exc.value) == "same_day"


# ---------------------------------------------------------------------------
# Valeur (compute_voucher_discount)
# ---------------------------------------------------------------------------


def test_compute_discount_amount_percent_free_item():
    amount = Coupon(discount_type=CouponDiscountType.amount, discount_value=2.0)
    assert compute_voucher_discount(amount, 10.0) == 2.0
    assert compute_voucher_discount(amount, 1.5) == 1.5  # capped at cart

    pct = Coupon(discount_type=CouponDiscountType.percent, discount_value=10.0)
    assert compute_voucher_discount(pct, 50.0) == 5.0

    scarf = Coupon(
        discount_type=CouponDiscountType.free_item, discount_value=15.0,
        free_item_label="foulard",
    )
    # No cart context → preview = cap.
    assert compute_voucher_discount(scarf, 100.0) == 15.0
    # Eligible item present → covers cheapest matching item (capped).
    items = [{"price": 8.0, "text": "foulard soie accessoires"}, {"price": 30.0, "text": "robe"}]
    assert compute_voucher_discount(scarf, 38.0, items) == 8.0
    # Cart but no eligible item → 0 (can't apply yet).
    assert compute_voucher_discount(scarf, 30.0, [{"price": 30.0, "text": "robe"}]) == 0.0


# ---------------------------------------------------------------------------
# Débit comme moyen de paiement (PosService.create_transaction)
# ---------------------------------------------------------------------------


async def _backdate_voucher(session, coupon, *, days: int = 1) -> None:
    """Bons d'ouverture : interdiction d'utilisation le jour de l'émission.

    Les tests de redeem ont besoin d'un bon ancien d'au moins 1 jour pour
    franchir la règle ``same_day``. On rejoue ``created_at`` à J-N pour
    isoler le test du calendrier réel."""
    coupon.created_at = datetime.now(timezone.utc) - timedelta(days=days)
    await session.flush()


@pytest.mark.anyio
async def test_voucher_tender_covers_part_of_cart(session):
    user = await _user(session)
    client = await _client(session)
    product = await _product(session, price=10.0)
    coupon = await ev.issue_voucher(session, client_id=client.id, type_key="bon_1e")
    await _backdate_voucher(session, coupon)

    transaction = await PosService(session).create_transaction(
        user_id=user.id,
        items=[_cart_item(product)],
        payments=[
            SimpleNamespace(method="cash", amount=9.0),
            SimpleNamespace(method="voucher", amount=1.0, voucher_code=coupon.code),
        ],
        client_id=client.id,
    )
    assert float(transaction.total_ttc) == 10.0

    # The voucher is consumed and linked to the sale.
    await session.refresh(coupon)
    assert coupon.redeemed_at is not None
    assert coupon.redeemed_transaction_id == transaction.id

    # A voucher payment line was recorded.
    pays = (await session.execute(
        select(Payment).where(Payment.transaction_id == transaction.id)
    )).scalars().all()
    methods = {p.method for p in pays}
    assert PaymentMethod.voucher in methods
    voucher_pay = next(p for p in pays if p.method == PaymentMethod.voucher)
    assert float(voucher_pay.amount) == 1.0


@pytest.mark.anyio
async def test_voucher_tender_over_value_rejected(session):
    user = await _user(session)
    client = await _client(session)
    product = await _product(session, price=10.0)
    coupon = await ev.issue_voucher(session, client_id=client.id, type_key="bon_1e")
    await _backdate_voucher(session, coupon)

    with pytest.raises(InvalidOperation):
        await PosService(session).create_transaction(
            user_id=user.id,
            items=[_cart_item(product)],
            payments=[
                SimpleNamespace(method="cash", amount=5.0),
                SimpleNamespace(method="voucher", amount=5.0, voucher_code=coupon.code),
            ],
            client_id=client.id,
        )


@pytest.mark.anyio
async def test_immediate_voucher_skips_same_day_and_per_person_rules(session):
    """Bons immédiats : utilisables le jour même, plusieurs possibles."""
    from app.services.coupon import validate_coupon

    client = await _client(session)
    c1 = await ev.issue_voucher(session, client_id=client.id, type_key="imm_2e")
    # 2e immediate doit pouvoir s'émettre sans déclencher already_issued
    c2 = await ev.issue_voucher(session, client_id=client.id, type_key="imm_1e")
    assert ev.is_immediate_voucher(c1)
    assert ev.is_immediate_voucher(c2)

    # Et ils sont validables le jour même (pas de same_day error)
    preview = await validate_coupon(
        session, code=c1.code, cart_total=10.0, client_id=client.id,
    )
    assert preview.discount_amount == 2.0


@pytest.mark.anyio
async def test_free_item_voucher_tender_on_scarf(session):
    user = await _user(session)
    client = await _client(session)
    scarf = await _product(session, name="Foulard en soie", price=8.0, category_name="Accessoires")
    coupon = await ev.issue_voucher(session, client_id=client.id, type_key="foulard")
    await _backdate_voucher(session, coupon)

    transaction = await PosService(session).create_transaction(
        user_id=user.id,
        items=[_cart_item(scarf)],
        payments=[SimpleNamespace(method="voucher", amount=8.0, voucher_code=coupon.code)],
        client_id=client.id,
    )
    await session.refresh(coupon)
    assert coupon.redeemed_at is not None
    assert float(transaction.total_ttc) == 8.0


@pytest.mark.anyio
async def test_only_one_event_voucher_per_transaction(session):
    """Empiler deux bons cadeau événementiels sur une même vente est refusé."""
    user = await _user(session)
    client = await _client(session)
    product = await _product(session, price=10.0)
    # Deux bons immédiats : les bons "prochain achat" sont déjà limités à 1
    # par cliente côté émission. Les immédiats peuvent être émis plusieurs
    # fois — le garde-fou empêche leur cumul *sur une même transaction*.
    c1 = await ev.issue_voucher(session, client_id=client.id, type_key="imm_1e")
    c2 = await ev.issue_voucher(session, client_id=client.id, type_key="imm_2e")

    with pytest.raises(InvalidOperation, match="Un seul bon"):
        await PosService(session).create_transaction(
            user_id=user.id,
            items=[_cart_item(product)],
            payments=[
                SimpleNamespace(method="voucher", amount=1.0, voucher_code=c1.code),
                SimpleNamespace(method="voucher", amount=2.0, voucher_code=c2.code),
                SimpleNamespace(method="cash", amount=7.0),
            ],
            client_id=client.id,
        )
