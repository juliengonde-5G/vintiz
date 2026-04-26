"""Tests for coupon validation + redemption (POS integration)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    AvoirTransaction,
    Client,
    Consent,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.coupon import Coupon, CouponDiscountType, CouponSource
from app.models.pos import Transaction
from app.models.user import User
from app.services.coupon import (
    CouponError,
    redeem_coupon,
    validate_coupon,
    issue_anniversary_coupon,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Client.__table__,
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        AvoirTransaction.__table__,
        Consent.__table__,
        Transaction.__table__,
        Coupon.__table__,
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


async def _generic_coupon(session, **overrides) -> Coupon:
    now = datetime.now(timezone.utc)
    defaults = dict(
        code="TEST-XXXXXX",
        client_id=None,
        discount_type=CouponDiscountType.percent,
        discount_value=10.0,
        source=CouponSource.manual,
        valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(days=7),
        is_active=True,
    )
    defaults.update(overrides)
    c = Coupon(**defaults)
    session.add(c)
    await session.flush()
    return c


# ---------------------------------------------------------------------------
# validate_coupon — success paths
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_validate_percent_coupon(session):
    await _generic_coupon(session, code="PERCENT-1", discount_value=10)
    preview = await validate_coupon(session, code="percent-1", cart_total=100.0)
    assert preview.discount_amount == 10.0
    assert preview.new_total == 90.0
    assert preview.code == "PERCENT-1"


@pytest.mark.anyio
async def test_validate_amount_coupon_caps_at_cart_total(session):
    await _generic_coupon(
        session, code="AMOUNT-1",
        discount_type=CouponDiscountType.amount, discount_value=200,
    )
    # Cart smaller than the coupon — discount caps at cart_total.
    preview = await validate_coupon(session, code="AMOUNT-1", cart_total=50.0)
    assert preview.discount_amount == 50.0
    assert preview.new_total == 0.0


# ---------------------------------------------------------------------------
# validate_coupon — failure paths
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_validate_unknown_code(session):
    with pytest.raises(CouponError, match="not_found"):
        await validate_coupon(session, code="NO-SUCH", cart_total=10)


@pytest.mark.anyio
async def test_validate_inactive_coupon(session):
    await _generic_coupon(session, code="OFF-1", is_active=False)
    with pytest.raises(CouponError, match="inactive"):
        await validate_coupon(session, code="OFF-1", cart_total=10)


@pytest.mark.anyio
async def test_validate_expired_coupon(session):
    now = datetime.now(timezone.utc)
    await _generic_coupon(
        session, code="OLD-1",
        valid_from=now - timedelta(days=10),
        valid_until=now - timedelta(days=1),
    )
    with pytest.raises(CouponError, match="expired"):
        await validate_coupon(session, code="OLD-1", cart_total=10)


@pytest.mark.anyio
async def test_validate_not_yet_valid_coupon(session):
    now = datetime.now(timezone.utc)
    await _generic_coupon(
        session, code="FUTURE-1",
        valid_from=now + timedelta(days=1),
        valid_until=now + timedelta(days=8),
    )
    with pytest.raises(CouponError, match="not_yet_valid"):
        await validate_coupon(session, code="FUTURE-1", cart_total=10)


@pytest.mark.anyio
async def test_validate_redeemed_coupon(session):
    now = datetime.now(timezone.utc)
    await _generic_coupon(
        session, code="USED-1", redeemed_at=now,
    )
    with pytest.raises(CouponError, match="redeemed"):
        await validate_coupon(session, code="USED-1", cart_total=10)


@pytest.mark.anyio
async def test_validate_nominative_requires_client(session):
    client = Client(first_name="A", last_name="B", email="a@b.fr")
    session.add(client)
    await session.flush()
    await _generic_coupon(session, code="NOMINATIVE", client_id=client.id)

    # No client supplied → reject
    with pytest.raises(CouponError, match="no_client"):
        await validate_coupon(session, code="NOMINATIVE", cart_total=10)

    # Wrong client → reject
    with pytest.raises(CouponError, match="wrong_client"):
        await validate_coupon(
            session, code="NOMINATIVE", cart_total=10,
            client_id=uuid.uuid4(),
        )

    # Right client → success
    preview = await validate_coupon(
        session, code="NOMINATIVE", cart_total=100,
        client_id=client.id,
    )
    assert preview.discount_amount == 10.0


# ---------------------------------------------------------------------------
# redeem_coupon
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_redeem_marks_used_and_links_tx(session):
    coupon = await _generic_coupon(session, code="REDEEM-1")
    fake_tx = uuid.uuid4()
    redeemed = await redeem_coupon(session, coupon.id, fake_tx)
    assert redeemed.redeemed_at is not None
    assert redeemed.redeemed_transaction_id == fake_tx


@pytest.mark.anyio
async def test_redeem_twice_rejected(session):
    coupon = await _generic_coupon(session, code="REDEEM-2")
    await redeem_coupon(session, coupon.id, uuid.uuid4())
    with pytest.raises(CouponError, match="redeemed"):
        await redeem_coupon(session, coupon.id, uuid.uuid4())


@pytest.mark.anyio
async def test_redeem_unknown_id_rejected(session):
    with pytest.raises(CouponError, match="not_found"):
        await redeem_coupon(session, uuid.uuid4(), uuid.uuid4())


# ---------------------------------------------------------------------------
# Anniversary coupon → validate → redeem (full flow)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_anniversary_full_flow(session):
    client = Client(first_name="Bob", last_name="X", email="b@x.fr")
    session.add(client)
    await session.flush()

    issued = await issue_anniversary_coupon(session, client.id)
    preview = await validate_coupon(
        session, code=issued.code, cart_total=80.0, client_id=client.id,
    )
    assert preview.discount_amount == 8.0  # 10% of 80
    fake_tx = uuid.uuid4()
    used = await redeem_coupon(session, preview.coupon_id, fake_tx)
    assert used.redeemed_transaction_id == fake_tx
