"""Tests for the customer qualification service (Personal Shopper 360 — V2)."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base
from app.models.client import (
    Client,
    Consent,
    ConsentPurpose,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.embeddings import CustomerTasteProfile, ProductEmbedding
from app.models.events import EventLog
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Gender, Product, ProductPhoto, ProductStatus
from app.models.user import User, UserRole
from app.services.customer_qualification import (
    classify_season,
    compute_qualification,
    score_atypie,
)
from app.services.embeddings import EmbeddingService


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
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        ProductEmbedding.__table__,
        CustomerTasteProfile.__table__,
        EventLog.__table__,
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


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


async def _make_user(session: AsyncSession) -> User:
    u = User(
        username=f"staff-{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:6]}@vintiz.fr",
        password_hash="x" * 60,
        role=UserRole.collaborateur,
        is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


async def _make_client(
    session: AsyncSession, *, email: str = "julie@example.com", consent: bool = True,
    gender_profile: str | None = None,
) -> Client:
    c = Client(first_name="Julie", last_name="Martin", email=email, gender_profile=gender_profile)
    session.add(c)
    await session.flush()
    if consent:
        session.add(
            Consent(
                client_id=c.id,
                purpose=ConsentPurpose.profiling,
                granted=True,
                policy_version="v2",
                source="test",
            )
        )
        await session.flush()
    return c


async def _make_product(
    session: AsyncSession,
    *,
    name: str,
    category_name: str = "Robes",
    price: float = 50.0,
    trend: float | None = 60.0,
    gender: Gender | None = None,
) -> Product:
    cat = (
        await session.execute(select(Category).where(Category.name == category_name))
    ).scalar_one_or_none()
    if cat is None:
        cat = Category(name=category_name)
        session.add(cat)
        await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name=name,
        category_id=cat.id,
        sale_price=price,
        trend_score=trend,
        gender=gender,
        status=ProductStatus.display,
    )
    session.add(p)
    await session.flush()
    return p


async def _purchase(
    session: AsyncSession,
    user: User,
    client: Client,
    product: Product,
    *,
    is_gift: bool = False,
    unit_price: float | None = None,
) -> Transaction:
    price = unit_price if unit_price is not None else float(product.sale_price)
    tx = Transaction(
        transaction_number=int(uuid.uuid4().int % 1_000_000_000),
        transaction_type=TransactionType.sale,
        user_id=user.id,
        client_id=client.id,
        total_ht=0,
        total_tva=0,
        total_ttc=price,
        hash_chain="x",
        is_gift=is_gift,
        exclude_from_taste=is_gift,
        created_at=datetime.now(timezone.utc),
    )
    session.add(tx)
    await session.flush()
    session.add(
        TransactionItem(
            transaction_id=tx.id,
            product_id=product.id,
            quantity=1,
            unit_price=price,
            discount_percent=0,
            line_total=price,
        )
    )
    await session.flush()
    return tx


# --------------------------------------------------------------------------- #
# season heuristic
# --------------------------------------------------------------------------- #


def test_classify_season_keywords():
    assert classify_season("Manteau en laine") == "winter"
    assert classify_season("Short en lin") == "summer"
    assert classify_season("Chemise en coton") is None


# --------------------------------------------------------------------------- #
# compute_qualification
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_qualification_requires_profiling_consent(session):
    user = await _make_user(session)
    client = await _make_client(session, consent=False)
    p = await _make_product(session, name="Manteau laine", price=80.0)
    await _purchase(session, user, client, p)

    result = await compute_qualification(session, client.id)
    assert result is None
    assert client.season_bias is None  # nothing written without consent


@pytest.mark.anyio
async def test_qualification_computes_and_persists_signals(session):
    user = await _make_user(session)
    client = await _make_client(session)
    # Three winter pieces at spread prices, high trend scores.
    await _purchase(session, user, client, await _make_product(
        session, name="Manteau laine", category_name="Manteaux", price=120.0, trend=80.0))
    await _purchase(session, user, client, await _make_product(
        session, name="Pull cachemire", category_name="Pulls", price=60.0, trend=70.0))
    await _purchase(session, user, client, await _make_product(
        session, name="Bottes cuir", category_name="Chaussures", price=90.0, trend=60.0))

    result = await compute_qualification(session, client.id)
    assert result is not None
    assert result["season_bias"] == "winter"
    assert client.season_bias == "winter"
    assert client.price_ceiling_cents is not None and client.price_ceiling_cents > 0
    assert 0.0 <= client.price_sensitivity <= 1.0
    # trend_affinity = mean(80,70,60)/100 = 0.70
    assert client.trend_affinity == pytest.approx(0.70, abs=0.01)


@pytest.mark.anyio
async def test_qualification_excludes_gifts(session):
    user = await _make_user(session)
    client = await _make_client(session)
    # Two real summer buys + one winter GIFT — season should resolve to summer.
    await _purchase(session, user, client, await _make_product(
        session, name="Short lin", category_name="Shorts", price=30.0))
    await _purchase(session, user, client, await _make_product(
        session, name="Sandales cuir", category_name="Chaussures", price=45.0))
    await _purchase(session, user, client, await _make_product(
        session, name="Manteau laine", category_name="Manteaux", price=150.0),
        is_gift=True)

    result = await compute_qualification(session, client.id)
    assert result is not None
    assert result["season_bias"] == "summer"


# --------------------------------------------------------------------------- #
# taste profile excludes gifts (embeddings)
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_taste_profile_skips_gift_only_history(session):
    user = await _make_user(session)
    client = await _make_client(session)
    p = await _make_product(session, name="Robe noire")
    await EmbeddingService(session).compute_for_product(p)
    await _purchase(session, user, client, p, is_gift=True)

    profile = await EmbeddingService(session).recompute_taste_profile(client.id)
    assert profile is None  # the only purchase is a gift → excluded


# --------------------------------------------------------------------------- #
# atypie
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_score_atypie_flags_gender_mismatch(session):
    user = await _make_user(session)
    client = await _make_client(session, gender_profile="femme")
    # She has bought a women's dress before.
    await _purchase(session, user, client, await _make_product(
        session, name="Robe", category_name="Robes", gender=Gender.femme))

    mens_suit = await _make_product(
        session, name="Costume homme", category_name="Costumes", gender=Gender.homme)
    result = await score_atypie(session, client.id, mens_suit)
    assert result["ask"] is True
    assert result["atypie"] >= 0.5
    assert any("genre" in r for r in result["reasons"])
