"""Tests for the monthly capsule service.

Couvre :
- la sélection des produits tendance (filtrée par statuts actifs)
- l'exclusion des produits vendus (``ProductStatus.sold``)
- le match événement par mot-clé sur catégorie / nom
- l'idempotence du regen (1 ligne par mois ISO)
- le fallback déterministe des pastilles (pas de clé Anthropic)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.audit import AuditLog, Settings
from app.models.capsule import MonthlyCapsule
from app.models.client import Client, LoyaltyAccount, LoyaltyTransaction
from app.models.pos import Payment, Receipt, Transaction, TransactionItem
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.user import User
from app.services import capsule as capsule_svc


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
        AuditLog.__table__,
        MonthlyCapsule.__table__,
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


async def _category(session, name: str) -> Category:
    c = Category(name=name)
    session.add(c)
    await session.flush()
    return c


async def _product(
    session,
    *,
    name: str = "Robe",
    status: ProductStatus = ProductStatus.displayed,
    trend_score: float | None = None,
    category: Category | None = None,
    color: str | None = None,
) -> Product:
    cat = category or await _category(session, "Robes")
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name=name,
        category_id=cat.id,
        sale_price=20.0,
        status=status,
        trend_score=trend_score,
        color=color,
    )
    session.add(p)
    await session.flush()
    return p


@pytest.mark.anyio
async def test_iso_month_key_formatting():
    when = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    assert capsule_svc.iso_month_key(when) == "2026-06"


@pytest.mark.anyio
async def test_trend_selection_picks_highest_score(session):
    cat = await _category(session, "Robes")
    high = await _product(session, name="Pièce A", trend_score=80.0, category=cat)
    mid = await _product(session, name="Pièce B", trend_score=55.0, category=cat)
    no_score = await _product(session, name="Pièce C", trend_score=None, category=cat)

    candidates = await capsule_svc._fetch_available_products(session)
    trend = capsule_svc._select_trend_products(candidates, k=2, min_score=50.0)
    ids = [p.id for p in trend]
    assert high.id in ids
    assert mid.id in ids
    assert no_score.id not in ids


@pytest.mark.anyio
async def test_sold_products_excluded_from_capsule(session):
    cat = await _category(session, "Robes")
    available = await _product(
        session, name="Robe rouge", trend_score=90.0, category=cat,
        status=ProductStatus.displayed,
    )
    sold = await _product(
        session, name="Robe vendue", trend_score=99.0, category=cat,
        status=ProductStatus.sold,
    )

    candidates = await capsule_svc._fetch_available_products(session)
    ids = [p.id for p in candidates]
    assert available.id in ids
    assert sold.id not in ids


@pytest.mark.anyio
async def test_event_match_by_category_keyword(session):
    # Mai → mots-clés ["foulard", "bijoux", "sac", ...]
    accessoires = await _category(session, "Foulards")
    robes = await _category(session, "Pulls")
    foulard = await _product(
        session, name="Foulard soie", category=accessoires, trend_score=40.0
    )
    pull = await _product(session, name="Pull oversize", category=robes, trend_score=40.0)

    candidates = await capsule_svc._fetch_available_products(session)
    event = capsule_svc.MONTH_EVENTS[5]
    matches = capsule_svc._select_event_products(candidates, event, k=5)
    ids = [p.id for p in matches]
    assert foulard.id in ids
    assert pull.id not in ids


@pytest.mark.anyio
async def test_build_proposal_yields_full_shape(session, monkeypatch):
    # Pas de clé Anthropic → on tombe sur le fallback déterministe.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    await _product(session, name="Robe", trend_score=85.0)

    when = datetime(2026, 5, 15, 8, 0, tzinfo=timezone.utc)
    proposal, used_llm = await capsule_svc.build_proposal(session, when=when)

    assert proposal["iso_month"] == "2026-05"
    assert proposal["event"]["name"].startswith("Fête des mères")
    assert isinstance(proposal["trend_products"], list)
    assert isinstance(proposal["event_products"], list)
    assert set(proposal["pastilles"].keys()) == {"colors", "watch_types", "gift_ideas"}
    # Sans clé API → fallback obligatoire.
    assert used_llm is False


@pytest.mark.anyio
async def test_regenerate_is_idempotent_per_month(session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    await _product(session, name="Pièce", trend_score=70.0)

    when = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
    first = await capsule_svc.regenerate_capsule(session, when=when)
    second = await capsule_svc.regenerate_capsule(session, when=when)
    assert first.id == second.id  # upsert sur iso_month, pas de doublon

    rows = (await session.execute(select(MonthlyCapsule))).scalars().all()
    assert len(rows) == 1
    assert rows[0].iso_month == "2026-06"
