"""Tests pour embeddings_cleanup.py — purge taste profiles inactifs (audit C12).

Vérifie le critère 24 mois (INACTIVITY_DAYS=730) et le mode dry_run, ainsi
que la purge des profils orphelins (clientes hard-deleted hors flow).
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    Client,
    LoyaltyAccount,
    LoyaltyTransaction,
    LoyaltyTxType,
)
from app.models.embeddings import CustomerTasteProfile
from app.services.embeddings_cleanup import (
    INACTIVITY_DAYS,
    purge_inactive_taste_profiles,
    purge_orphan_taste_profiles,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        Client.__table__,
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        CustomerTasteProfile.__table__,
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


def _client(first: str = "Anaïs") -> Client:
    return Client(first_name=first, last_name="X")


async def _add_client_with_loyalty(
    session,
    last_tx_at: datetime | None,
    profile_computed_at: datetime | None,
    membership_no: str,
) -> Client:
    """Crée Client + LoyaltyAccount + (optionnel) une LoyaltyTransaction
    + un CustomerTasteProfile."""
    c = _client()
    session.add(c)
    await session.flush()

    acct = LoyaltyAccount(
        client_id=c.id, points=0, membership_number=membership_no,
    )
    session.add(acct)
    await session.flush()

    if last_tx_at is not None:
        session.add(LoyaltyTransaction(
            account_id=acct.id,
            tx_type=LoyaltyTxType.earn,
            points=5,
            description="seed",
            created_at=last_tx_at,
        ))

    profile = CustomerTasteProfile(
        customer_id=c.id,
        n_purchases_analyzed=1,
        computed_at=profile_computed_at,
        algo_version="t",
    )
    session.add(profile)
    await session.flush()
    return c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_active_within_window_kept(session):
    """Cliente avec une transaction loyalty récente → profil conservé."""
    now = datetime.now(timezone.utc)
    await _add_client_with_loyalty(
        session,
        last_tx_at=now - timedelta(days=30),
        profile_computed_at=now - timedelta(days=10),
        membership_no="V000001",
    )

    res = await purge_inactive_taste_profiles(session, dry_run=False)
    await session.commit()

    assert res["candidate_count"] == 0
    assert res["deleted_count"] == 0

    remaining = (await session.execute(select(CustomerTasteProfile))).scalars().all()
    assert len(remaining) == 1


@pytest.mark.anyio
async def test_inactive_beyond_window_purged(session):
    """Cliente avec dernière tx > 24 mois → profil supprimé."""
    now = datetime.now(timezone.utc)
    await _add_client_with_loyalty(
        session,
        last_tx_at=now - timedelta(days=INACTIVITY_DAYS + 30),
        profile_computed_at=now - timedelta(days=INACTIVITY_DAYS + 30),
        membership_no="V000002",
    )

    res = await purge_inactive_taste_profiles(session, dry_run=False)
    await session.commit()

    assert res["candidate_count"] == 1
    assert res["deleted_count"] == 1
    assert len(res["deleted_customer_ids"]) == 1

    remaining = (await session.execute(select(CustomerTasteProfile))).scalars().all()
    assert len(remaining) == 0


@pytest.mark.anyio
async def test_dry_run_does_not_delete(session):
    """dry_run=True identifie les candidats sans rien supprimer."""
    now = datetime.now(timezone.utc)
    await _add_client_with_loyalty(
        session,
        last_tx_at=now - timedelta(days=INACTIVITY_DAYS + 365),
        profile_computed_at=now - timedelta(days=INACTIVITY_DAYS + 365),
        membership_no="V000003",
    )

    res = await purge_inactive_taste_profiles(session, dry_run=True)

    assert res["candidate_count"] == 1
    assert res["deleted_count"] == 0
    assert res["dry_run"] is True

    # Le profil est toujours là
    remaining = (await session.execute(select(CustomerTasteProfile))).scalars().all()
    assert len(remaining) == 1


@pytest.mark.anyio
async def test_no_loyalty_tx_recent_profile_kept(session):
    """Profil tout neuf, jamais de tx loyalty → conservé (pas de purge prématurée)."""
    now = datetime.now(timezone.utc)
    await _add_client_with_loyalty(
        session,
        last_tx_at=None,
        profile_computed_at=now - timedelta(days=15),
        membership_no="V000004",
    )

    res = await purge_inactive_taste_profiles(session, dry_run=False)
    await session.commit()

    assert res["deleted_count"] == 0


@pytest.mark.anyio
async def test_no_loyalty_tx_old_profile_purged(session):
    """Profil ancien sans aucune tx loyalty → purgé après 24 mois."""
    now = datetime.now(timezone.utc)
    await _add_client_with_loyalty(
        session,
        last_tx_at=None,
        profile_computed_at=now - timedelta(days=INACTIVITY_DAYS + 1),
        membership_no="V000005",
    )

    res = await purge_inactive_taste_profiles(session, dry_run=False)
    await session.commit()

    assert res["deleted_count"] == 1


@pytest.mark.anyio
async def test_mixed_population_purges_only_inactive(session):
    """Mélange actif/inactif/tout neuf → ne purge que les inactifs ≥ 24 mois."""
    now = datetime.now(timezone.utc)
    # Active
    await _add_client_with_loyalty(
        session, now - timedelta(days=10),
        now - timedelta(days=10), "V000010",
    )
    # Inactive — purge attendue
    await _add_client_with_loyalty(
        session, now - timedelta(days=INACTIVITY_DAYS + 60),
        now - timedelta(days=INACTIVITY_DAYS + 60), "V000011",
    )
    # Toute fraîche, jamais de tx
    await _add_client_with_loyalty(
        session, None, now - timedelta(days=2), "V000012",
    )

    res = await purge_inactive_taste_profiles(session, dry_run=False)
    await session.commit()

    assert res["deleted_count"] == 1
    remaining = (
        await session.execute(select(CustomerTasteProfile))
    ).scalars().all()
    assert len(remaining) == 2


@pytest.mark.anyio
async def test_orphan_profiles_removed(session):
    """Un profil sans Client correspondant → supprimé par purge_orphan."""
    # Cliente présente
    c = _client("Réelle")
    session.add(c)
    await session.flush()
    session.add(CustomerTasteProfile(
        customer_id=c.id, n_purchases_analyzed=2,
        computed_at=datetime.now(timezone.utc),
    ))
    # Profil orphelin — on supprime la cliente derrière son dos
    import uuid as _uuid
    orphan_id = _uuid.uuid4()
    session.add(CustomerTasteProfile(
        customer_id=orphan_id, n_purchases_analyzed=1,
        computed_at=datetime.now(timezone.utc),
    ))
    await session.flush()

    removed = await purge_orphan_taste_profiles(session)
    await session.commit()

    assert removed == 1
    remaining = (
        await session.execute(select(CustomerTasteProfile))
    ).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].customer_id == c.id


@pytest.mark.anyio
async def test_orphan_purge_idempotent(session):
    """Pas d'orphelins → purge_orphan retourne 0 sans erreur."""
    removed = await purge_orphan_taste_profiles(session)
    assert removed == 0
