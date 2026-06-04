"""Capsule du mois — page éditoriale mensuelle.

Compose en une seule ressource :

- **Audience cible** dérivée du Personal Shopper
  (:func:`predictive_targeting.dominant_tastes_loyal_active`)
- **Produits tendance de la semaine** : pièces actives (en stock ou en rayon)
  rankées par ``trend_score`` décroissant
- **Produits événement** : pièces actives matchant les mots-clés du mois
  (mai → fête des mères, juin → fête des pères, etc.)
- **Pastilles d'information** : couleurs tendances, types à surveiller,
  idées cadeaux — générées par Claude Haiku via :func:`ai_router.call_with_routing`
  (avec repli déterministe si pas de clé API)

La capsule est persistée par mois ISO ("2026-06") via le modèle
:class:`MonthlyCapsule`. Le cron du 1er du mois (`jobs.run_monthly_capsule`)
upsert la ligne ; un endpoint admin permet aussi un regen manuel.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.capsule import MonthlyCapsule
from app.models.product import Product, ProductStatus
from app.services.predictive_targeting import (
    dominant_tastes_loyal_active,
    serialize_dominant,
)

logger = logging.getLogger("vintiz.capsule")


# Statuts considérés disponibles à la vente. Aligné sur ``store_ops_audit``
# (STOCK + FLOOR). On exclut volontairement ``sold``, ``returned``,
# ``donated`` et ``returned_to_sorting``.
AVAILABLE_STATUSES: tuple[ProductStatus, ...] = (
    ProductStatus.stock,
    ProductStatus.received,
    ProductStatus.sorted,
    ProductStatus.tagged,
    ProductStatus.display,
    ProductStatus.displayed,
    ProductStatus.discounted,
    ProductStatus.deep_discounted,
)


# Calendrier événementiel du commerce boutique (mois → événement principal +
# mots-clés catégorie/keywords utilisés pour filtrer le catalogue actif). Si
# un mois n'a pas d'entrée, la section "événement" est omise.
MONTH_EVENTS: dict[int, dict[str, Any]] = {
    1: {
        "name": "Soldes d'hiver",
        "keywords": ["pull", "manteau", "écharpe", "bottes"],
    },
    2: {
        "name": "Saint-Valentin",
        "keywords": ["robe", "bijoux", "lingerie", "rouge", "rose"],
    },
    3: {
        "name": "Printemps — Nouvelle collection",
        "keywords": ["robe", "blouse", "veste légère", "pastel"],
    },
    4: {
        "name": "Printemps fleuri",
        "keywords": ["robe", "blouse", "fleuri", "trench"],
    },
    5: {
        "name": "Fête des mères",
        "keywords": ["foulard", "bijoux", "sac", "robe", "maroquinerie"],
    },
    6: {
        "name": "Fête des pères + Été",
        "keywords": ["chemise", "polo", "sac", "lin", "blanc"],
    },
    7: {
        "name": "Soldes d'été",
        "keywords": ["robe", "short", "sandale", "maillot"],
    },
    8: {
        "name": "Été indien",
        "keywords": ["robe légère", "tunique", "panier", "lin"],
    },
    9: {
        "name": "Rentrée",
        "keywords": ["veste", "blazer", "sac à main", "cartable", "denim"],
    },
    10: {
        "name": "Automne",
        "keywords": ["pull", "veste", "bottines", "moutarde", "bordeaux"],
    },
    11: {
        "name": "Black Friday + Pré-Noël",
        "keywords": ["manteau", "pull", "écharpe", "cadeau"],
    },
    12: {
        "name": "Noël",
        "keywords": ["robe", "paillette", "rouge", "vert", "cadeau", "bijoux"],
    },
}


def iso_month_key(when: datetime | None = None) -> str:
    """Renvoie la clé ``YYYY-MM`` du mois courant en UTC."""
    when = when or datetime.now(timezone.utc)
    return f"{when.year:04d}-{when.month:02d}"


def _matches_event(product: Product, keywords: list[str]) -> bool:
    """Match texte simple (insensible casse) entre keywords et la fiche.

    On checke nom, description, catégorie, couleur. Pas de NLP — un keyword
    présent en sous-chaîne suffit. C'est une short-list, l'IA pastilles fait
    le reste du tri éditorial.
    """
    if not keywords:
        return False
    haystack_parts: list[str] = []
    if product.name:
        haystack_parts.append(product.name.lower())
    if product.description:
        haystack_parts.append(product.description.lower())
    if product.color:
        haystack_parts.append(product.color.lower())
    if product.category and product.category.name:
        haystack_parts.append(product.category.name.lower())
    haystack = " ".join(haystack_parts)
    for kw in keywords:
        if kw.lower() in haystack:
            return True
    return False


def _serialize_product(p: Product) -> dict[str, Any]:
    """Forme minimale carte produit pour l'UI capsule."""
    return {
        "id": str(p.id),
        "name": p.name,
        "brand": p.brand,
        "category": p.category.name if p.category else None,
        "color": p.color,
        "size": p.size,
        "price_eur": float(p.sale_price) if p.sale_price is not None else None,
        "photo_url": p.storefront_photo_url or p.photo_url,
        "trend_score": float(p.trend_score) if p.trend_score is not None else None,
    }


async def _fetch_available_products(
    db: AsyncSession, *, limit: int = 200
) -> list[Product]:
    """Fenêtre récente de pièces vendables — exclut tout produit non actif."""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.status.in_(AVAILABLE_STATUSES))
        .order_by(Product.trend_score.desc().nullslast(), Product.received_at.desc().nullslast())
        .limit(limit)
    )
    return list(result.scalars().all())


def _select_trend_products(
    candidates: list[Product], *, k: int = 6, min_score: float = 50.0
) -> list[Product]:
    """Top k pièces par ``trend_score``, en gardant les pièces sans score
    si on a trop peu de candidates au-dessus du seuil."""
    scored = [p for p in candidates if (p.trend_score or 0) >= min_score]
    scored.sort(key=lambda p: -(p.trend_score or 0))
    if len(scored) >= k:
        return scored[:k]
    fillers = [p for p in candidates if p not in scored]
    return scored + fillers[: max(0, k - len(scored))]


def _select_event_products(
    candidates: list[Product], event: dict[str, Any] | None, *, k: int = 6
) -> list[Product]:
    if not event:
        return []
    keywords = list(event.get("keywords") or [])
    matches = [p for p in candidates if _matches_event(p, keywords)]
    matches.sort(key=lambda p: -(p.trend_score or 0))
    return matches[:k]


# ---------------------------------------------------------------------------
# Pastilles éditoriales (Claude Haiku + fallback déterministe)
# ---------------------------------------------------------------------------


def _fallback_pastilles(month_event: dict[str, Any] | None) -> dict[str, list[dict]]:
    """Repli déterministe quand l'IA est indisponible (clé absente, erreur).

    Volontairement court et générique : c'est un filet de sécurité, pas
    une production éditoriale. Le manager peut toujours régénérer plus tard.
    """
    base_event_label = (month_event or {}).get("name") or "le mois"
    return {
        "colors": [
            {"name": "Crème", "hex": "#F1E9D9", "note": "Valeur sûre des cartes mode."},
            {"name": "Vert sauge", "hex": "#A4B894", "note": "Tendance prolongée."},
            {"name": "Terracotta", "hex": "#C77E5A", "note": "Bonne carte chez la 35-55."},
        ],
        "watch_types": [
            {"label": "Robes mi-longues", "note": "Forte rotation chez les fidèles."},
            {"label": "Sacs en cuir", "note": "Demande persistante au-dessus de 60 €."},
            {"label": "Foulards", "note": "Booster d'addition moyenne au POS."},
        ],
        "gift_ideas": [
            {
                "label": "Foulard en soie",
                "price_range": "15–35 €",
                "note": f"Cadeau {base_event_label} — boîte cadeau Vintiz incluse.",
            },
            {
                "label": "Bijou fantaisie",
                "price_range": "10–25 €",
                "note": "Petit prix, gros effet packaging.",
            },
            {
                "label": "Sac à main",
                "price_range": "30–80 €",
                "note": "Idéal cadeau premium si l'audience est haut-tier.",
            },
        ],
    }


async def _generate_pastilles_with_llm(
    db: AsyncSession,
    *,
    audience: dict,
    trend_products: list[dict],
    month_event: dict[str, Any] | None,
) -> tuple[dict[str, list[dict]], bool]:
    """Demande à Claude Haiku 3 sections JSON. Tuple (pastilles, used_llm)."""
    from app.services.ai_router import call_with_routing

    system = (
        "Tu es directeur artistique d'une boutique de seconde main premium à "
        "Vernon (Normandie). Tu réponds STRICTEMENT en JSON valide, sans "
        "texte avant ou après. Pas de markdown."
    )
    audience_summary = ", ".join(
        f"{c['name']}×{c['count']}"
        for c in (audience.get("top_categories") or [])[:5]
    ) or "audience non encore profilée"
    trend_summary = ", ".join(
        f"{p['name']}"
        for p in trend_products[:6]
    ) or "catalogue calme cette semaine"
    event_label = (month_event or {}).get("name") or "mois sans événement majeur"

    user = (
        f"Mois : {event_label}\n"
        f"Audience fidèle dominante : {audience_summary}\n"
        f"Tendance catalogue : {trend_summary}\n\n"
        "Produis un JSON :\n"
        '{\n'
        '  "colors":      [ 3 objets {"name":"…","hex":"#RRGGBB","note":"<20 mots"} ],\n'
        '  "watch_types": [ 3 objets {"label":"…","note":"<20 mots"} ],\n'
        '  "gift_ideas":  [ 3 objets {"label":"…","price_range":"X–Y €","note":"<20 mots"} ]\n'
        '}'
    )

    res = await call_with_routing(
        db,
        "monthly_capsule",
        user_message=user,
        system_message=system,
        max_tokens=900,
    )
    output = (res or {}).get("output_text") or ""
    if not output:
        return _fallback_pastilles(month_event), False
    # Robust JSON extract — strip ``` fences if présents.
    cleaned = output.strip()
    if cleaned.startswith("```"):
        # Drop first fence and any trailing ``` block.
        cleaned = cleaned.split("```", 2)[1] if "```" in cleaned[3:] else cleaned[3:]
        if cleaned.lstrip().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
        cleaned = cleaned.strip().rstrip("`").strip()
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Capsule LLM JSON parse failed: %s — output=%r", exc, output[:200])
        return _fallback_pastilles(month_event), False
    # Valide la forme : on attend 3 listes nommées.
    pastilles = {
        "colors": parsed.get("colors") or [],
        "watch_types": parsed.get("watch_types") or [],
        "gift_ideas": parsed.get("gift_ideas") or [],
    }
    if not (pastilles["colors"] and pastilles["watch_types"] and pastilles["gift_ideas"]):
        return _fallback_pastilles(month_event), False
    return pastilles, True


# ---------------------------------------------------------------------------
# Composition + persistance
# ---------------------------------------------------------------------------


async def build_proposal(
    db: AsyncSession, *, when: datetime | None = None
) -> tuple[dict[str, Any], bool]:
    """Compose le payload de capsule du mois (sans persister).

    Tuple (proposal, used_llm) — used_llm est vrai si les pastilles
    proviennent réellement de l'appel Claude (pas du fallback).
    """
    now = when or datetime.now(timezone.utc)
    month_event = MONTH_EVENTS.get(now.month)

    audience = serialize_dominant(
        await dominant_tastes_loyal_active(db, period_days=90, top_n=8)
    )

    candidates = await _fetch_available_products(db, limit=200)
    trend = _select_trend_products(candidates, k=6, min_score=50.0)
    event_products = _select_event_products(candidates, month_event, k=6)

    trend_payload = [_serialize_product(p) for p in trend]
    event_payload = [_serialize_product(p) for p in event_products]

    pastilles, used_llm = await _generate_pastilles_with_llm(
        db,
        audience=audience,
        trend_products=trend_payload,
        month_event=month_event,
    )

    proposal = {
        "iso_month": iso_month_key(now),
        "generated_at": now.replace(microsecond=0).isoformat(),
        "audience": audience,
        "event": (
            {
                "name": month_event["name"],
                "keywords": list(month_event.get("keywords") or []),
            }
            if month_event
            else None
        ),
        "trend_products": trend_payload,
        "event_products": event_payload,
        "pastilles": pastilles,
        "available_count": len(candidates),
    }
    return proposal, used_llm


async def get_or_create_current_capsule(
    db: AsyncSession, *, when: datetime | None = None
) -> MonthlyCapsule:
    """Renvoie la capsule du mois courant ; la crée si absente."""
    key = iso_month_key(when)
    existing = (
        await db.execute(
            select(MonthlyCapsule).where(MonthlyCapsule.iso_month == key)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    return await regenerate_capsule(db, when=when)


async def regenerate_capsule(
    db: AsyncSession, *, when: datetime | None = None
) -> MonthlyCapsule:
    """Recompose et upsert la capsule du mois courant.

    Le manager peut l'appeler depuis l'UI pour forcer un rafraîchissement
    (par ex. après avoir saisi de nouveaux produits ou changé un événement).
    """
    proposal, used_llm = await build_proposal(db, when=when)
    key = iso_month_key(when)

    existing = (
        await db.execute(
            select(MonthlyCapsule).where(MonthlyCapsule.iso_month == key)
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.proposal = proposal
        existing.used_llm = used_llm
        # Un regen explicite repart d'une validation vierge.
        existing.accepted_at = None
        existing.accepted_by_user_id = None
        await db.flush()
        return existing

    row = MonthlyCapsule(
        iso_month=key,
        proposal=proposal,
        used_llm=used_llm,
    )
    db.add(row)
    await db.flush()
    return row


def serialize_capsule(row: MonthlyCapsule) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "iso_month": row.iso_month,
        "proposal": row.proposal,
        "used_llm": row.used_llm,
        "accepted_at": row.accepted_at.isoformat() if row.accepted_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
