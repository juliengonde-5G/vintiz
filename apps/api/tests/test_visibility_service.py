"""Tests for the visibility service (P3-003 + P3-004 + P3-005)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.user import User, UserRole
from app.models.visibility import (
    GoogleReview,
    SEOSnapshot,
    SocialMention,
    SocialPlatform,
    SocialPost,
    SocialPostCategory,
)
from app.services.visibility import (
    _generate_fallback_posts,
    _normalize_post_payload,
    capture_seo_snapshot,
    generate_weekly_social_posts,
    iso_week_key,
    list_current_week_posts,
    list_recent_snapshots,
    suggest_review_reply,
    suggest_review_reply_fallback,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        SEOSnapshot.__table__,
        SocialPost.__table__,
        SocialMention.__table__,
        GoogleReview.__table__,
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
    """Force the deterministic fallback path."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "ANTHROPIC_API_KEY", None)


# ---------------------------------------------------------------------------
# iso_week_key
# ---------------------------------------------------------------------------


def test_iso_week_key_format():
    when = datetime(2026, 4, 26, tzinfo=timezone.utc)  # Sunday → ISO 17
    assert iso_week_key(when) == "2026-W17"


# ---------------------------------------------------------------------------
# SEO snapshots (P3-005)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_capture_seo_snapshot_persists(session):
    snap = await capture_seo_snapshot(
        session,
        site_url="https://vintiz.fr",
        score=87,
        response_ms=420,
        checks=[{"name": "title", "passed": True, "detail": None}],
    )
    assert snap.id is not None
    assert snap.score == 87
    rows = (await session.execute(select(SEOSnapshot))).scalars().all()
    assert len(rows) == 1


@pytest.mark.anyio
async def test_list_recent_snapshots_filters_by_window(session):
    # Old snapshot (40 days ago) — out of the default 30-day window.
    old = SEOSnapshot(
        site_url="https://vintiz.fr", score=50, response_ms=300,
        checks=[], fetched_at=datetime.now(timezone.utc) - timedelta(days=40),
    )
    recent = SEOSnapshot(
        site_url="https://vintiz.fr", score=80, response_ms=200,
        checks=[], fetched_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    session.add_all([old, recent])
    await session.flush()

    rows = await list_recent_snapshots(session, days=30)
    ids = {r.id for r in rows}
    assert old.id not in ids
    assert recent.id in ids


@pytest.mark.anyio
async def test_list_recent_snapshots_orders_chronologically(session):
    base = datetime.now(timezone.utc) - timedelta(days=10)
    a = SEOSnapshot(
        site_url="x", score=70, response_ms=100, checks=[],
        fetched_at=base + timedelta(days=2),
    )
    b = SEOSnapshot(
        site_url="x", score=80, response_ms=100, checks=[],
        fetched_at=base + timedelta(days=5),
    )
    session.add_all([b, a])  # insert reverse to test ORDER BY
    await session.flush()

    rows = await list_recent_snapshots(session, days=30)
    assert rows[0].id == a.id
    assert rows[1].id == b.id


# ---------------------------------------------------------------------------
# Social posts (P3-004)
# ---------------------------------------------------------------------------


def test_fallback_posts_cover_all_4_categories():
    posts = _generate_fallback_posts()
    assert len(posts) == 4
    cats = {p["category"] for p in posts}
    assert cats == {"PRODUIT_STAR", "VALEURS", "TEMOIGNAGE", "ACTU_LOCALE"}


def test_normalize_post_payload_rejects_unknown_category():
    out = _normalize_post_payload({
        "category": "DANCE_OFF",
        "platform": "instagram",
        "caption": "test",
    })
    assert out is None


def test_normalize_post_payload_normalizes_hashtags():
    out = _normalize_post_payload({
        "category": "VALEURS",
        "platform": "instagram",
        "caption": "test",
        "hashtags": ["vintizvernon", "#vernon"],
    })
    assert out is not None
    assert out["hashtags"] == ["#vintizvernon", "#vernon"]


def test_normalize_post_payload_drops_invalid_best_time():
    out = _normalize_post_payload({
        "category": "VALEURS",
        "platform": "instagram",
        "caption": "test",
        "best_time": "later",
    })
    assert out is not None
    assert out["best_time"] is None


def test_normalize_post_payload_falls_back_platform_to_both():
    out = _normalize_post_payload({
        "category": "VALEURS",
        "platform": "myspace",
        "caption": "test",
    })
    assert out is not None
    assert out["platform"] == SocialPlatform.both


@pytest.mark.anyio
async def test_generate_weekly_social_posts_writes_4_rows(session):
    rows = await generate_weekly_social_posts(session)
    assert len(rows) == 4
    cats = {r.category for r in rows}
    assert cats == set(SocialPostCategory)
    assert all(r.used_llm is False for r in rows)  # fallback in tests


@pytest.mark.anyio
async def test_regenerate_replaces_previous_week(session):
    """A second generate_weekly_social_posts call within the same ISO
    week must wipe the prior set, not accumulate drafts."""
    first = await generate_weekly_social_posts(session)
    assert len(first) == 4
    second = await generate_weekly_social_posts(session)
    assert len(second) == 4
    rows = (await session.execute(select(SocialPost))).scalars().all()
    assert len(rows) == 4


@pytest.mark.anyio
async def test_list_current_week_posts(session):
    await generate_weekly_social_posts(session)
    posts = await list_current_week_posts(session)
    assert len(posts) == 4


@pytest.mark.anyio
async def test_distinct_iso_weeks_keep_their_proposals(session):
    """A proposal stamped for a different ISO week is NOT touched by
    the regeneration of the current week."""
    foreign = SocialPost(
        iso_week="1999-W01",
        category=SocialPostCategory.valeurs,
        platform=SocialPlatform.both,
        caption="historic",
        hashtags=[],
    )
    session.add(foreign)
    await session.flush()

    await generate_weekly_social_posts(session)
    rows = (await session.execute(
        select(SocialPost).where(SocialPost.iso_week == "1999-W01")
    )).scalars().all()
    assert len(rows) == 1  # the historic row survived


# ---------------------------------------------------------------------------
# Reviews (P3-003)
# ---------------------------------------------------------------------------


def test_review_reply_fallback_positive():
    review = GoogleReview(
        author="Camille",
        rating=5,
        text="Super boutique !",
        fetched_at=datetime.now(timezone.utc),
    )
    text = suggest_review_reply_fallback(review)
    assert "Camille" in text
    assert "@vintiz.fr" not in text  # positive review, no support escalation


def test_review_reply_fallback_negative():
    review = GoogleReview(
        author="Anonyme",
        rating=2,
        text="Déçu...",
        fetched_at=datetime.now(timezone.utc),
    )
    text = suggest_review_reply_fallback(review)
    # Negative replies always include the contact email so the customer
    # has a path back.
    assert "@vintiz.fr" in text


@pytest.mark.anyio
async def test_suggest_review_reply_uses_fallback_when_no_key(session):
    review = GoogleReview(
        author="Léa", rating=4, text="Très bien",
        fetched_at=datetime.now(timezone.utc),
    )
    session.add(review)
    await session.flush()
    text, used_llm = await suggest_review_reply(review)
    assert used_llm is False
    assert text  # non-empty
