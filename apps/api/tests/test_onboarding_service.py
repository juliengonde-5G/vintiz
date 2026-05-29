"""Tests for the layered onboarding service (Personal Shopper 360 — V1).

Covers the three layers introduced by V1:
- Layer 1 — declarative ``gender`` + ``age_band`` persisted on the Client.
- Layer 2 — visual cold-start: liked product ids mean-pool into a real
  ``visual_centroid``.
- Layer 3 — detailed (styles / occasions / budget / brands) features.

Plus the picker helpers (``pick_visual_candidates``, ``list_available_brands``).
Runs against SQLite, like the other service tests.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base
from app.models.client import Client
from app.models.embeddings import CustomerTasteProfile, ProductEmbedding
from app.models.product import Category, Gender, Product, ProductPhoto, ProductStatus
from app.services.embeddings import EmbeddingService, _l2_normalize
from app.services.onboarding import (
    COLD_START_ALGO_VERSION,
    _features_from_choices,
    cold_start_taste_profile,
    list_available_brands,
    pick_visual_candidates,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        Category.__table__,
        Product.__table__,
        ProductPhoto.__table__,
        ProductEmbedding.__table__,
        Client.__table__,
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
# Helpers
# ---------------------------------------------------------------------------


async def _make_client(session: AsyncSession, email: str = "julie@example.com") -> Client:
    c = Client(first_name="Julie", last_name="Martin", email=email, avoir_credit=0)
    session.add(c)
    await session.flush()
    return c


async def _make_product(
    session: AsyncSession,
    *,
    name: str,
    category_name: str = "Robes",
    brand: str = "Sandro",
    gender: Gender | None = None,
    with_photo: bool = True,
    status: ProductStatus = ProductStatus.display,
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
        brand=brand,
        color="noir",
        size="M",
        sale_price=49.0,
        status=status,
        gender=gender,
        photo_url="https://img/photo.jpg" if with_photo else None,
    )
    session.add(p)
    await session.flush()
    return p


# ---------------------------------------------------------------------------
# Layer 1 — declarative gender + age band
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_layer1_only_persists_fields_without_centroid(session):
    """Submitting only genre/âge stores them on the Client and creates NO
    taste profile (we don't write an all-zero centroid)."""
    client = await _make_client(session)

    profile = await cold_start_taste_profile(
        session, client, gender="femme", age_band="35-44"
    )

    assert profile is None
    assert client.gender_profile == "femme"
    assert client.age_band == "35-44"
    rows = (
        await session.execute(
            select(CustomerTasteProfile).where(
                CustomerTasteProfile.customer_id == client.id
            )
        )
    ).scalars().all()
    assert rows == []


@pytest.mark.anyio
async def test_layer1_rejects_invalid_values(session):
    """Out-of-vocabulary genre/âge are ignored (defence in depth behind the
    API Literal validation)."""
    client = await _make_client(session)

    await cold_start_taste_profile(
        session, client, gender="alien", age_band="120+"
    )

    assert client.gender_profile is None
    assert client.age_band is None


# ---------------------------------------------------------------------------
# Layer 3 — declarative style features
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_layer3_styles_build_cold_start_centroid(session):
    client = await _make_client(session)

    profile = await cold_start_taste_profile(
        session, client, gender="femme", age_band="25-34",
        liked_style_keys=["chic"],
    )

    assert profile is not None
    assert profile.algo_version == COLD_START_ALGO_VERSION
    assert profile.n_purchases_analyzed == 0
    # Centroid is a real (non-zero, L2-normalised) vector.
    assert profile.visual_centroid is not None
    norm = sum(x * x for x in profile.visual_centroid) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-6)
    # Layer 1 still persisted alongside the centroid.
    assert client.gender_profile == "femme"


def test_layer3_brands_become_brand_features():
    feats = _features_from_choices([], None, None, None, ["Sandro", "Maje"])
    assert ("brand", "sandro") in feats
    assert ("brand", "maje") in feats


# ---------------------------------------------------------------------------
# Layer 2 — visual cold-start from real liked products
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_layer2_visual_centroid_is_mean_of_liked_embeddings(session):
    client = await _make_client(session)
    p1 = await _make_product(session, name="Robe noire", category_name="Robes")
    p2 = await _make_product(session, name="Pull gris", category_name="Pulls")

    emb = EmbeddingService(session)
    e1 = await emb.compute_for_product(p1)
    e2 = await emb.compute_for_product(p2)

    profile = await cold_start_taste_profile(
        session, client,
        gender="femme", age_band="25-34",
        liked_product_ids=[str(p1.id), str(p2.id)],
    )

    assert profile is not None
    expected = _l2_normalize(
        [e1.visual_embedding[i] + e2.visual_embedding[i] for i in range(len(e1.visual_embedding))]
    )
    for got, want in zip(profile.visual_centroid, expected):
        assert got == pytest.approx(want, abs=1e-6)


@pytest.mark.anyio
async def test_layer2_unknown_ids_fall_back_to_declarative(session):
    """Liked ids with no embeddings don't blow up — the declarative features
    still anchor the centroid."""
    client = await _make_client(session)

    profile = await cold_start_taste_profile(
        session, client,
        liked_style_keys=["vintage"],
        liked_product_ids=[str(uuid.uuid4())],  # no such product
    )

    assert profile is not None
    assert profile.visual_centroid is not None


# ---------------------------------------------------------------------------
# Visual candidate picker
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_pick_visual_candidates_filters_gender_and_photo(session):
    await _make_product(session, name="Robe femme", category_name="Robes", gender=Gender.femme)
    await _make_product(session, name="Costume homme", category_name="Costumes", gender=Gender.homme)
    await _make_product(session, name="Écharpe mixte", category_name="Accessoires", gender=Gender.mixte)
    await _make_product(session, name="Sac sans genre", category_name="Sacs", gender=None)
    # No photo → must be excluded entirely.
    await _make_product(session, name="Robe sans photo", category_name="Manteaux", gender=Gender.femme, with_photo=False)

    items = await pick_visual_candidates(session, gender="femme", n=8)
    names = {it["name"] for it in items}

    assert "Robe femme" in names      # femme kept
    assert "Écharpe mixte" in names   # mixte always kept
    assert "Sac sans genre" in names  # unset gender kept
    assert "Costume homme" not in names    # other gender excluded
    assert "Robe sans photo" not in names  # no photo excluded
    # Every returned candidate exposes a photo + price.
    for it in items:
        assert it["photo_url"]
        assert isinstance(it["price_cents"], int)


@pytest.mark.anyio
async def test_pick_visual_candidates_diversifies_by_category(session):
    await _make_product(session, name="Robe A", category_name="Robes")
    await _make_product(session, name="Robe B", category_name="Robes")
    await _make_product(session, name="Pull C", category_name="Pulls")

    items = await pick_visual_candidates(session, n=2)
    assert len(items) == 2
    # Two distinct categories preferred over two robes.
    assert {it["name"] for it in items} == {"Robe A", "Pull C"} or {
        it["name"] for it in items
    } == {"Robe B", "Pull C"}


@pytest.mark.anyio
async def test_list_available_brands_from_catalogue(session):
    await _make_product(session, name="Robe Sandro", brand="Sandro")
    await _make_product(session, name="Robe Sandro 2", brand="Sandro", category_name="Pulls")
    await _make_product(session, name="Sac Maje", brand="Maje", category_name="Sacs")

    brands = await list_available_brands(session)
    keys = [b["key"] for b in brands]
    assert "Sandro" in keys
    assert "Maje" in keys
    # Sandro (2 pieces) ranks before Maje (1 piece).
    assert keys.index("Sandro") < keys.index("Maje")
