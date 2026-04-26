"""Tests for the embedding pipeline (P1-004)."""

import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import (
    AvoirTransaction,
    Client,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.embeddings import (
    EMBEDDING_DIM,
    CustomerTasteProfile,
    ProductEmbedding,
)
from app.models.pos import (
    Payment,
    Receipt,
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.user import User, UserRole
from app.services.embeddings import (
    ALGO_VERSION,
    EmbeddingService,
    _cosine,
    _encode_features,
    _l2_normalize,
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
        Transaction.__table__,
        TransactionItem.__table__,
        Payment.__table__,
        Receipt.__table__,
        LoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
        AvoirTransaction.__table__,
        ProductEmbedding.__table__,
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


# ---------------------------------------------------------------------------
# Encoder primitives
# ---------------------------------------------------------------------------


def test_l2_normalize_yields_unit_vector():
    out = _l2_normalize([3.0, 4.0])
    norm = math.sqrt(sum(x * x for x in out))
    assert abs(norm - 1.0) < 1e-9


def test_l2_normalize_handles_zero_vector():
    out = _l2_normalize([0.0, 0.0, 0.0])
    assert out == [0.0, 0.0, 0.0]


def test_encode_features_is_deterministic():
    a = _encode_features([("brand", "Hermes"), ("color", "noir")])
    b = _encode_features([("color", "noir"), ("brand", "Hermes")])
    # Same set of features → same vector regardless of order.
    assert a == b


def test_encode_features_yields_unit_norm_when_non_empty():
    vec = _encode_features([("brand", "Sandro"), ("color", "rouge")])
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-9
    assert len(vec) == EMBEDDING_DIM


def test_cosine_self_similarity_is_one_for_normalized():
    vec = _encode_features([("brand", "Maje"), ("color", "vert")])
    assert abs(_cosine(vec, vec) - 1.0) < 1e-9


def test_cosine_returns_zero_for_missing_vectors():
    assert _cosine(None, [1.0]) == 0.0
    assert _cosine([1.0], None) == 0.0
    # Mismatched dims → guarded with 0.0
    assert _cosine([1.0, 0.0], [1.0]) == 0.0


# ---------------------------------------------------------------------------
# Per-product compute
# ---------------------------------------------------------------------------


async def _make_product(
    session: AsyncSession,
    *,
    name: str = "Robe noire",
    brand: str = "Sandro",
    color: str = "noir",
    sale_price: float = 49.0,
    category_name: str = "Robes",
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
        sale_price=sale_price,
        status=ProductStatus.display,
    )
    session.add(p)
    await session.flush()
    return p


@pytest.mark.anyio
async def test_compute_for_product_writes_both_axes(session):
    p = await _make_product(session)
    row = await EmbeddingService(session).compute_for_product(p)

    assert row.product_id == p.id
    assert row.algo_version == ALGO_VERSION
    assert len(row.visual_embedding) == EMBEDDING_DIM
    assert len(row.text_embedding) == EMBEDDING_DIM
    # L2-normalised → roughly unit norm
    norm_v = math.sqrt(sum(x * x for x in row.visual_embedding))
    norm_t = math.sqrt(sum(x * x for x in row.text_embedding))
    assert abs(norm_v - 1.0) < 1e-9
    assert abs(norm_t - 1.0) < 1e-9


@pytest.mark.anyio
async def test_compute_for_product_updates_existing_row_in_place(session):
    p = await _make_product(session, brand="Sandro")
    svc = EmbeddingService(session)
    first = await svc.compute_for_product(p)
    first_visual = list(first.visual_embedding)

    # Mutate the product → recompute should change the visual vector.
    p.brand = "Hermes"
    await session.flush()
    second = await svc.compute_for_product(p)
    assert second.visual_embedding != first_visual

    # And only one row exists for this product.
    rows = (await session.execute(
        select(ProductEmbedding).where(ProductEmbedding.product_id == p.id)
    )).scalars().all()
    assert len(rows) == 1


@pytest.mark.anyio
async def test_similar_products_are_close_in_visual_space(session):
    """Two products with the same brand+colour+price-bucket must score
    higher with each other than with an unrelated product."""
    a = await _make_product(session, brand="Sandro", color="noir", sale_price=49.0)
    b = await _make_product(session, brand="Sandro", color="noir", sale_price=52.0)
    c = await _make_product(session, brand="Kiabi", color="rose", sale_price=8.0)

    svc = EmbeddingService(session)
    ea = await svc.compute_for_product(a)
    eb = await svc.compute_for_product(b)
    ec = await svc.compute_for_product(c)

    sim_ab = _cosine(ea.visual_embedding, eb.visual_embedding)
    sim_ac = _cosine(ea.visual_embedding, ec.visual_embedding)
    assert sim_ab > sim_ac, f"sim(a,b)={sim_ab}, sim(a,c)={sim_ac}"


# ---------------------------------------------------------------------------
# Recompute all products
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_recompute_all_processes_active_products(session):
    await _make_product(session, name="A")
    await _make_product(session, name="B")
    # A 'returned' product should NOT be embedded (only stock/display/sold).
    p_returned = await _make_product(session, name="C")
    p_returned.status = ProductStatus.returned
    await session.flush()

    summary = await EmbeddingService(session).recompute_all_products()
    assert summary["scanned"] == 2
    assert summary["recomputed"] == 2
    assert summary["algo_version"] == ALGO_VERSION


@pytest.mark.anyio
async def test_recompute_only_missing_skips_up_to_date_rows(session):
    p = await _make_product(session)
    svc = EmbeddingService(session)
    await svc.compute_for_product(p)

    summary = await svc.recompute_all_products(only_missing=True)
    assert summary["scanned"] == 1
    assert summary["recomputed"] == 0


# ---------------------------------------------------------------------------
# Customer taste profile
# ---------------------------------------------------------------------------


async def _make_user_and_client(session: AsyncSession) -> tuple[User, Client]:
    user = User(
        username="staff",
        email="staff@vintiz.fr",
        password_hash="x" * 60,
        role=UserRole.collaborateur,
        is_active=True,
    )
    client = Client(
        first_name="Julie",
        last_name="Martin",
        email=f"julie-{uuid.uuid4().hex[:6]}@example.com",
        avoir_credit=0,
    )
    session.add_all([user, client])
    await session.flush()
    return user, client


async def _record_purchase(
    session: AsyncSession,
    user: User,
    client: Client,
    product: Product,
    *,
    when: datetime | None = None,
    qty: int = 1,
) -> Transaction:
    tx = Transaction(
        transaction_number=int(uuid.uuid4().int % 1_000_000_000),
        transaction_type=TransactionType.sale,
        user_id=user.id,
        client_id=client.id,
        total_ht=0,
        total_tva=0,
        total_ttc=float(product.sale_price) * qty,
        hash_chain="x",
        created_at=when or datetime.now(timezone.utc),
    )
    session.add(tx)
    await session.flush()
    session.add(
        TransactionItem(
            transaction_id=tx.id,
            product_id=product.id,
            quantity=qty,
            unit_price=float(product.sale_price),
            discount_percent=0,
            line_total=float(product.sale_price) * qty,
        )
    )
    await session.flush()
    return tx


@pytest.mark.anyio
async def test_recompute_taste_profile_returns_none_for_no_purchases(session):
    _, client = await _make_user_and_client(session)
    profile = await EmbeddingService(session).recompute_taste_profile(client.id)
    assert profile is None


@pytest.mark.anyio
async def test_recompute_taste_profile_aggregates_purchases(session):
    user, client = await _make_user_and_client(session)
    p1 = await _make_product(session, name="A")
    p2 = await _make_product(session, name="B")

    svc = EmbeddingService(session)
    await svc.compute_for_product(p1)
    await svc.compute_for_product(p2)

    await _record_purchase(session, user, client, p1)
    await _record_purchase(session, user, client, p2)

    profile = await svc.recompute_taste_profile(client.id)
    assert profile is not None
    assert profile.n_purchases_analyzed == 2
    assert len(profile.visual_centroid) == EMBEDDING_DIM
    norm = math.sqrt(sum(x * x for x in profile.visual_centroid))
    assert abs(norm - 1.0) < 1e-9
    assert profile.algo_version == ALGO_VERSION


@pytest.mark.anyio
async def test_recompute_taste_profile_updates_existing_row(session):
    user, client = await _make_user_and_client(session)
    p = await _make_product(session)
    svc = EmbeddingService(session)
    await svc.compute_for_product(p)
    await _record_purchase(session, user, client, p)

    first = await svc.recompute_taste_profile(client.id)
    assert first.n_purchases_analyzed == 1

    # Add a second purchase of a different product.
    p2 = await _make_product(session, brand="Hermes", color="rouge")
    await svc.compute_for_product(p2)
    await _record_purchase(session, user, client, p2)
    second = await svc.recompute_taste_profile(client.id)
    assert second.n_purchases_analyzed == 2

    # Only one taste profile row per customer.
    rows = (await session.execute(
        select(CustomerTasteProfile).where(
            CustomerTasteProfile.customer_id == client.id
        )
    )).scalars().all()
    assert len(rows) == 1


@pytest.mark.anyio
async def test_recent_purchases_weigh_more_in_centroid(session):
    """A purchase last week should pull the centroid more than one a year
    old. We verify by checking which of two opposite-style products is
    closer to the centroid."""
    user, client = await _make_user_and_client(session)
    sandro = await _make_product(session, brand="Sandro", color="noir")
    kiabi = await _make_product(session, brand="Kiabi", color="rose")
    svc = EmbeddingService(session)
    await svc.compute_for_product(sandro)
    await svc.compute_for_product(kiabi)

    # Old kiabi purchase (~1 year ago) and recent sandro purchase (today).
    await _record_purchase(
        session, user, client, kiabi,
        when=datetime.now(timezone.utc) - timedelta(days=365),
    )
    await _record_purchase(
        session, user, client, sandro,
        when=datetime.now(timezone.utc),
    )

    profile = await svc.recompute_taste_profile(client.id)
    sim_sandro = _cosine(
        profile.visual_centroid,
        (await session.execute(
            select(ProductEmbedding).where(ProductEmbedding.product_id == sandro.id)
        )).scalar_one().visual_embedding,
    )
    sim_kiabi = _cosine(
        profile.visual_centroid,
        (await session.execute(
            select(ProductEmbedding).where(ProductEmbedding.product_id == kiabi.id)
        )).scalar_one().visual_embedding,
    )
    assert sim_sandro > sim_kiabi


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_find_similar_products_ranks_by_combined_similarity(session):
    user, client = await _make_user_and_client(session)
    p_match = await _make_product(session, brand="Sandro", color="noir")
    p_meh = await _make_product(session, brand="Hermes", color="vert")
    p_off = await _make_product(session, brand="Kiabi", color="rose", sale_price=8.0)
    svc = EmbeddingService(session)
    for p in (p_match, p_meh, p_off):
        await svc.compute_for_product(p)

    await _record_purchase(session, user, client, p_match)
    profile = await svc.recompute_taste_profile(client.id)

    results = await svc.find_similar_products(profile, top_k=3)
    assert len(results) == 3
    assert results[0][0].id == p_match.id
    # Score is monotonically non-increasing
    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.anyio
async def test_find_similar_products_excludes_unavailable_statuses(session):
    user, client = await _make_user_and_client(session)
    p_in_stock = await _make_product(session)
    p_sold = await _make_product(session)
    p_sold.status = ProductStatus.sold
    await session.flush()

    svc = EmbeddingService(session)
    await svc.compute_for_product(p_in_stock)
    await svc.compute_for_product(p_sold)

    await _record_purchase(session, user, client, p_in_stock)
    profile = await svc.recompute_taste_profile(client.id)

    results = await svc.find_similar_products(profile, top_k=10)
    ids = [p.id for p, _ in results]
    assert p_in_stock.id in ids
    assert p_sold.id not in ids
