"""Tests for RFM segmentation (P4-007)."""

import uuid
from datetime import datetime, timedelta, timezone

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
from app.models.pos import Transaction, TransactionType
from app.models.user import User, UserRole
from app.services.rfm import (
    _label_from_scores,
    _rank_quintiles,
    compute_rfm,
    persist_segments,
    run_segmentation,
    segment_summary,
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


async def _user(session: AsyncSession) -> User:
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


async def _client(session: AsyncSession, name: str) -> Client:
    c = Client(first_name=name, last_name="Test", email=f"{name.lower()}@x.fr")
    session.add(c)
    await session.flush()
    return c


_tx_seq = {"n": 0}


async def _sale(
    session: AsyncSession,
    user: User,
    client: Client,
    *,
    when: datetime,
    amount: float,
) -> Transaction:
    _tx_seq["n"] += 1
    tx = Transaction(
        transaction_number=_tx_seq["n"],
        transaction_type=TransactionType.sale,
        user_id=user.id,
        client_id=client.id,
        total_ht=amount / 1.2,
        total_tva=amount - amount / 1.2,
        total_ttc=amount,
        hash_chain="x" * 64,
        created_at=when,
    )
    session.add(tx)
    await session.flush()
    return tx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_label_from_scores_covers_main_segments():
    assert _label_from_scores(5, 5, 5) == "champion"
    assert _label_from_scores(4, 4, 4) == "loyal"
    assert _label_from_scores(5, 1, 1) == "new"
    assert _label_from_scores(4, 1, 2) == "promising"
    assert _label_from_scores(1, 5, 5) == "cant_lose"
    assert _label_from_scores(1, 4, 3) == "at_risk"
    assert _label_from_scores(2, 2, 1) == "hibernating"
    assert _label_from_scores(1, 1, 1) == "lost"
    assert _label_from_scores(3, 3, 1) == "regular"


def test_rank_quintiles_ranks_higher_values_higher():
    # Ascending: bigger value → bigger score.
    scores = _rank_quintiles([1.0, 2.0, 3.0, 4.0, 5.0])
    assert scores[0] == 1
    assert scores[4] == 5


def test_rank_quintiles_descending_inverts():
    # Descending: smaller value → bigger score (recency in days).
    scores = _rank_quintiles([1.0, 2.0, 3.0, 4.0, 5.0], descending=True)
    assert scores[0] == 5
    assert scores[4] == 1


def test_rank_quintiles_handles_empty():
    assert _rank_quintiles([]) == {}


# ---------------------------------------------------------------------------
# compute_rfm
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_compute_rfm_returns_one_score_per_buyer(session):
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    user = await _user(session)
    alice = await _client(session, "Alice")
    bob = await _client(session, "Bob")

    await _sale(session, user, alice, when=now - timedelta(days=1), amount=200)
    await _sale(session, user, alice, when=now - timedelta(days=10), amount=120)
    await _sale(session, user, bob, when=now - timedelta(days=80), amount=40)

    scores = await compute_rfm(session, now=now)
    by_id = {s.customer_id: s for s in scores}
    assert alice.id in by_id and bob.id in by_id
    # Alice is more recent and higher monetary than Bob.
    assert by_id[alice.id].r_score >= by_id[bob.id].r_score
    assert by_id[alice.id].m_score >= by_id[bob.id].m_score
    # Frequency is also higher for Alice (2 vs 1).
    assert by_id[alice.id].f_score >= by_id[bob.id].f_score


@pytest.mark.anyio
async def test_compute_rfm_skips_clients_without_paid_sales(session):
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    await _user(session)
    await _client(session, "NoPurchase")

    scores = await compute_rfm(session, now=now)
    assert scores == []


# ---------------------------------------------------------------------------
# persist_segments + run_segmentation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_persist_segments_stamps_clients(session):
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    user = await _user(session)
    alice = await _client(session, "Alice")
    await _sale(session, user, alice, when=now - timedelta(days=1), amount=300)

    scores = await compute_rfm(session, now=now)
    touched = await persist_segments(session, scores)
    assert touched == 1

    refreshed = (await session.execute(
        Client.__table__.select().where(Client.id == alice.id)
    )).first()
    assert refreshed is not None
    # Stamping the same value a second time is a no-op (touched == 0).
    second = await persist_segments(session, scores)
    assert second == 0


@pytest.mark.anyio
async def test_run_segmentation_returns_summary(session):
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    user = await _user(session)
    alice = await _client(session, "Alice")
    bob = await _client(session, "Bob")
    await _sale(session, user, alice, when=now - timedelta(days=1), amount=300)
    await _sale(session, user, bob, when=now - timedelta(days=300), amount=15)

    summary = await run_segmentation(session)
    assert summary["computed"] == 2
    assert summary["updated"] == 2
    assert sum(summary["segments"].values()) == 2

    # segment_summary reads back through the persisted column.
    read_back = await segment_summary(session)
    assert sum(read_back.values()) == 2
