"""Tests for the DGFiP fiscal export (P1-015)."""

from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    AvoirTransaction,
    Client,
    Consent,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.pos import (
    CashDrawer,
    Payment,
    PaymentMethod,
    Receipt,
    Transaction,
    TransactionItem,
    TransactionType,
    ZReport,
)
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.user import User, UserRole
from app.services.fiscal_export import FiscalExportService


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
        Transaction.__table__,
        TransactionItem.__table__,
        Payment.__table__,
        Receipt.__table__,
        CashDrawer.__table__,
        ZReport.__table__,
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        AvoirTransaction.__table__,
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


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


async def _seed_minimal(session: AsyncSession) -> dict:
    """Insert one user + one category + two sales + one Z report."""
    user = User(
        username="u", email="u@v.fr", password_hash="x" * 60,
        role=UserRole.manager, is_active=True,
    )
    session.add(user)
    cat = Category(name="Robes")
    session.add(cat)
    await session.flush()

    p1 = Product(
        barcode="A", name="Robe", category_id=cat.id, sale_price=49.0,
        status=ProductStatus.sold,
    )
    p2 = Product(
        barcode="B", name="Sac", category_id=cat.id, sale_price=12.0,
        status=ProductStatus.sold,
    )
    session.add_all([p1, p2])
    await session.flush()

    base_dt = datetime(2026, 4, 26, 9, 0, 0, tzinfo=timezone.utc)

    sale1 = Transaction(
        transaction_number=1,
        transaction_type=TransactionType.sale,
        user_id=user.id,
        total_ht=40.83, total_tva=8.17, total_ttc=49.00,
        hash_chain="hash-1",
        created_at=base_dt,
    )
    session.add(sale1)
    await session.flush()
    session.add_all([
        TransactionItem(
            transaction_id=sale1.id, product_id=p1.id,
            quantity=1, unit_price=49.0, discount_percent=0, line_total=49.0,
        ),
        Payment(transaction_id=sale1.id, method=PaymentMethod.cash, amount=49.0),
    ])

    sale2 = Transaction(
        transaction_number=2,
        transaction_type=TransactionType.sale,
        user_id=user.id,
        total_ht=10.0, total_tva=2.0, total_ttc=12.0,
        hash_chain="hash-2",
        created_at=base_dt + timedelta(hours=1),
    )
    session.add(sale2)
    await session.flush()
    session.add_all([
        TransactionItem(
            transaction_id=sale2.id, product_id=p2.id,
            quantity=1, unit_price=12.0, discount_percent=0, line_total=12.0,
        ),
        Payment(transaction_id=sale2.id, method=PaymentMethod.card, amount=12.0),
    ])

    drawer = CashDrawer(
        user_id=user.id,
        opened_at=base_dt - timedelta(hours=1),
        closed_at=base_dt + timedelta(hours=2),
        opening_amount=100.0,
        closing_amount=149.0,
        expected_amount=149.0,
        is_open=False,
    )
    session.add(drawer)
    await session.flush()

    z = ZReport(
        report_number=1,
        user_id=user.id,
        cash_drawer_id=drawer.id,
        total_sales=61.0,
        total_refunds=0,
        total_net=61.0,
        transaction_count=2,
        hash="z-hash-1",
        previous_hash="0",
        created_at=base_dt + timedelta(hours=2),
    )
    session.add(z)
    await session.flush()
    return {
        "user": user, "p1": p1, "p2": p2,
        "sale1": sale1, "sale2": sale2, "z": z,
        "base_dt": base_dt,
    }


# ---------------------------------------------------------------------------
# Snapshot structure
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_snapshot_includes_all_transactions_and_z_reports(session):
    await _seed_minimal(session)
    snap = await FiscalExportService(session).build_snapshot()

    assert snap["totals"]["transactions_count"] == 2
    assert snap["totals"]["sales_count"] == 2
    assert snap["totals"]["refunds_count"] == 0
    assert snap["totals"]["z_reports_count"] == 1
    # Order is chain order — sale1 first
    assert snap["transactions"][0]["number"] == 1
    assert snap["transactions"][1]["number"] == 2
    # hash_chain present (the legal anchor)
    assert snap["transactions"][0]["hash_chain"] == "hash-1"
    # Items + payments rolled in
    assert len(snap["transactions"][0]["items"]) == 1
    assert snap["transactions"][0]["payments"][0]["method"] == "cash"


@pytest.mark.anyio
async def test_period_filter_excludes_out_of_window(session):
    seed = await _seed_minimal(session)
    # Window covers only sale1 (sale2 is 1h later).
    snap = await FiscalExportService(session).build_snapshot(
        period_from=seed["base_dt"] - timedelta(minutes=1),
        period_to=seed["base_dt"] + timedelta(minutes=30),
    )
    assert snap["totals"]["transactions_count"] == 1
    assert snap["transactions"][0]["number"] == 1
    # Z report is outside the window
    assert snap["totals"]["z_reports_count"] == 0


# ---------------------------------------------------------------------------
# XML encoder
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_xml_export_is_well_formed_and_carries_hash_chain(session):
    await _seed_minimal(session)
    svc = FiscalExportService(session)
    snap = await svc.build_snapshot(merchant_name="Vintiz Vernon")
    xml = svc.to_xml(snap)

    assert xml.startswith("<?xml")
    root = ET.fromstring(xml)
    assert root.tag == "FiscalExport"
    assert root.get("merchant_name") == "Vintiz Vernon"
    assert root.get("format") == "vintiz-nf525-export"

    transactions = root.find("Transactions")
    assert transactions.get("count") == "2"
    first_tx = transactions[0]
    assert first_tx.get("number") == "1"
    assert first_tx.get("type") == "sale"
    assert first_tx.get("hash_chain") == "hash-1"
    # Items + payments are sub-elements
    items = first_tx.find("Items")
    assert items.get("count") == "1"
    payments = first_tx.find("Payments")
    assert payments.get("count") == "1"
    assert payments[0].get("method") == "cash"

    z_reports = root.find("ZReports")
    assert z_reports.get("count") == "1"
    assert z_reports[0].get("hash") == "z-hash-1"
    assert z_reports[0].get("previous_hash") == "0"


# ---------------------------------------------------------------------------
# JSON encoder
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_json_export_round_trips(session):
    import json

    await _seed_minimal(session)
    svc = FiscalExportService(session)
    snap = await svc.build_snapshot()
    payload = svc.to_json(snap)
    parsed = json.loads(payload)

    assert parsed["format"] == "vintiz-nf525-export"
    assert parsed["totals"]["transactions_count"] == 2
    assert parsed["transactions"][0]["hash_chain"] == "hash-1"
    assert parsed["z_reports"][0]["hash"] == "z-hash-1"


# ---------------------------------------------------------------------------
# Refunds and cashier/client identifiers are exported
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_refund_appears_with_original_link_and_reason(session):
    seed = await _seed_minimal(session)
    user = seed["user"]
    sale1 = seed["sale1"]

    refund = Transaction(
        transaction_number=3,
        transaction_type=TransactionType.refund,
        user_id=user.id,
        cashier_id=user.id,
        client_id=None,
        original_transaction_id=sale1.id,
        refund_reason="Mauvaise taille",
        total_ht=40.83, total_tva=8.17, total_ttc=49.00,
        hash_chain="hash-refund",
        created_at=seed["base_dt"] + timedelta(hours=3),
    )
    session.add(refund)
    await session.flush()

    snap = await FiscalExportService(session).build_snapshot()
    refund_dict = next(
        t for t in snap["transactions"] if t["type"] == "refund"
    )
    assert refund_dict["original_transaction_id"] == str(sale1.id)
    assert refund_dict["refund_reason"] == "Mauvaise taille"
    assert refund_dict["cashier_id"] == str(user.id)


# ---------------------------------------------------------------------------
# Empty period — clean output
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_empty_period_produces_valid_export(session):
    # No data inserted at all
    svc = FiscalExportService(session)
    snap = await svc.build_snapshot()
    assert snap["totals"]["transactions_count"] == 0
    assert snap["totals"]["z_reports_count"] == 0
    xml = svc.to_xml(snap)
    root = ET.fromstring(xml)
    assert root.find("Transactions").get("count") == "0"
    assert root.find("ZReports").get("count") == "0"
