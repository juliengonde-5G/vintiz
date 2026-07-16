"""Tests for the cold-start onboarding service (P2-004)."""

import math

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import Client
from app.models.embeddings import (
    EMBEDDING_DIM,
    CustomerTasteProfile,
)
from app.services.onboarding import (
    COLD_START_ALGO_VERSION,
    STYLE_PROFILES,
    cold_start_taste_profile,
    list_available_occasions,
    list_available_price_buckets,
    list_available_style_profiles,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
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


async def _make_client(session: AsyncSession, *, email: str = "x@example.com") -> Client:
    c = Client(first_name="Julie", last_name="M", email=email, avoir_credit=0)
    session.add(c)
    await session.flush()
    return c


# ---------------------------------------------------------------------------
# Static catalogues
# ---------------------------------------------------------------------------


def test_style_profiles_catalogue_is_non_empty():
    styles = list_available_style_profiles()
    assert len(styles) >= 4
    assert all("key" in s and "label" in s for s in styles)
    keys = {s["key"] for s in styles}
    # The encoder must know every key returned by the picker.
    assert keys.issubset(set(STYLE_PROFILES.keys()))


def test_occasions_and_price_buckets_have_labels():
    for entry in list_available_occasions() + list_available_price_buckets():
        assert "key" in entry and "label" in entry


# ---------------------------------------------------------------------------
# Profile creation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_creates_a_unit_norm_visual_centroid(session):
    client = await _make_client(session)
    profile = await cold_start_taste_profile(
        session, client,
        liked_style_keys=["minimaliste"],
    )

    assert profile.customer_id == client.id
    assert profile.algo_version == COLD_START_ALGO_VERSION
    assert profile.n_purchases_analyzed == 0
    assert len(profile.visual_centroid) == EMBEDDING_DIM
    norm = math.sqrt(sum(x * x for x in profile.visual_centroid))
    assert abs(norm - 1.0) < 1e-9


@pytest.mark.anyio
async def test_re_running_overwrites_in_place(session):
    client = await _make_client(session)
    first = await cold_start_taste_profile(
        session, client, liked_style_keys=["chic"],
    )
    # Snapshot the centroid before the in-place update; ``first`` is the
    # same ORM row as ``second`` so reading .visual_centroid afterwards
    # returns the updated value.
    first_centroid = list(first.visual_centroid)
    first_id = first.id

    second = await cold_start_taste_profile(
        session, client, liked_style_keys=["sport"],
    )
    assert first_id == second.id
    assert first_centroid != list(second.visual_centroid)

    rows = (await session.execute(
        select(CustomerTasteProfile).where(
            CustomerTasteProfile.customer_id == client.id
        )
    )).scalars().all()
    assert len(rows) == 1


@pytest.mark.anyio
async def test_unknown_style_key_is_silently_ignored(session):
    client = await _make_client(session)
    profile = await cold_start_taste_profile(
        session, client,
        liked_style_keys=["minimaliste", "definitely-not-a-real-style"],
    )
    # The known key still produced a non-zero centroid.
    assert any(abs(x) > 1e-9 for x in profile.visual_centroid)


@pytest.mark.anyio
async def test_no_choices_at_all_yields_no_profile(session):
    """Edge case: an empty submission writes NO taste profile (PS 360 V1).

    We no longer persist an all-zero, useless centroid; the layered onboarding
    returns ``None`` when neither declarative styles nor visual likes are given,
    and the recommender falls back to its assumed empty state."""
    client = await _make_client(session)
    profile = await cold_start_taste_profile(
        session, client, liked_style_keys=[],
    )
    assert profile is None


@pytest.mark.anyio
async def test_distinct_styles_produce_distinct_centroids(session):
    a = await _make_client(session, email="a@example.com")
    b = await _make_client(session, email="b@example.com")
    pa = await cold_start_taste_profile(
        session, a, liked_style_keys=["chic"],
    )
    pb = await cold_start_taste_profile(
        session, b, liked_style_keys=["sport"],
    )
    assert pa.visual_centroid != pb.visual_centroid


@pytest.mark.anyio
async def test_quiz_answers_extend_the_feature_set(session):
    """Adding occasions / price buckets / categories changes the centroid
    — confirms the quiz isn't ignored."""
    client_a = await _make_client(session, email="just-style@example.com")
    base = await cold_start_taste_profile(
        session, client_a, liked_style_keys=["minimaliste"],
    )

    client_b = await _make_client(session, email="style-plus-quiz@example.com")
    enriched = await cold_start_taste_profile(
        session, client_b,
        liked_style_keys=["minimaliste"],
        preferred_occasions=["bureau"],
        preferred_price_buckets=["50-100"],
        preferred_categories=["Robes"],
    )
    assert enriched.visual_centroid != base.visual_centroid


@pytest.mark.anyio
async def test_invalid_quiz_values_are_dropped(session):
    """Garbage quiz inputs from a malicious payload don't pollute the
    encoder — they're silently filtered."""
    client = await _make_client(session)
    profile = await cold_start_taste_profile(
        session, client,
        liked_style_keys=["minimaliste"],
        preferred_occasions=["definitely_not_real"],
        preferred_price_buckets=["1e9"],
    )
    # Centroid still computed — those bad values just didn't add features.
    assert profile is not None
    assert profile.algo_version == COLD_START_ALGO_VERSION


@pytest.mark.anyio
async def test_n_purchases_analyzed_stays_zero(session):
    """Cold-start marker must remain visible so the daily cron knows it
    can replace this row with a real centroid."""
    client = await _make_client(session)
    profile = await cold_start_taste_profile(
        session, client, liked_style_keys=["chic"],
    )
    assert profile.n_purchases_analyzed == 0
