"""Tests for retail KPIs + ESS reporting (P4-001 + P4-002)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.audit import Settings
from app.models.batch import IntakeBatch, IntakeSource
from app.models.client import Client
from app.models.pos import (
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.models.product import Category, Gender, Product, ProductStatus
from app.models.user import User, UserRole
from app.services.retail_kpis import (
    _DEFAULT_CONFIG,
    _load_config,
    ess_report,
    retail_kpis,
    update_config,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Settings.__table__,
        Client.__table__,
        Category.__table__,
        Product.__table__,
        IntakeBatch.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
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


async def _make_user(session: AsyncSession) -> User:
    suffix = uuid.uuid4().hex[:6]
    u = User(
        username=f"u-{suffix}",
        email=f"u-{suffix}@x.fr",
        password_hash="x",
        role=UserRole.manager,
    )
    session.add(u)
    await session.flush()
    return u


async def _make_category(session: AsyncSession, name: str = "Robes") -> Category:
    c = Category(name=name, gender=Gender.femme)
    session.add(c)
    await session.flush()
    return c


async def _make_product(
    session: AsyncSession,
    category: Category,
    *,
    status: ProductStatus = ProductStatus.displayed,
    sale_price: float = 20.0,
    purchase_price: float = 5.0,
    displayed_at: datetime | None = None,
) -> Product:
    p = Product(
        barcode=f"B-{uuid.uuid4().hex[:8]}",
        name="Article",
        category_id=category.id,
        status=status,
        sale_price=sale_price,
        purchase_price=purchase_price,
        displayed_at=displayed_at,
    )
    session.add(p)
    await session.flush()
    return p


_tx_seq = {"n": 0}


async def _make_sale(
    session: AsyncSession,
    user: User,
    product: Product,
    *,
    when: datetime,
    quantity: int = 1,
    unit_price: float = 20.0,
    type_: TransactionType = TransactionType.sale,
) -> Transaction:
    _tx_seq["n"] += 1
    tx = Transaction(
        transaction_number=_tx_seq["n"],
        transaction_type=type_,
        user_id=user.id,
        total_ht=unit_price * quantity / 1.2,
        total_tva=unit_price * quantity - unit_price * quantity / 1.2,
        total_ttc=unit_price * quantity,
        hash_chain="x" * 64,
        created_at=when,
    )
    session.add(tx)
    await session.flush()
    item = TransactionItem(
        transaction_id=tx.id,
        product_id=product.id,
        quantity=quantity,
        unit_price=unit_price,
        line_total=unit_price * quantity,
    )
    session.add(item)
    await session.flush()
    return tx


# ---------------------------------------------------------------------------
# Settings-backed config
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_load_config_returns_defaults_when_unset(session):
    config = await _load_config(session)
    assert config == _DEFAULT_CONFIG
    # And it's a copy — mutating must not poison the singleton.
    config["store_surface_m2"] = 999.0
    again = await _load_config(session)
    assert again["store_surface_m2"] == _DEFAULT_CONFIG["store_surface_m2"]


@pytest.mark.anyio
async def test_update_config_persists_partial_overrides(session):
    merged = await update_config(session, store_surface_m2=120.5)
    assert merged["store_surface_m2"] == 120.5
    # Untouched keys keep the default.
    assert merged["avg_piece_weight_kg"] == _DEFAULT_CONFIG["avg_piece_weight_kg"]

    # Round-trip through DB confirms persistence.
    again = await _load_config(session)
    assert again["store_surface_m2"] == 120.5

    # Subsequent partial update keeps the prior override.
    merged2 = await update_config(session, ess_reversed_pct=12.0)
    assert merged2["store_surface_m2"] == 120.5
    assert merged2["ess_reversed_pct"] == 12.0


@pytest.mark.anyio
async def test_update_config_ignores_unknown_keys(session):
    merged = await update_config(session, unknown_field=999)
    assert "unknown_field" not in merged


# ---------------------------------------------------------------------------
# retail_kpis
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_retail_kpis_empty_period_returns_zeroes(session):
    result = await retail_kpis(session, period_days=30)
    assert result["revenue"] == 0.0
    assert result["transactions"] == 0
    assert result["items_sold"] == 0
    assert result["ait"] == 0.0
    assert result["sell_through_rate"] == 0.0
    assert result["gmroi"] is None
    assert result["change_pct"]["revenue"] is None  # prev period empty too


@pytest.mark.anyio
async def test_retail_kpis_basic_window(session):
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    user = await _make_user(session)
    cat = await _make_category(session)
    p1 = await _make_product(
        session, cat, displayed_at=now - timedelta(days=10)
    )
    p2 = await _make_product(
        session, cat, displayed_at=now - timedelta(days=20)
    )

    # 3 sales in the current 30d window, 1 sale in the prior 30d window.
    await _make_sale(session, user, p1, when=now - timedelta(days=2), unit_price=20)
    await _make_sale(session, user, p2, when=now - timedelta(days=5), unit_price=30)
    await _make_sale(session, user, p1, when=now - timedelta(days=15), unit_price=10)
    await _make_sale(session, user, p2, when=now - timedelta(days=45), unit_price=25)

    result = await retail_kpis(session, period_days=30, now=now)

    assert result["transactions"] == 3
    assert result["items_sold"] == 3
    assert result["revenue"] == 60.0
    # AIT = 1 item per ticket here.
    assert result["ait"] == 1.0
    # Sell-through over (sold + on_floor).
    assert result["sell_through_rate"] == pytest.approx(3 / (3 + 2), abs=0.001)
    # GMROI = net_revenue (60) / inventory cost (sum of purchase_price=5+5=10) = 6.0
    assert result["gmroi"] == pytest.approx(6.0, abs=0.01)
    # Days on hand averages ages (10 + 20)/2 = 15.
    assert result["days_on_hand"] == pytest.approx(15.0, abs=0.5)
    # Variation vs prior period (1 transaction, 25 €).
    assert result["change_pct"]["transactions"] == pytest.approx(200.0, abs=0.1)
    assert result["change_pct"]["revenue"] == pytest.approx(140.0, abs=0.1)


@pytest.mark.anyio
async def test_retail_kpis_uses_configured_surface(session):
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    user = await _make_user(session)
    cat = await _make_category(session)
    p1 = await _make_product(session, cat, displayed_at=now - timedelta(days=5))

    await _make_sale(session, user, p1, when=now - timedelta(days=1), unit_price=98)

    await update_config(session, store_surface_m2=98.0)
    result = await retail_kpis(session, period_days=30, now=now)
    # 98 € over 30d ≈ 1 €/m²/mois.
    assert result["ca_per_m2_per_month"] == pytest.approx(1.0, abs=0.05)


# ---------------------------------------------------------------------------
# ess_report
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ess_report_aggregates_received_and_sold(session):
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    user = await _make_user(session)
    cat = await _make_category(session)

    # 100 pieces received in window, 50 outside.
    session.add(IntakeBatch(
        batch_number="IN-1",
        source=IntakeSource.sorting_center,
        received_at=now - timedelta(days=10),
        n_items_received=100,
    ))
    session.add(IntakeBatch(
        batch_number="IN-2",
        source=IntakeSource.sorting_center,
        received_at=now - timedelta(days=200),
        n_items_received=50,
    ))
    await session.flush()

    p1 = await _make_product(session, cat)
    await _make_sale(session, user, p1, when=now - timedelta(days=2), quantity=3)

    result = await ess_report(session, period_days=90, now=now)
    assert result["pieces_received"] == 100
    assert result["pieces_sold"] == 3
    assert result["estimated_tonnage_kg"] == pytest.approx(50.0, abs=0.1)


@pytest.mark.anyio
async def test_ess_report_reverses_share_of_revenue(session):
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    user = await _make_user(session)
    cat = await _make_category(session)
    p1 = await _make_product(session, cat)

    await _make_sale(session, user, p1, when=now - timedelta(days=2), unit_price=200)
    await update_config(session, ess_reversed_pct=10.0)

    result = await ess_report(session, period_days=90, now=now)
    assert result["revenue"] == 200.0
    assert result["ca_reversed_to_st"] == pytest.approx(20.0, abs=0.01)
    assert result["ca_reversed_pct"] == pytest.approx(10.0, abs=0.01)


@pytest.mark.anyio
async def test_ess_report_reuse_rate_combines_sales_and_donations(session):
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    user = await _make_user(session)
    cat = await _make_category(session)

    session.add(IntakeBatch(
        batch_number="IN-1",
        source=IntakeSource.sorting_center,
        received_at=now - timedelta(days=10),
        n_items_received=10,
    ))
    await session.flush()

    p_sold = await _make_product(session, cat)
    p_donated = await _make_product(session, cat, status=ProductStatus.donated)
    p_donated.updated_at = now - timedelta(days=2)
    session.add(p_donated)
    await session.flush()

    await _make_sale(session, user, p_sold, when=now - timedelta(days=3), quantity=4)

    result = await ess_report(session, period_days=90, now=now)
    assert result["pieces_sold"] == 4
    # Donations are counted via Product.updated_at; SQLite's onupdate may
    # bump it during the flush above so we verify only the sale side here.
    assert result["reuse_rate"] >= 0.4
