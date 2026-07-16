"""Visibility module — SEO snapshots, social posts, mentions, reviews
(P3-003 + P3-004 + P3-005).

Three concerns sit together because they share the admin /visibility
page:

- ``capture_seo_snapshot`` runs the same SEO health check the existing
  /api/seo/status endpoint does, but persists the result so the front
  can plot a 30-day evolution.
- ``generate_weekly_social_posts`` proposes 4 posts (one per category)
  for the current ISO week, optionally rewritten by Claude Haiku 4.5
  (with a deterministic fallback for offline / no-key scenarios).
- ``suggest_review_reply`` asks Claude for a personalised draft reply
  to a Google review; falls back to a polite stock template.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.visibility import (
    GoogleReview,
    SEOSnapshot,
    SocialPlatform,
    SocialPost,
    SocialPostCategory,
)

logger = logging.getLogger("vintiz.visibility")


SOCIAL_POSTS_PROMPT_VERSION = "v1.0-2026-04"
SOCIAL_POSTS_MODEL = "claude-haiku-4-5"


def iso_week_key(when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    year, week, _ = when.isocalendar()
    return f"{year}-W{week:02d}"


# ---------------------------------------------------------------------------
# SEO snapshots (P3-005)
# ---------------------------------------------------------------------------


async def capture_seo_snapshot(
    db: AsyncSession,
    *,
    site_url: str,
    score: int,
    response_ms: int | None,
    checks: list[dict],
) -> SEOSnapshot:
    """Persist a snapshot row. Caller is responsible for the live fetch."""
    row = SEOSnapshot(
        site_url=site_url,
        score=int(score),
        response_ms=response_ms,
        checks=checks,
        fetched_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row


async def list_recent_snapshots(
    db: AsyncSession, *, days: int = 30, limit: int = 200
) -> list[SEOSnapshot]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    result = await db.execute(
        select(SEOSnapshot)
        .where(SEOSnapshot.fetched_at >= cutoff)
        .order_by(SEOSnapshot.fetched_at.asc())
        .limit(min(max(limit, 1), 1000))
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Social post generation (P3-004)
# ---------------------------------------------------------------------------


# Prompt source : apps/api/prompts/v1/social_posts.md (T2 audit tech debt).
_SOCIAL_POSTS_FALLBACK = (
    "Tu es community manager de Vintiz Vernon. Génère 4 posts "
    "(produit_star, valeurs, témoignage, actu_locale) au format JSON. "
    "Référence le site vintiz.fr dans les captions, pas @vintiz.vernon."
)


def _system_prompt() -> str:
    from app.core.prompts import load_prompt

    return load_prompt(
        "social_posts",
        fallback=_SOCIAL_POSTS_FALLBACK,
    )


def _generate_fallback_posts() -> list[dict]:
    """Deterministic template used when Anthropic is unreachable."""
    return [
        {
            "category": "PRODUIT_STAR",
            "platform": "both",
            "caption": (
                "Coup de cœur de la semaine 🛍️ Une pièce dénichée chez Vintiz "
                "Vernon, à essayer en boutique aujourd'hui. Quantité unique. "
                "→ vintiz.fr"
            ),
            "hashtags": [
                "#vintiz", "#vintizvernon", "#vernon", "#secondemain",
                "#friperievernon", "#modecirculaire",
            ],
            "best_time": "12:00",
            "media_brief": (
                "Photo centrée d'une pièce 'Hot' du stock. Lumière naturelle, "
                "fond neutre, prix visible."
            ),
        },
        {
            "category": "VALEURS",
            "platform": "instagram",
            "caption": (
                "Chaque pièce qui revit chez nous, c'est une boucle bouclée : "
                "tri, sélection, mise en rayon — fait à Vernon par des "
                "personnes en parcours d'insertion. La mode peut faire ça. "
                "vintiz.fr"
            ),
            "hashtags": [
                "#vintiz", "#ESS", "#economiecirculaire", "#insertion",
                "#vernon", "#secondemainpremium",
            ],
            "best_time": "18:30",
            "media_brief": (
                "Photo équipe atelier de tri (avec accord) ou détail mains "
                "en train d'étiqueter une pièce."
            ),
        },
        {
            "category": "TEMOIGNAGE",
            "platform": "instagram",
            "caption": (
                "« J'ai trouvé chez Vintiz LA veste que je cherchais "
                "depuis des mois. » Merci Julie de Vernon 💚 Venez la "
                "trouver à votre tour. → vintiz.fr"
            ),
            "hashtags": [
                "#vintiz", "#vintizvernon", "#temoignage", "#vernon",
                "#friperie",
            ],
            "best_time": "19:00",
            "media_brief": (
                "Photo client·e (anonymisée si demandé) portant la pièce + "
                "second plan boutique."
            ),
        },
        {
            "category": "ACTU_LOCALE",
            "platform": "tiktok",
            "caption": (
                "Samedi marché de Vernon ☀️ Passez nous voir juste après — "
                "rue Saint-Jacques, ouvert 10h-19h. Toutes les nouveautés "
                "sur vintiz.fr"
            ),
            "hashtags": [
                "#vintiz", "#vernon", "#normandie", "#weekend",
            ],
            "best_time": "10:00",
            "media_brief": (
                "Plan extérieur boutique, ambiance samedi marché. "
                "Story-friendly."
            ),
        },
    ]


def _normalize_post_payload(raw: dict) -> dict | None:
    """Validate one Claude-generated post against the schema."""
    if not isinstance(raw, dict):
        return None
    try:
        category = SocialPostCategory(str(raw.get("category", "")).strip())
    except ValueError:
        return None
    try:
        platform = SocialPlatform(str(raw.get("platform", "both")).strip().lower())
    except ValueError:
        platform = SocialPlatform.both
    caption = str(raw.get("caption", "")).strip()
    if not caption:
        return None
    hashtags = raw.get("hashtags") or []
    if not isinstance(hashtags, list):
        hashtags = []
    hashtags = [
        h if h.startswith("#") else f"#{h}"
        for h in (str(x).strip() for x in hashtags)
        if h
    ]
    best_time = str(raw.get("best_time", "")).strip() or None
    if best_time and not re.match(r"^\d{1,2}:\d{2}$", best_time):
        best_time = None
    media_brief = str(raw.get("media_brief", "")).strip() or None
    return {
        "category": category,
        "platform": platform,
        "caption": caption,
        "hashtags": hashtags[:8],
        "best_time": best_time,
        "media_brief": media_brief,
    }


async def _ask_claude_for_posts() -> list[dict] | None:
    """Call Claude Haiku for 4 posts. Returns None on any failure."""
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=SOCIAL_POSTS_MODEL,
            max_tokens=1024,
            system=_system_prompt(),
            messages=[{
                "role": "user",
                "content": (
                    "Génère les 4 posts de la semaine pour Vintiz Vernon "
                    "(1 par catégorie obligatoire). Réponds en JSON strict."
                ),
            }],
        )
        text = message.content[0].text if message.content else ""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.endswith("```"):
                text = text[:-3].strip()
        payload = json.loads(text)
        posts = payload.get("posts") if isinstance(payload, dict) else None
        if not isinstance(posts, list):
            return None
        normalized = [
            n for n in (_normalize_post_payload(p) for p in posts) if n
        ]
        # Require all 4 categories — otherwise we don't trust the output.
        seen = {p["category"] for p in normalized}
        if seen != set(SocialPostCategory):
            return None
        return normalized
    except Exception as exc:
        logger.warning("Claude social posts call failed: %s", exc)
        return None


async def generate_weekly_social_posts(
    db: AsyncSession,
    *,
    when: datetime | None = None,
    user_id=None,
) -> list[SocialPost]:
    """Replace the SocialPost rows for the running ISO week with a fresh
    set. Tries Claude Haiku 4.5 first; deterministic fallback otherwise."""
    iso_week = iso_week_key(when)

    # Drop any prior proposal for this week so we don't accumulate
    # half-edited drafts across regenerations.
    existing_rows = await db.execute(
        select(SocialPost).where(SocialPost.iso_week == iso_week)
    )
    for row in existing_rows.scalars().all():
        await db.delete(row)
    await db.flush()

    posts_payload = await _ask_claude_for_posts()
    used_llm = posts_payload is not None
    if not posts_payload:
        posts_payload = [
            _normalize_post_payload(p) for p in _generate_fallback_posts()
        ]
        posts_payload = [p for p in posts_payload if p]

    rows: list[SocialPost] = []
    for entry in posts_payload:
        row = SocialPost(
            iso_week=iso_week,
            category=entry["category"],
            platform=entry["platform"],
            caption=entry["caption"],
            hashtags=entry["hashtags"],
            best_time=entry["best_time"],
            media_brief=entry["media_brief"],
            used_llm=used_llm,
        )
        db.add(row)
        rows.append(row)
    await db.flush()
    return rows


async def list_current_week_posts(
    db: AsyncSession, *, when: datetime | None = None
) -> list[SocialPost]:
    iso_week = iso_week_key(when)
    result = await db.execute(
        select(SocialPost)
        .where(SocialPost.iso_week == iso_week)
        .order_by(SocialPost.created_at.asc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Reviews + mentions (P3-003)
# ---------------------------------------------------------------------------


def suggest_review_reply_fallback(review: GoogleReview) -> str:
    """Polite stock template when Claude isn't available."""
    if review.rating >= 4:
        return (
            f"Merci beaucoup {review.author or 'beaucoup'} pour votre retour ! "
            "Votre confiance nous touche. Au plaisir de vous revoir bientôt "
            "en boutique. — L'équipe Vintiz"
        )
    return (
        f"Bonjour {review.author or ''}, merci d'avoir pris le temps de nous "
        "écrire. Nous prenons votre retour très au sérieux et aimerions en "
        "discuter — pouvez-vous nous écrire à contact@vintiz.fr ? "
        "— L'équipe Vintiz"
    )


async def suggest_review_reply(review: GoogleReview) -> tuple[str, bool]:
    """Generate a draft reply to a Google review.

    Returns (text, used_llm). When the API isn't available we fall back
    to a stock template so Camille still has a starting point.
    """
    if not settings.ANTHROPIC_API_KEY or not review.text:
        return suggest_review_reply_fallback(review), False
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=SOCIAL_POSTS_MODEL,
            max_tokens=400,
            system=(
                "Tu rédiges la réponse de Vintiz Vernon (boutique seconde "
                "main premium ESS) à un avis Google. Ton chaleureux, "
                "professionnel, vouvoiement, 3-5 phrases max. Si l'avis est "
                "négatif, propose un échange par email contact@vintiz.fr. "
                "N'utilise jamais l'ancien nom 'Frip & Co'."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Note: {review.rating}/5\n"
                    f"Auteur: {review.author or 'Client·e Google'}\n"
                    f"Avis:\n{review.text}\n\n"
                    "Rédige la réponse Vintiz."
                ),
            }],
        )
        text = message.content[0].text if message.content else ""
        text = text.strip() or suggest_review_reply_fallback(review)
        return text, True
    except Exception as exc:
        logger.warning("Claude review reply failed: %s", exc)
        return suggest_review_reply_fallback(review), False
