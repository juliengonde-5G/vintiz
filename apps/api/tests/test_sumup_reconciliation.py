"""Tests du service de réconciliation SumUp.

On stub l'appel HTTP SumUp (``_fetch_sumup_transactions``) pour pouvoir
contrôler la liste des transactions remontées et vérifier :

- match par identifiant exact (cas nominal)
- match par montant en repli (Vintiz n'a pas d'ID — typique du jour 1)
- détection de l'absence de clé API (diagnostic explicite)
- exposition d'un message d'erreur API plutôt que silence
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.audit import Settings
from app.models.client import Client, LoyaltyAccount, LoyaltyTransaction
from app.models.pos import (
    Payment,
    PaymentMethod,
    Receipt,
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.user import User
from app.services.sumup_reconciliation import (
    SumUpReconciliationService,
    SumUpTx,
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
        ProductPhoto.__table__,
        Client.__table__,
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        Payment.__table__,
        Receipt.__table__,
        Settings.__table__,
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


async def _user(session) -> User:
    from app.models.user import UserRole

    u = User(
        username=f"u{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:6]}@x.fr",
        password_hash="x" * 60,
        role=UserRole.manager,
        is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


async def _card_payment(
    session,
    *,
    user: User,
    amount: float,
    sumup_transaction_id: str | None,
    transaction_number: int,
    when: datetime,
) -> tuple[Transaction, Payment]:
    txn = Transaction(
        user_id=user.id,
        transaction_type=TransactionType.sale,
        transaction_number=transaction_number,
        total_ht=amount / 1.20,
        total_tva=amount - (amount / 1.20),
        total_ttc=amount,
        hash_chain="0" * 64,
        created_at=when,
    )
    session.add(txn)
    await session.flush()
    payment = Payment(
        transaction_id=txn.id,
        method=PaymentMethod.card,
        amount=amount,
        sumup_transaction_id=sumup_transaction_id,
    )
    session.add(payment)
    await session.flush()
    return txn, payment


def _stub_fetch(txs: list[SumUpTx], err: str | None = None, pages: int = 1):
    def _stub(self, api_key, target_date):
        return txs, err, pages

    return _stub


@pytest.mark.anyio
async def test_matches_by_id_when_payment_has_sumup_id(session, monkeypatch):
    monkeypatch.setenv("SUMUP_API_KEY", "sup_sk_test")
    user = await _user(session)
    when = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    _, _payment = await _card_payment(
        session,
        user=user,
        amount=20.0,
        sumup_transaction_id="tx_abc",
        transaction_number=1,
        when=when,
    )
    fake_txs = [SumUpTx(
        transaction_id="tx_abc", transaction_code="C1",
        amount=20.0, currency="EUR", status="SUCCESSFUL",
        timestamp=when.isoformat(),
    )]
    monkeypatch.setattr(
        SumUpReconciliationService,
        "_fetch_sumup_transactions",
        _stub_fetch(fake_txs),
    )

    report = await SumUpReconciliationService(session).reconcile(date(2026, 6, 4))
    assert report.matched_count == 1
    assert report.matched_by_amount == 0
    assert report.unmatched_vintiz == 0
    assert report.unmatched_sumup == 0
    assert report.lines[0].status == "matched"


@pytest.mark.anyio
async def test_fallback_pairs_by_amount_when_vintiz_id_missing(session, monkeypatch):
    """Le cas réel jour 1 : la caissière a validé en manuel, SumUp ID NULL."""
    monkeypatch.setenv("SUMUP_API_KEY", "sup_sk_test")
    user = await _user(session)
    when = datetime(2026, 6, 4, 11, 0, tzinfo=timezone.utc)
    await _card_payment(
        session, user=user, amount=12.50, sumup_transaction_id=None,
        transaction_number=10, when=when,
    )
    await _card_payment(
        session, user=user, amount=8.00, sumup_transaction_id=None,
        transaction_number=11, when=when,
    )
    fake_txs = [
        SumUpTx(transaction_id="tx_1", transaction_code="C1",
                amount=12.50, currency="EUR", status="SUCCESSFUL",
                timestamp=when.isoformat()),
        SumUpTx(transaction_id="tx_2", transaction_code="C2",
                amount=8.00, currency="EUR", status="SUCCESSFUL",
                timestamp=when.isoformat()),
    ]
    monkeypatch.setattr(
        SumUpReconciliationService,
        "_fetch_sumup_transactions",
        _stub_fetch(fake_txs),
    )

    report = await SumUpReconciliationService(session).reconcile(date(2026, 6, 4))
    assert report.matched_count == 2
    assert report.matched_by_amount == 2
    assert report.unmatched_vintiz == 0
    assert report.unmatched_sumup == 0
    statuses = {ln.status for ln in report.lines if ln.vintiz_payment_id}
    assert statuses == {"matched_amount"}


@pytest.mark.anyio
async def test_amount_pairing_is_fifo_when_duplicates(session, monkeypatch):
    monkeypatch.setenv("SUMUP_API_KEY", "sup_sk_test")
    user = await _user(session)
    base = datetime(2026, 6, 4, 9, 0, tzinfo=timezone.utc)
    # Deux paiements Vintiz de 15 € sans ID + un 20 €.
    _, p1 = await _card_payment(session, user=user, amount=15.0,
                                 sumup_transaction_id=None,
                                 transaction_number=1, when=base)
    _, p2 = await _card_payment(session, user=user, amount=15.0,
                                 sumup_transaction_id=None,
                                 transaction_number=2,
                                 when=base.replace(hour=10))
    _, p3 = await _card_payment(session, user=user, amount=20.0,
                                 sumup_transaction_id=None,
                                 transaction_number=3,
                                 when=base.replace(hour=11))
    fake_txs = [
        SumUpTx(transaction_id="tx_a", transaction_code="A", amount=15.0,
                currency="EUR", status="SUCCESSFUL", timestamp=base.isoformat()),
        SumUpTx(transaction_id="tx_b", transaction_code="B", amount=15.0,
                currency="EUR", status="SUCCESSFUL",
                timestamp=base.replace(hour=10).isoformat()),
        SumUpTx(transaction_id="tx_c", transaction_code="C", amount=20.0,
                currency="EUR", status="SUCCESSFUL",
                timestamp=base.replace(hour=11).isoformat()),
    ]
    monkeypatch.setattr(
        SumUpReconciliationService,
        "_fetch_sumup_transactions",
        _stub_fetch(fake_txs),
    )

    report = await SumUpReconciliationService(session).reconcile(date(2026, 6, 4))
    assert report.matched_by_amount == 3
    assert report.unmatched_vintiz == 0
    assert report.unmatched_sumup == 0


@pytest.mark.anyio
async def test_reports_missing_api_key_explicitly(session, monkeypatch):
    monkeypatch.delenv("SUMUP_API_KEY", raising=False)
    user = await _user(session)
    when = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    await _card_payment(
        session, user=user, amount=10.0, sumup_transaction_id=None,
        transaction_number=1, when=when,
    )

    report = await SumUpReconciliationService(session).reconcile(date(2026, 6, 4))
    assert report.api_key_present is False
    assert report.api_error is not None
    assert "SumUp" in report.api_error
    # 1 paiement orphelin, mais pas d'appel API → pas de SumUp côté.
    assert report.unmatched_vintiz == 1
    assert report.unmatched_sumup == 0


@pytest.mark.anyio
async def test_surfaces_api_error_in_report(session, monkeypatch):
    monkeypatch.setenv("SUMUP_API_KEY", "sup_sk_test")
    user = await _user(session)
    when = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    await _card_payment(
        session, user=user, amount=10.0, sumup_transaction_id="tx_x",
        transaction_number=1, when=when,
    )
    monkeypatch.setattr(
        SumUpReconciliationService,
        "_fetch_sumup_transactions",
        _stub_fetch([], err="HTTP 401 Unauthorized"),
    )

    report = await SumUpReconciliationService(session).reconcile(date(2026, 6, 4))
    assert report.api_key_present is True
    assert report.api_error == "HTTP 401 Unauthorized"
    assert report.unmatched_vintiz == 1
