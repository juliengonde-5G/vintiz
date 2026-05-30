"""Tests for the Personal Shopper v2 pipeline (P2-003)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    AvoirTransaction,
    Client,
    Consent,
    ConsentPurpose,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.embeddings import (
    CustomerTasteProfile,
    ProductEmbedding,
)
from app.models.events import EventLog, EventType
from app.models.pos import (
    Payment,
    Receipt,
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.store import StoreZone
from app.models.user import User, UserRole
from app.services.embeddings import EmbeddingService
from app.services.personal_shopper import (
    ALGO_VERSION,
    PersonalShopperService,
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
        Consent.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        Payment.__table__,
        Receipt.__table__,
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        AvoirTransaction.__table__,
        ProductEmbedding.__table__,
        CustomerTasteProfile.__table__,
        EventLog.__table__,
        StoreZone.__table__,
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


@pytest.fixture(autouse=True)
def _no_anthropic_key(monkeypatch):
    """Force the deterministic fallback path so tests don't need a real key."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "ANTHROPIC_API_KEY", None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_user(session: AsyncSession) -> User:
    u = User(
        username="staff",
        email="staff@vintiz.fr",
        password_hash="x" * 60,
        role=UserRole.collaborateur,
        is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


async def _make_client(session: AsyncSession, *, email: str = "julie@example.com") -> Client:
    c = Client(
        first_name="Julie",
        last_name="Martin",
        email=email,
        avoir_credit=0,
    )
    session.add(c)
    await session.flush()
    # Personal Shopper is members-only with explicit profiling consent (PR2
    # gating). Every test client is therefore a consenting loyalty member so
    # recommend() runs past _enforce_gating.
    session.add(
        LoyaltyAccount(
            client_id=c.id,
            points=0,
            membership_number=f"V{uuid.uuid4().int % 1_000_000:06d}",
        )
    )
    c.loyalty_subscribed_at = datetime.now(timezone.utc)
    c.loyalty_expires_at = datetime.now(timezone.utc) + timedelta(days=730)
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
    brand: str = "Sandro",
    color: str = "noir",
    size: str | None = "M",
    sale_price: float = 49.0,
    category_name: str = "Robes",
    status: ProductStatus = ProductStatus.display,
) -> Product:
    cat_result = await session.execute(
        select(Category).where(Category.name == category_name)
    )
    cat = cat_result.scalar_one_or_none()
    if cat is None:
        cat = Category(name=category_name)
        session.add(cat)
        await session.flush()
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name=name,
        category_id=cat.id,
        brand=brand,
        color=color,
        size=size,
        sale_price=sale_price,
        status=status,
    )
    session.add(p)
    await session.flush()
    return p


async def _record_purchase(
    session: AsyncSession,
    user: User,
    client: Client,
    product: Product,
    *,
    when: datetime | None = None,
) -> Transaction:
    tx = Transaction(
        transaction_number=int(uuid.uuid4().int % 1_000_000_000),
        transaction_type=TransactionType.sale,
        user_id=user.id,
        client_id=client.id,
        total_ht=0,
        total_tva=0,
        total_ttc=float(product.sale_price),
        hash_chain="x",
        created_at=when or datetime.now(timezone.utc),
    )
    session.add(tx)
    await session.flush()
    session.add(
        TransactionItem(
            transaction_id=tx.id,
            product_id=product.id,
            quantity=1,
            unit_price=float(product.sale_price),
            discount_percent=0,
            line_total=float(product.sale_price),
        )
    )
    await session.flush()
    return tx


async def _seed_minimal_history(session: AsyncSession) -> tuple[User, Client]:
    """Creates 1 user, 1 client, 1 past purchase + 4 candidate products
    (3 distinct categories) all with embeddings computed."""
    user = await _make_user(session)
    client = await _make_client(session)

    past = await _make_product(
        session, name="Robe Sandro classique",
        brand="Sandro", color="noir", size="M",
        category_name="Robes", status=ProductStatus.sold,
    )
    candidate_robe = await _make_product(
        session, name="Robe Sandro nouvelle",
        brand="Sandro", color="noir", size="M", category_name="Robes",
    )
    candidate_robe2 = await _make_product(
        session, name="Robe Maje",
        brand="Maje", color="noir", size="M", category_name="Robes",
    )
    candidate_pull = await _make_product(
        session, name="Pull Sandro",
        brand="Sandro", color="gris", size="M", category_name="Pulls",
    )
    candidate_sac = await _make_product(
        session, name="Sac Le Tanneur",
        brand="Le Tanneur", color="camel", size=None, category_name="Sacs",
    )

    emb = EmbeddingService(session)
    for p in (past, candidate_robe, candidate_robe2, candidate_pull, candidate_sac):
        await emb.compute_for_product(p)

    await _record_purchase(session, user, client, past)
    await emb.recompute_taste_profile(client.id)
    return user, client


# ---------------------------------------------------------------------------
# recommend()
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_recommend_returns_diversified_products(session):
    user, client = await _seed_minimal_history(session)
    svc = PersonalShopperService(session)
    result = await svc.recommend(client.id, top_n=4)

    assert len(result["products"]) <= 4
    assert len(result["products"]) >= 1
    # No two recommended products share the same category
    cats = {
        (await session.execute(
            select(Product.category_id).where(Product.id == uuid.UUID(p["id"]))
        )).scalar_one()
        for p in result["products"]
    }
    assert len(cats) == len(result["products"])
    assert result["algo_version"] == ALGO_VERSION
    assert result["fallback_used"] is True  # No key configured in tests
    assert result["recommendation_set_id"]


@pytest.mark.anyio
async def test_recommend_logs_one_event_per_product(session):
    user, client = await _seed_minimal_history(session)
    svc = PersonalShopperService(session)
    result = await svc.recommend(client.id, top_n=3)

    rows = (await session.execute(
        select(EventLog).where(
            EventLog.event_type == EventType.customer_recommendation_shown,
            EventLog.customer_id == client.id,
        )
    )).scalars().all()
    assert len(rows) == len(result["products"])
    # All events share the same recommendation_set_id (in session_id)
    set_ids = {r.session_id for r in rows}
    assert len(set_ids) == 1
    assert str(next(iter(set_ids))) == result["recommendation_set_id"]
    for row in rows:
        assert row.algo_version == ALGO_VERSION
        assert "score" in (row.meta or {})


@pytest.mark.anyio
async def test_recommend_fallback_message_references_past_purchase(session):
    user, client = await _seed_minimal_history(session)
    svc = PersonalShopperService(session)
    result = await svc.recommend(client.id)
    # Fallback template mentions the most recent purchase by name.
    assert "Robe Sandro classique" in result["message"]
    assert client.first_name in result["message"]


@pytest.mark.anyio
async def test_recommend_unknown_customer_raises_lookup(session):
    svc = PersonalShopperService(session)
    with pytest.raises(LookupError):
        await svc.recommend(uuid.uuid4())


# ---------------------------------------------------------------------------
# Cold start (no taste profile, no embeddings)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cold_start_returns_assumed_empty_state(session):
    """A profile-less customer gets the assumed empty state — NOT a generic
    newest-stock dump (PS 360 §3.2 / §5.2)."""
    user = await _make_user(session)
    client = await _make_client(session, email="newbie@example.com")

    await _make_product(session, name="Veste 1", category_name="Vestes")
    await _make_product(session, name="Robe 2", category_name="Robes")
    # No purchases, no embeddings, no taste profile → assumed empty state.

    svc = PersonalShopperService(session)
    result = await svc.recommend(client.id, top_n=4)

    assert result["fallback_used"] is True
    assert result["empty_state"] is True
    assert result["products"] == []  # we no longer pad with generic stock
    assert "Rien de neuf" in result["message"]
    assert client.first_name in result["message"]
    # cold_start does NOT log recommendation_shown events (we'd be biasing
    # the funnel with non-personalised data) — assert that.
    rows = (await session.execute(
        select(EventLog).where(
            EventLog.event_type == EventType.customer_recommendation_shown
        )
    )).scalars().all()
    assert rows == []


# ---------------------------------------------------------------------------
# Size filter
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_size_filter_keeps_unknown_size_candidates(session):
    """A candidate with size=None must not be discarded by the size filter."""
    user = await _make_user(session)
    client = await _make_client(session)

    bought = await _make_product(
        session, name="Robe M", size="M", category_name="Robes",
        status=ProductStatus.sold,
    )
    candidate_size_match = await _make_product(
        session, name="Robe M neuve", size="M", category_name="Robes",
    )
    candidate_no_size = await _make_product(
        session, name="Sac unique", size=None, category_name="Sacs",
    )
    candidate_size_off = await _make_product(
        session, name="Robe XS", size="XS", category_name="Robes",
    )

    emb = EmbeddingService(session)
    for p in (bought, candidate_size_match, candidate_no_size, candidate_size_off):
        await emb.compute_for_product(p)
    # Multiple purchases at size M so the filter actually engages.
    for _ in range(3):
        await _record_purchase(session, user, client, bought)
    await emb.recompute_taste_profile(client.id)

    svc = PersonalShopperService(session)
    result = await svc.recommend(client.id, top_n=5)

    names = {p["name"] for p in result["products"]}
    assert "Sac unique" in names  # Size unknown → kept
    # XS robe should be filtered out since the customer's preferred size is M
    assert "Robe XS" not in names


# ---------------------------------------------------------------------------
# record_click
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_record_click_emits_event(session):
    user, client = await _seed_minimal_history(session)
    svc = PersonalShopperService(session)
    result = await svc.recommend(client.id, top_n=2)
    set_id = uuid.UUID(result["recommendation_set_id"])
    product_id = uuid.UUID(result["products"][0]["id"])

    await svc.record_click(
        recommendation_set_id=set_id,
        product_id=product_id,
        customer_id=client.id,
        position_in_list=0,
    )

    rows = (await session.execute(
        select(EventLog).where(
            EventLog.event_type == EventType.customer_recommendation_clicked,
            EventLog.product_id == product_id,
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].session_id == set_id
    assert rows[0].customer_id == client.id
    assert rows[0].meta["position_in_list"] == 0


# ---------------------------------------------------------------------------
# Price contract (V0 — fix « NaN € » on the espace client cards)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_recommend_payload_exposes_price_cents_and_product_id(session):
    """The front reads ``price_cents`` + ``product_id``; both must be present
    and consistent so a card never renders ``NaN €``."""
    user, client = await _seed_minimal_history(session)
    svc = PersonalShopperService(session)
    result = await svc.recommend(client.id, top_n=4)

    assert result["products"]
    for p in result["products"]:
        assert isinstance(p["price_cents"], int)
        assert p["price_cents"] == round(p["sale_price"] * 100)
        assert p["product_id"] == p["id"]


# ---------------------------------------------------------------------------
# daily_picks() — « Pépites du jour » (V3)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_daily_picks_returns_picks_and_logs_event(session):
    user, client = await _seed_minimal_history(session)
    svc = PersonalShopperService(session)
    result = await svc.daily_picks(client.id, top_n=3)

    assert result["gated"] is None
    assert len(result["picks"]) >= 1
    for p in result["picks"]:
        assert "zone_name" in p  # key present even when None
        assert isinstance(p["price_cents"], int)
        assert p["product_id"] == p["id"]
    # One customer_picks_shown event per surfaced pick.
    rows = (await session.execute(
        select(EventLog).where(
            EventLog.event_type == EventType.customer_picks_shown,
            EventLog.customer_id == client.id,
        )
    )).scalars().all()
    assert len(rows) == len(result["picks"])


@pytest.mark.anyio
async def test_daily_picks_annotates_zone(session):
    user, client = await _seed_minimal_history(session)
    # Give one display product a physical zone.
    zone = StoreZone(name="Tendance — tête de gondole")
    session.add(zone)
    await session.flush()
    prod = (await session.execute(
        select(Product).where(Product.status == ProductStatus.display).limit(1)
    )).scalars().first()
    prod.zone_id = zone.id
    await session.flush()

    result = await PersonalShopperService(session).daily_picks(client.id, top_n=5)
    matching = [p for p in result["picks"] if p["id"] == str(prod.id)]
    assert matching and matching[0]["zone_name"] == "Tendance — tête de gondole"


@pytest.mark.anyio
async def test_daily_picks_gated_non_member_returns_cta(session):
    # A bare client with no loyalty + no consent.
    bare = Client(first_name="Non", last_name="Membre", email="bare@example.com")
    session.add(bare)
    await session.flush()

    result = await PersonalShopperService(session).daily_picks(bare.id)
    assert result["gated"] == "loyalty_required"
    assert result["cta"]
    assert result["picks"] == []


@pytest.mark.anyio
async def test_daily_picks_frequency_cap_excludes_recent(session):
    user, client = await _seed_minimal_history(session)
    svc = PersonalShopperService(session)
    first = await svc.daily_picks(client.id, top_n=2)
    ids1 = {p["id"] for p in first["picks"]}
    assert ids1
    second = await svc.daily_picks(client.id, top_n=2)
    ids2 = {p["id"] for p in second["picks"]}
    # The pieces shown <24h ago are not surfaced again (enough candidates exist).
    assert ids1.isdisjoint(ids2)


@pytest.mark.anyio
async def test_cold_start_empty_state_has_no_products(session):
    """The assumed empty state carries no products (so no price contract to
    honour) but flags ``empty_state`` for the front to render the wait."""
    client = await _make_client(session, email="cold@example.com")
    await _make_product(session, name="Veste neuve", category_name="Vestes")

    svc = PersonalShopperService(session)
    result = await svc.recommend(client.id, top_n=4)

    assert result["fallback_used"] is True
    assert result["empty_state"] is True
    assert result["products"] == []
