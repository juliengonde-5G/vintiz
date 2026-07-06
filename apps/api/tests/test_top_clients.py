"""Tests Top Clients — GET /api/crm/clients/top (+ export CSV).

Couvre la porte d'auth au niveau HTTP (comme test_clients_full) et le
service ``top_clients`` sur SQLite en mémoire : fenêtrage calendaire,
CA = ventes − remboursements, exclusion des ventes anonymes et des
transactions void, jointure fidélité (n° carte + points), tri et limit.
"""

from datetime import datetime, timezone

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
from app.models.pos import (
    Payment,
    Receipt,
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.models.product import Category, Product, ProductPhoto
from app.models.user import User, UserRole
from app.services.cahier_service import EUROPE_PARIS
from app.services.top_clients import period_start, top_clients

# now fixe : mercredi 15/07/2026 midi Paris → day=15/07, week=lundi 13/07,
# month=01/07, year=01/01. Marges d'un jour et plus sur les seeds pour rester
# insensible au stockage naïf des datetimes par SQLite (±2 h vs Paris).
NOW = datetime(2026, 7, 15, 12, 0, tzinfo=EUROPE_PARIS)


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


def _tx(n, user, client, total, tx_type, created):
    return Transaction(
        transaction_number=n,
        transaction_type=tx_type,
        user_id=user.id,
        client_id=client.id if client else None,
        total_ttc=total,
        hash_chain="0" * 64,
        created_at=created,
    )


async def _seed(session):
    user = User(
        username="manager",
        email="m@v.fr",
        password_hash="x" * 60,
        role=UserRole.manager,
        is_active=True,
    )
    a = Client(first_name="Aline", last_name="Dupont")
    b = Client(first_name="Berthe", last_name="Martin")
    c = Client(first_name="Chloé", last_name="Durand")
    session.add_all([user, a, b, c])
    await session.flush()
    session.add(
        LoyaltyAccount(client_id=a.id, points=120, membership_number="V000001")
    )

    utc = timezone.utc
    sale, refund, void = (
        TransactionType.sale,
        TransactionType.refund,
        TransactionType.void,
    )
    session.add_all([
        # A : 100 + 50 − 30 de refund → 120 sur le mois, 20 sur la semaine
        _tx(1, user, a, 100.0, sale, datetime(2026, 7, 5, 10, 0, tzinfo=utc)),
        _tx(2, user, a, 50.0, sale, datetime(2026, 7, 14, 10, 0, tzinfo=utc)),
        _tx(3, user, a, 30.0, refund, datetime(2026, 7, 14, 11, 0, tzinfo=utc)),
        # void : jamais compté
        _tx(4, user, a, 400.0, void, datetime(2026, 7, 14, 12, 0, tzinfo=utc)),
        # B : 200 en début de mois (hors semaine courante)
        _tx(5, user, b, 200.0, sale, datetime(2026, 7, 3, 10, 0, tzinfo=utc)),
        # C : 500 en mars → visible sur l'année seulement
        _tx(6, user, c, 500.0, sale, datetime(2026, 3, 10, 10, 0, tzinfo=utc)),
        # Vente anonyme : hors classement
        _tx(7, user, None, 999.0, sale, datetime(2026, 7, 14, 10, 0, tzinfo=utc)),
    ])
    await session.flush()
    return a, b, c


@pytest.mark.anyio
async def test_month_ranking_revenue_and_loyalty(session):
    a, b, c = await _seed(session)
    data = await top_clients(session, period="month", limit=10, now=NOW)

    assert data["period"] == "month"
    assert data["count"] == 2
    first, second = data["results"]

    assert first["rank"] == 1
    assert first["client_id"] == str(b.id)
    assert first["revenue"] == 200.0
    assert first["loyalty_active"] is False
    assert first["membership_number"] is None
    assert first["loyalty_points"] == 0

    assert second["client_id"] == str(a.id)
    assert second["revenue"] == 120.0  # 150 de ventes − 30 de refund, void ignoré
    assert second["transactions_count"] == 2
    assert second["membership_number"] == "V000001"
    assert second["loyalty_points"] == 120


@pytest.mark.anyio
async def test_week_and_year_windows(session):
    a, b, c = await _seed(session)

    week = await top_clients(session, period="week", limit=10, now=NOW)
    assert [r["client_id"] for r in week["results"]] == [str(a.id)]
    assert week["results"][0]["revenue"] == 20.0

    year = await top_clients(session, period="year", limit=10, now=NOW)
    assert [r["client_id"] for r in year["results"]] == [
        str(c.id),
        str(b.id),
        str(a.id),
    ]
    assert year["results"][0]["revenue"] == 500.0


@pytest.mark.anyio
async def test_limit_truncates(session):
    a, b, c = await _seed(session)
    data = await top_clients(session, period="year", limit=1, now=NOW)
    assert data["count"] == 1
    assert data["results"][0]["client_id"] == str(c.id)


def test_period_start_boundaries():
    assert period_start("day", now=NOW) == datetime(
        2026, 7, 15, 0, 0, tzinfo=EUROPE_PARIS
    )
    assert period_start("week", now=NOW) == datetime(
        2026, 7, 13, 0, 0, tzinfo=EUROPE_PARIS
    )
    assert period_start("month", now=NOW) == datetime(
        2026, 7, 1, 0, 0, tzinfo=EUROPE_PARIS
    )
    assert period_start("year", now=NOW) == datetime(
        2026, 1, 1, 0, 0, tzinfo=EUROPE_PARIS
    )
    with pytest.raises(ValueError):
        period_start("quarter", now=NOW)


# ---------------------------------------------------------------------------
# Niveau HTTP — porte d'auth + routes câblées (pattern test_clients_full)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_top_endpoint_requires_auth(client):
    res = await client.get("/api/crm/clients/top?period=month&limit=10")
    assert res.status_code == 401
    res = await client.get("/api/crm/clients/top/export?period=month&limit=10")
    assert res.status_code == 401


@pytest.mark.anyio
async def test_top_routes_registered_before_client_id():
    """« top » ne doit pas être avalé par /clients/{client_id} (UUID).

    On passe par ``app.openapi()`` plutôt que ``app.routes`` : depuis
    FastAPI 0.139 ``include_router`` garde les sous-routers imbriqués
    (``_IncludedRouter`` sans ``.path``), alors que le schéma OpenAPI reste
    aplati et ordonné comme les déclarations dans les deux mondes.
    """
    from app.main import app

    paths = list(app.openapi()["paths"])
    assert "/api/crm/clients/top" in paths
    assert "/api/crm/clients/top/export" in paths
    assert paths.index("/api/crm/clients/top") < paths.index(
        "/api/crm/clients/{client_id}"
    )
