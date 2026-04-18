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
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import RoleChecker
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
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
