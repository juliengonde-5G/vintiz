"""Tests for the admin-configurable loyalty earning rules (#1)."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.services.loyalty_config import (
    DEFAULT_EURO_PER_POINT,
    DEFAULT_VOUCHER_THRESHOLD,
    get_earning_config,
    set_earning_config,
)
from app.services.offers_engine import milestones_crossed, points_to_credit


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
async def test_defaults_match_historical_constants(session):
    cfg = await get_earning_config(session)
    assert cfg.euro_per_point == DEFAULT_EURO_PER_POINT == 1
    # Règle boutique : 100 pts = chèque cadeau de 5 € (500 cents).
    assert cfg.voucher_value_cents == 500
    assert cfg.voucher_threshold == DEFAULT_VOUCHER_THRESHOLD == 100
    assert cfg.voucher_valid_days == 180
    assert cfg.points_expiry_days == 730


@pytest.mark.anyio
async def test_set_and_read_back(session):
    cfg = await set_earning_config(
        session,
        euro_per_point=2,
        voucher_value_cents=1000,
        voucher_threshold=50,
        voucher_valid_days=90,
        points_expiry_days=365,
    )
    assert cfg.euro_per_point == 2
    again = await get_earning_config(session)
    assert again.voucher_threshold == 50
    assert again.voucher_value_cents == 1000


@pytest.mark.anyio
async def test_invalid_values_rejected(session):
    with pytest.raises(ValueError):
        await set_earning_config(
            session, euro_per_point=0, voucher_value_cents=800,
            voucher_threshold=100, voucher_valid_days=180, points_expiry_days=730,
        )


def test_points_to_credit_honours_euro_per_point():
    # 1 pt / 2 € → 49 € = 24 pts
    assert points_to_credit(49.0, 2) == 24
    # default 1 pt / € → 49 pts
    assert points_to_credit(49.0) == 49


def test_milestones_crossed_honours_threshold():
    # threshold 50 → going 40 → 110 crosses 50 and 100 = 2 vouchers
    assert milestones_crossed(40, 110, 50) == 2
    # default 100 → 90 → 210 crosses 100 and 200 = 2
    assert milestones_crossed(90, 210) == 2
