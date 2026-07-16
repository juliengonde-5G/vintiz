"""Regression tests for the NF525 v2 seals and periodic archives."""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.pos import Payment, PaymentMethod, Transaction, TransactionItem
from app.models.user import User, UserRole
from app.services.fiscal import FiscalService
from app.services.fiscal_closure import FiscalClosureService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _signed_sale(session):
    user = User(
        username="fiscal-manager",
        email="fiscal@vintiz.fr",
        password_hash="x" * 60,
        role=UserRole.manager,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    created_at = datetime.now(timezone.utc) - timedelta(days=40)
    transaction = Transaction(
        transaction_number=1,
        user_id=user.id,
        cashier_id=user.id,
        total_ht=10,
        total_tva=2,
        total_ttc=12,
        hash_chain="",
        created_at=created_at,
    )
    session.add(transaction)
    await session.flush()

    item = TransactionItem(
        transaction_id=transaction.id,
        product_name="Article fiscal figé",
        quantity=1,
        unit_price=12,
        line_total=12,
        discount_percent=0,
        promotional=False,
        tva_rate=20,
    )
    payment = Payment(
        transaction_id=transaction.id,
        method=PaymentMethod.cash,
        amount=12,
        tendered_amount=20,
    )
    session.add_all([item, payment])
    await FiscalService(session).sign_transaction(transaction)
    return user, transaction, item, payment, created_at


@pytest.mark.anyio
async def test_v2_signature_detects_item_and_payment_tampering(session):
    _, transaction, item, payment, _ = await _signed_sale(session)
    service = FiscalService(session)

    assert await service.verify_chain_integrity() == {"valid": True, "checked": 1}

    item.line_total = 11
    await session.flush()
    assert (await service.verify_chain_integrity())["reason"] == "signature_mismatch"

    item.line_total = 12
    await service.sign_transaction(transaction)
    payment.amount = 11
    await session.flush()
    assert (await service.verify_chain_integrity())["reason"] == "signature_mismatch"


@pytest.mark.anyio
async def test_periodic_archive_is_signed_cumulative_and_tamper_evident(session):
    user, _, _, _, created_at = await _signed_sale(session)
    service = FiscalClosureService(session)
    period_start = created_at - timedelta(days=1)
    period_end = created_at + timedelta(days=1)

    closure = await service.close_period(
        closure_type="monthly",
        period_start=period_start,
        period_end=period_end,
        user_id=user.id,
    )

    assert closure.manifest["grand_total_period"]["net_ttc"] == "12.00"
    assert closure.manifest["total_perpetual"]["net_ttc"] == "12.00"
    archive = json.loads(gzip.decompress(closure.archive_content))
    assert archive["totals"]["net_ttc"] == "12.00"
    assert await service.verify_chain() == {"valid": True, "checked": 1}

    closure.archive_content += b"tampered"
    await session.flush()
    integrity = await service.verify_chain()
    assert integrity["valid"] is False
    assert integrity["reason"] == "archive_sha256_mismatch"
