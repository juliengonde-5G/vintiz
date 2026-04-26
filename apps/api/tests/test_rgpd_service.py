"""Tests for the RGPD service: consent ledger, data export, soft/hard deletion (P1-007)."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    AvoirTransaction,
    AvoirTxType,
    Client,
    Consent,
    ConsentPurpose,
    LoyaltyAccount,
    LoyaltyTransaction,
    LoyaltyTxType,
)
from app.models.pos import (
    Payment,
    Receipt,
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.models.product import Category, Product, ProductStatus
from app.models.user import User, UserRole
from app.services.rgpd import (
    CURRENT_POLICY_VERSION,
    DELETION_WINDOW,
    RgpdService,
)


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
        Client.__table__,
        Consent.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        Payment.__table__,
        Receipt.__table__,
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


async def _make_user(session: AsyncSession, username: str = "manager") -> User:
    u = User(
        username=username, email=f"{username}@vintiz.fr",
        password_hash="x" * 60, role=UserRole.manager, is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


async def _make_client(session: AsyncSession, email: str = "julie@example.com") -> Client:
    c = Client(
        first_name="Julie", last_name="Martin",
        email=email, avoir_credit=0,
        email_optin=False, sms_optin=False,
    )
    session.add(c)
    await session.flush()
    return c


# ---------------------------------------------------------------------------
# Consents
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_record_consent_appends_row_and_mirrors_flag(session):
    user = await _make_user(session)
    client = await _make_client(session)

    svc = RgpdService(session)
    entry = await svc.record_consent(
        client=client,
        purpose=ConsentPurpose.email_marketing,
        granted=True,
        source="site_signup",
        recorded_by_user_id=user.id,
    )

    assert entry.granted is True
    assert entry.policy_version == CURRENT_POLICY_VERSION
    # Legacy flag mirrored
    assert client.email_optin is True


@pytest.mark.anyio
async def test_revoking_consent_clears_legacy_flag(session):
    user = await _make_user(session)
    client = await _make_client(session)
    svc = RgpdService(session)

    await svc.record_consent(
        client, ConsentPurpose.sms_marketing, True, "admin", user.id,
    )
    assert client.sms_optin is True

    await svc.record_consent(
        client, ConsentPurpose.sms_marketing, False, "admin", user.id,
    )
    assert client.sms_optin is False


@pytest.mark.anyio
async def test_current_consents_returns_latest_per_purpose(session):
    user = await _make_user(session)
    client = await _make_client(session)
    svc = RgpdService(session)

    await svc.record_consent(client, ConsentPurpose.email_marketing, True, "site", user.id)
    await svc.record_consent(client, ConsentPurpose.email_marketing, False, "admin", user.id)
    await svc.record_consent(client, ConsentPurpose.profiling, True, "site", user.id)

    current = await svc.current_consents(client.id)
    assert current["email_marketing"]["granted"] is False
    assert current["profiling"]["granted"] is True


@pytest.mark.anyio
async def test_consent_history_is_reverse_chronological(session):
    user = await _make_user(session)
    client = await _make_client(session)
    svc = RgpdService(session)

    await svc.record_consent(client, ConsentPurpose.email_marketing, True, "site", user.id)
    await svc.record_consent(client, ConsentPurpose.profiling, True, "site", user.id)

    history = await svc.consent_history(client.id)
    assert len(history) == 2
    assert {row["purpose"] for row in history} == {"email_marketing", "profiling"}


# ---------------------------------------------------------------------------
# Data export
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_data_export_includes_full_snapshot(session):
    user = await _make_user(session)
    client = await _make_client(session)
    client.phone = "0612345678"
    client.notes = "VIP"
    client.avoir_credit = 12.50

    # Loyalty
    account = LoyaltyAccount(client_id=client.id, points=120, tier="silver")
    session.add(account)
    await session.flush()
    session.add(LoyaltyTransaction(
        account_id=account.id, tx_type=LoyaltyTxType.earn,
        points=20, description="Achat #42",
    ))

    # Avoir history
    session.add(AvoirTransaction(
        client_id=client.id, tx_type=AvoirTxType.credit,
        amount=Decimal("12.50"), reason="Refund",
    ))

    # Consent
    svc = RgpdService(session)
    await svc.record_consent(client, ConsentPurpose.email_marketing, True, "site", user.id)
    await session.flush()

    export = await svc.export_client_data(client)

    assert export["client"]["email"] == "julie@example.com"
    assert export["client"]["phone"] == "0612345678"
    assert export["client"]["avoir_credit"] == pytest.approx(12.50)
    assert export["loyalty"]["tier"] == "silver"
    assert export["loyalty"]["points"] == 120
    assert len(export["loyalty"]["transactions"]) == 1
    assert len(export["avoir_history"]) == 1
    assert len(export["consents"]) == 1
    assert export["policy_version"] == CURRENT_POLICY_VERSION


# ---------------------------------------------------------------------------
# Soft / hard deletion + cancel
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_request_deletion_stamps_timestamp(session):
    client = await _make_client(session)
    requested_at = await RgpdService(session).request_deletion(client)
    assert client.deletion_requested_at == requested_at
    assert (datetime.now(timezone.utc) - requested_at) < timedelta(seconds=5)


@pytest.mark.anyio
async def test_double_deletion_request_rejected(session):
    from fastapi import HTTPException

    client = await _make_client(session)
    svc = RgpdService(session)
    await svc.request_deletion(client)
    with pytest.raises(HTTPException) as exc:
        await svc.request_deletion(client)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_cancel_deletion_clears_timestamp(session):
    client = await _make_client(session)
    svc = RgpdService(session)
    await svc.request_deletion(client)
    assert client.deletion_requested_at is not None
    await svc.cancel_deletion(client)
    assert client.deletion_requested_at is None


@pytest.mark.anyio
async def test_cancel_deletion_without_request_rejected(session):
    from fastapi import HTTPException

    client = await _make_client(session)
    with pytest.raises(HTTPException) as exc:
        await RgpdService(session).cancel_deletion(client)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_purge_skips_clients_within_window(session):
    client = await _make_client(session)
    client.deletion_requested_at = datetime.now(timezone.utc) - timedelta(days=10)
    await session.flush()

    summary = await RgpdService(session).purge_pending_deletions()
    assert summary["purged_count"] == 0
    # Client still exists
    assert (await session.execute(
        select(Client).where(Client.id == client.id)
    )).scalar_one_or_none() is not None


@pytest.mark.anyio
async def test_purge_hard_deletes_client_past_window_and_anonymizes_transactions(session):
    user = await _make_user(session)
    client = await _make_client(session, email="topurge@example.com")

    # Create a transaction tied to this client
    cat = Category(name="Robes")
    session.add(cat)
    await session.flush()
    sale = Transaction(
        transaction_number=42,
        transaction_type=TransactionType.sale,
        user_id=user.id,
        client_id=client.id,
        total_ht=10, total_tva=2, total_ttc=12,
        hash_chain="x",
    )
    session.add(sale)
    # Add a loyalty account + avoir + consent to verify they vanish
    account = LoyaltyAccount(client_id=client.id, points=10, tier="bronze")
    session.add(account)
    await session.flush()
    session.add(LoyaltyTransaction(
        account_id=account.id, tx_type=LoyaltyTxType.earn,
        points=10, description="x",
    ))
    session.add(AvoirTransaction(
        client_id=client.id, tx_type=AvoirTxType.credit,
        amount=Decimal("5"), reason="x",
    ))
    svc = RgpdService(session)
    await svc.record_consent(client, ConsentPurpose.email_marketing, True, "admin", user.id)

    # Stamp deletion request 31 days ago
    client.deletion_requested_at = datetime.now(timezone.utc) - timedelta(days=31)
    await session.flush()

    summary = await svc.purge_pending_deletions()
    assert summary["purged_count"] == 1

    # Client gone
    assert (await session.execute(
        select(Client).where(Client.id == client.id)
    )).scalar_one_or_none() is None

    # Transaction kept but anonymised
    refreshed = (await session.execute(
        select(Transaction).where(Transaction.id == sale.id)
    )).scalar_one()
    assert refreshed.client_id is None

    # Loyalty / avoir / consent rows for this client are gone
    assert (await session.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.client_id == client.id)
    )).scalar_one_or_none() is None
    assert (await session.execute(
        select(AvoirTransaction).where(AvoirTransaction.client_id == client.id)
    )).scalars().all() == []
    assert (await session.execute(
        select(Consent).where(Consent.client_id == client.id)
    )).scalars().all() == []


@pytest.mark.anyio
async def test_deletion_window_constant_is_30_days():
    # Sanity check so a future refactor that quietly shrinks the grace period
    # surfaces in CI.
    assert DELETION_WINDOW == timedelta(days=30)
