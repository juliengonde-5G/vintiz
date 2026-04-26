"""SEO health check and monitoring endpoints for the public site.

Performs lightweight HTTP fetches against the public landing page to verify:
- Sitemap, robots.txt accessibility
- Presence of critical SEO tags (title, meta description, canonical, OG, JSON-LD)
- Analytics marker presence
- Response time
"""
from __future__ import annotations

import asyncio
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import RoleChecker, get_current_user
from app.models.user import User

router = APIRouter(prefix="/seo", tags=["seo"])

manager_only = RoleChecker(["manager"])


class SEOCheck(BaseModel):
    name: str
    passed: bool
    detail: str | None = None


class SEOStatus(BaseModel):
    site_url: str
    ga_measurement_id: str | None
    google_site_verification_configured: bool
    checks: list[SEOCheck]
    score: int  # 0..100
    fetched_at: str
    response_ms: int | None


async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[int | None, str | None, int | None]:
    start = time.perf_counter()
    try:
        resp = await client.get(url, timeout=5.0, follow_redirects=True)
        elapsed = int((time.perf_counter() - start) * 1000)
        return resp.status_code, resp.text, elapsed
    except Exception:
        return None, None, None


@router.get("/status", response_model=SEOStatus)
async def get_seo_status(
    current_user: Annotated[User, Depends(manager_only)],
) -> SEOStatus:
    site_url = settings.PUBLIC_SITE_URL.rstrip("/")
    checks: list[SEOCheck] = []

    async with httpx.AsyncClient() as client:
        (home_status, home_html, home_ms), (robots_status, robots_txt, _), (sitemap_status, sitemap_xml, _) = await asyncio.gather(
            _fetch(client, f"{site_url}/"),
            _fetch(client, f"{site_url}/robots.txt"),
            _fetch(client, f"{site_url}/sitemap.xml"),
        )

    html = home_html or ""

    checks.append(SEOCheck(
        name="Landing page accessible (200)",
        passed=home_status == 200,
        detail=f"HTTP {home_status}" if home_status else "Unreachable",
    ))
    checks.append(SEOCheck(
        name="robots.txt présent",
        passed=robots_status == 200,
        detail=f"HTTP {robots_status}" if robots_status else "Unreachable",
    ))
    checks.append(SEOCheck(
        name="sitemap.xml présent",
        passed=sitemap_status == 200,
        detail=f"HTTP {sitemap_status}" if sitemap_status else "Unreachable",
    ))
    checks.append(SEOCheck(
        name="Balise <title>",
        passed=bool(re.search(r"<title>[^<]{10,}</title>", html, re.IGNORECASE)),
        detail=_extract_first(r"<title>([^<]+)</title>", html),
    ))
    desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    checks.append(SEOCheck(
        name="Meta description",
        passed=bool(desc_match and len(desc_match.group(1)) >= 50),
        detail=(desc_match.group(1)[:160] + "…") if desc_match else None,
    ))
    canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    checks.append(SEOCheck(
        name="URL canonical",
        passed=bool(canonical_match),
        detail=canonical_match.group(1) if canonical_match else None,
    ))
    checks.append(SEOCheck(
        name="Open Graph (og:title)",
        passed=bool(re.search(r'property=["\']og:title["\']', html, re.IGNORECASE)),
    ))
    checks.append(SEOCheck(
        name="Données structurées JSON-LD",
        passed='application/ld+json' in html.lower(),
    ))
    checks.append(SEOCheck(
        name="Favicon déclaré",
        passed=bool(re.search(r'<link[^>]+rel=["\'](?:shortcut )?icon["\']', html, re.IGNORECASE)),
    ))
    checks.append(SEOCheck(
        name="Lang HTML = fr",
        passed=bool(re.search(r'<html[^>]+lang=["\']fr', html, re.IGNORECASE)),
    ))
    checks.append(SEOCheck(
        name="Google Analytics (GA4) détecté",
        passed='gtag/js?id=' in html or 'googletagmanager.com/gtag' in html,
        detail="Chargé après consentement (Consent Mode v2). Non détecté si pas encore accepté." if 'gtag' not in html else None,
    ))
    checks.append(SEOCheck(
        name="Clé GA configurée",
        passed=bool(settings.GA_MEASUREMENT_ID),
        detail=settings.GA_MEASUREMENT_ID if settings.GA_MEASUREMENT_ID else "NEXT_PUBLIC_GA_ID non défini",
    ))
    checks.append(SEOCheck(
        name="Vérification Search Console",
        passed=bool(settings.GOOGLE_SITE_VERIFICATION),
        detail="Configurée" if settings.GOOGLE_SITE_VERIFICATION else "NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION non défini",
    ))
    if sitemap_xml:
        url_count = sitemap_xml.count("<url>")
        checks.append(SEOCheck(
            name="URLs dans le sitemap",
            passed=url_count >= 1,
            detail=f"{url_count} URL(s)",
        ))
    if robots_txt and "Sitemap:" in robots_txt:
        checks.append(SEOCheck(
            name="robots.txt référence le sitemap",
            passed=True,
            detail=None,
        ))
    else:
        checks.append(SEOCheck(
            name="robots.txt référence le sitemap",
            passed=False,
            detail=None,
        ))

    passed_count = sum(1 for c in checks if c.passed)
    score = round(passed_count / len(checks) * 100) if checks else 0

    return SEOStatus(
        site_url=site_url,
        ga_measurement_id=settings.GA_MEASUREMENT_ID,
        google_site_verification_configured=bool(settings.GOOGLE_SITE_VERIFICATION),
        checks=checks,
        score=score,
        fetched_at=_now_iso(),
        response_ms=home_ms,
    )


def _extract_first(pattern: str, html: str) -> str | None:
    m = re.search(pattern, html, re.IGNORECASE)
    return m.group(1) if m else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===========================================================================
# P3-005 — Persisted SEO snapshots
# ===========================================================================


async def _run_seo_check_and_persist(db: AsyncSession) -> dict:
    """Shared core: live fetch + persistence. Used by both the manual
    endpoint and the daily cron."""
    from app.services.visibility import capture_seo_snapshot

    site_url = settings.PUBLIC_SITE_URL.rstrip("/")
    async with httpx.AsyncClient() as client:
        (home_status, home_html, home_ms), (robots_status, robots_txt, _), (sitemap_status, sitemap_xml, _) = await asyncio.gather(
            _fetch(client, f"{site_url}/"),
            _fetch(client, f"{site_url}/robots.txt"),
            _fetch(client, f"{site_url}/sitemap.xml"),
        )

    html = home_html or ""
    checks: list[dict] = [
        {
            "name": "Landing page accessible (200)",
            "passed": home_status == 200,
            "detail": f"HTTP {home_status}" if home_status else "Unreachable",
        },
        {
            "name": "robots.txt présent",
            "passed": robots_status == 200,
            "detail": f"HTTP {robots_status}" if robots_status else "Unreachable",
        },
        {
            "name": "sitemap.xml présent",
            "passed": sitemap_status == 200,
            "detail": f"HTTP {sitemap_status}" if sitemap_status else "Unreachable",
        },
        {
            "name": "Balise <title>",
            "passed": bool(re.search(r"<title>[^<]{10,}</title>", html, re.IGNORECASE)),
        },
        {
            "name": "Meta description",
            "passed": bool(re.search(
                r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{50,})["\']',
                html, re.IGNORECASE,
            )),
        },
        {
            "name": "Données structurées JSON-LD",
            "passed": "application/ld+json" in html.lower(),
        },
        {
            "name": "Open Graph (og:title)",
            "passed": bool(re.search(r'property=["\']og:title["\']', html, re.IGNORECASE)),
        },
    ]
    score = round(sum(1 for c in checks if c["passed"]) / len(checks) * 100)

    snapshot = await capture_seo_snapshot(
        db,
        site_url=site_url,
        score=score,
        response_ms=home_ms,
        checks=checks,
    )
    return {
        "id": str(snapshot.id),
        "score": snapshot.score,
        "fetched_at": snapshot.fetched_at.isoformat(),
        "response_ms": snapshot.response_ms,
    }


@router.post("/snapshots/run", dependencies=[Depends(manager_only)])
async def run_seo_snapshot(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Run the SEO health check and persist the result. Same checks as
    ``GET /api/seo/status`` but a row lands in ``seo_snapshots``."""
    payload = await _run_seo_check_and_persist(db)
    await db.commit()
    return payload


@router.get("/snapshots", dependencies=[Depends(manager_only)])
async def list_seo_snapshots(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 30,
):
    """Return SEO snapshots over the last ``days`` (default 30) for the
    evolution graph."""
    from app.services.visibility import list_recent_snapshots

    rows = await list_recent_snapshots(db, days=days)
    return [
        {
            "id": str(r.id),
            "site_url": r.site_url,
            "score": r.score,
            "response_ms": r.response_ms,
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            "checks": r.checks,
        }
        for r in rows
    ]


# ===========================================================================
# P3-004 — Social posts (calendrier éditorial)
# ===========================================================================


@router.get("/social-posts/current", dependencies=[Depends(manager_only)])
async def get_current_social_posts(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return the 4 social posts proposed for the current ISO week."""
    from app.services.visibility import iso_week_key, list_current_week_posts

    rows = await list_current_week_posts(db)
    return {
        "iso_week": iso_week_key(),
        "posts": [
            {
                "id": str(r.id),
                "category": r.category.value,
                "platform": r.platform.value,
                "caption": r.caption,
                "hashtags": r.hashtags or [],
                "best_time": r.best_time,
                "media_brief": r.media_brief,
                "used_llm": r.used_llm,
                "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None,
            }
            for r in rows
        ],
    }


@router.post("/social-posts/regenerate", dependencies=[Depends(manager_only)])
async def regenerate_social_posts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Force a fresh batch of 4 social posts for the running ISO week."""
    from app.services.visibility import generate_weekly_social_posts, iso_week_key

    rows = await generate_weekly_social_posts(db, user_id=current_user.id)
    await db.commit()
    return {
        "iso_week": iso_week_key(),
        "posts_count": len(rows),
        "used_llm": all(r.used_llm for r in rows),
    }


@router.post(
    "/social-posts/{post_id}/accept",
    dependencies=[Depends(manager_only)],
)
async def accept_social_post(
    post_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    from app.models.visibility import SocialPost

    result = await db.execute(
        select(SocialPost).where(SocialPost.id == post_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Post not found")
    row.accepted_at = datetime.now(timezone.utc)
    row.accepted_by_user_id = current_user.id
    await db.flush()
    await db.commit()
    return {"id": str(row.id), "accepted_at": row.accepted_at.isoformat()}


# ===========================================================================
# P3-003 — Mentions + Google reviews
# ===========================================================================


class MentionInput(BaseModel):
    platform: str  # instagram / tiktok / both
    source_url: str | None = None
    author: str | None = None
    text: str | None = None
    sentiment: float | None = None
    occurred_at: datetime | None = None


class ReviewInput(BaseModel):
    author: str | None = None
    rating: int
    text: str | None = None
    occurred_at: datetime | None = None


@router.get("/mentions", dependencies=[Depends(manager_only)])
async def list_mentions(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 30,
):
    from app.models.visibility import SocialMention

    cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(
        days=max(1, days)
    )
    result = await db.execute(
        select(SocialMention)
        .where(SocialMention.fetched_at >= cutoff)
        .order_by(desc(SocialMention.fetched_at))
        .limit(200)
    )
    return [
        {
            "id": str(r.id),
            "platform": r.platform.value,
            "source_url": r.source_url,
            "author": r.author,
            "text": r.text,
            "sentiment": r.sentiment,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
        }
        for r in result.scalars().all()
    ]


@router.post(
    "/mentions",
    dependencies=[Depends(manager_only)],
    status_code=http_status.HTTP_201_CREATED,
)
async def create_mention(
    request: MentionInput,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.visibility import SocialMention, SocialPlatform

    try:
        platform = SocialPlatform(request.platform.strip().lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="platform must be: " + ", ".join(p.value for p in SocialPlatform),
        )
    row = SocialMention(
        platform=platform,
        source_url=request.source_url,
        author=request.author,
        text=request.text,
        sentiment=request.sentiment,
        occurred_at=request.occurred_at,
        fetched_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    await db.commit()
    return {"id": str(row.id)}


@router.get("/reviews", dependencies=[Depends(manager_only)])
async def list_reviews(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 90,
):
    from app.models.visibility import GoogleReview

    cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(
        days=max(1, days)
    )
    result = await db.execute(
        select(GoogleReview)
        .where(GoogleReview.fetched_at >= cutoff)
        .order_by(desc(GoogleReview.occurred_at), desc(GoogleReview.fetched_at))
        .limit(200)
    )
    return [
        {
            "id": str(r.id),
            "author": r.author,
            "rating": r.rating,
            "text": r.text,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            "reply_text": r.reply_text,
            "replied_at": r.replied_at.isoformat() if r.replied_at else None,
        }
        for r in result.scalars().all()
    ]


@router.post(
    "/reviews",
    dependencies=[Depends(manager_only)],
    status_code=http_status.HTTP_201_CREATED,
)
async def create_review(
    request: ReviewInput,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.visibility import GoogleReview

    if not (1 <= request.rating <= 5):
        raise HTTPException(status_code=400, detail="rating must be 1..5")
    row = GoogleReview(
        author=request.author,
        rating=request.rating,
        text=request.text,
        occurred_at=request.occurred_at,
        fetched_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    await db.commit()
    return {"id": str(row.id), "rating": row.rating}


@router.post(
    "/reviews/{review_id}/suggest-reply",
    dependencies=[Depends(manager_only)],
)
async def suggest_review_reply_endpoint(
    review_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate a draft reply (Claude when available, fallback otherwise).
    Does NOT save it — Camille edits in the UI then posts via PUT /reply."""
    from app.models.visibility import GoogleReview
    from app.services.visibility import suggest_review_reply

    result = await db.execute(
        select(GoogleReview).where(GoogleReview.id == review_id)
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    text, used_llm = await suggest_review_reply(review)
    return {"draft": text, "used_llm": used_llm}


@router.put(
    "/reviews/{review_id}/reply",
    dependencies=[Depends(manager_only)],
)
async def set_review_reply(
    review_id: uuid.UUID,
    payload: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.visibility import GoogleReview

    text = (payload or {}).get("reply_text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="reply_text required")
    result = await db.execute(
        select(GoogleReview).where(GoogleReview.id == review_id)
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    review.reply_text = text
    review.replied_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    return {"id": str(review.id), "replied_at": review.replied_at.isoformat()}
