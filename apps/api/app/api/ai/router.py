"""AI Booster API endpoints.

Provides:
- Photo analysis (Claude Vision)
- Trend scoring
- Price suggestions
- Store mapping & recommendations
- Weekly checklist
- Fashion trends
- Persona marketing report
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.ai_task import AITask
from app.models.user import User
from app.models.product import Product, ProductStatus
from app.models.client import Client
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.audit import Settings
from app.models.store import StoreZone
from app.services.ai_vision import analyze_product_photo, analyze_photo_from_url
from app.services.ai_trend import compute_trend_scores, update_product_scores, get_stale_products
from app.services.ai_pricing import suggest_price
from app.services.ai_mapping import (
    init_default_zones,
    get_zone_stats,
    generate_arrangement_recommendations,
    assign_product_to_zone,
)


async def _get_setting(db: AsyncSession, key: str) -> str | None:
    result = await db.execute(select(Settings).where(Settings.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def _set_setting(db: AsyncSession, key: str, value: str) -> None:
    result = await db.execute(select(Settings).where(Settings.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(Settings(key=key, value=value))
    await db.flush()

router = APIRouter(prefix="/ai", tags=["ai-booster"])


# ---------------------------------------------------------------------------
# Vision: Photo Analysis
# ---------------------------------------------------------------------------

@router.post("/vision/analyze")
async def analyze_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Analyze a product photo using Claude Vision.

    Upload a photo and get back detected attributes:
    type, color, material, brand, size, condition, season, style, description.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Le fichier doit etre une image")

    image_data = await file.read()
    if len(image_data) > 20 * 1024 * 1024:  # 20MB safety net (tablet downscales first)
        raise HTTPException(status_code=400, detail="Image trop volumineuse (max 20 Mo)")

    media_type = file.content_type or "image/jpeg"

    try:
        result = await analyze_product_photo(image_data, media_type)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'analyse: {str(e)}")

    return result


@router.post("/vision/analyze-url")
async def analyze_photo_url(
    photo_url: str,
    current_user: User = Depends(get_current_user),
):
    """Analyze a product photo from URL using Claude Vision."""
    try:
        result = await analyze_photo_from_url(photo_url)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'analyse: {str(e)}")

    return result


# ---------------------------------------------------------------------------
# Trend Scoring
# ---------------------------------------------------------------------------

@router.get("/trends/scores")
async def get_trend_scores(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
):
    """Get trend scores for all active products, sorted by score descending."""
    scores = await compute_trend_scores(db)
    return scores[:limit]


@router.post("/trends/refresh")
async def refresh_trend_scores(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Recalculate and persist trend scores for all active products."""
    count = await update_product_scores(db)
    return {"message": f"Scores mis a jour pour {count} produits", "count": count}


@router.get("/trends/stale")
async def get_stale(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    weeks: int = Query(4, ge=1, le=52),
):
    """Get products that have been on shelf for more than N weeks."""
    products = await get_stale_products(db, weeks)
    return products


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

@router.post("/pricing/suggest")
async def suggest_product_price(
    category_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    purchase_price: float | None = None,
    brand: str | None = None,
    condition: str | None = None,
):
    """Suggest an optimal sale price for a product.

    ``purchase_price`` is now optional — Vintiz fonctionne en achat-revente
    sans saisie du prix d'achat côté caisse, donc la suggestion s'appuie
    sur la grille tarifaire (médiane catégorie) + le prix moyen vendu +
    marque + état quand ce paramètre est absent.
    """
    result = await suggest_price(db, category_id, purchase_price, brand, condition)
    return result


# ---------------------------------------------------------------------------
# Store Mapping
# ---------------------------------------------------------------------------

@router.post("/mapping/init-zones")
async def initialize_zones(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Initialize default store zones (Vintiz boutique layout)."""
    zones = await init_default_zones(db)
    return {"zones": zones, "count": len(zones)}


@router.get("/mapping/zones")
async def get_zones(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get all zones with occupancy stats."""
    stats = await get_zone_stats(db)
    return stats


@router.post("/mapping/assign")
async def assign_to_zone(
    product_id: str,
    zone_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Assign a product to a store zone."""
    result = await assign_product_to_zone(db, product_id, zone_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/mapping/recommendations")
async def get_recommendations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Generate AI-powered store arrangement recommendations."""
    try:
        result = await generate_arrangement_recommendations(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur IA: {str(e)}")
    return result


# ---------------------------------------------------------------------------
# Weekly Checklist
# ---------------------------------------------------------------------------

@router.get("/weekly-checklist")
async def get_weekly_checklist(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    force_refresh: bool = Query(False, description="Force regeneration even if cache is fresh"),
):
    """Return the weekly checklist. Generated by AI on Mondays, cached for the rest of the week."""
    now = datetime.now(timezone.utc)
    week = now.isocalendar()[1]
    year = now.year
    is_monday = now.weekday() == 0  # 0 = Monday

    # Return cached version unless it's Monday or forced
    if not is_monday and not force_refresh:
        cached = await _get_setting(db, "ai_checklist_cache")
        if cached:
            try:
                data = json.loads(cached)
                if data.get("week") == week and data.get("year") == year:
                    return data
            except (json.JSONDecodeError, KeyError):
                pass

    # Fetch 50 products with lowest trend scores
    low_score_result = await db.execute(
        select(Product)
        .where(Product.status.in_([ProductStatus.stock, ProductStatus.display]))
        .where(Product.trend_score.is_not(None))
        .order_by(Product.trend_score.asc())
        .limit(50)
    )
    low_score_products = low_score_result.scalars().all()

    # Fetch avg price per category (for relative pricing)
    avg_by_cat_result = await db.execute(
        select(Product.category_id, func.avg(Product.sale_price))
        .where(Product.status.in_([ProductStatus.stock, ProductStatus.display]))
        .group_by(Product.category_id)
    )
    avg_by_cat = {str(row[0]): float(row[1]) for row in avg_by_cat_result.all()}

    # Note prix : la politique boutique impose un prix correct dès la mise en
    # rayon (pas de markdown). Aucune routine de réduction de prix n'est
    # générée — le merchandising agit sur la visibilité, la rotation, la
    # composition de vitrine, mais jamais sur le tarif post-shelving.

    # Products to highlight (mid range score)
    mise_en_avant_products = [
        {
            "id": str(p.id),
            "name": p.name,
            "brand": p.brand,
            "sale_price": float(p.sale_price),
            "trend_score": p.trend_score,
        }
        for p in low_score_products[:10]
        if p.trend_score and 30 <= p.trend_score < 60
    ]

    checklist = [
        {
            "type": "mise_en_avant",
            "priority": "haute",
            "title": f"Mettre en avant {len(mise_en_avant_products)} produits a fort potentiel",
            "description": "Ces produits ont un score tendance modere mais pourraient se vendre davantage s'ils sont mieux visibles.",
            "products": mise_en_avant_products,
        },
        {
            "type": "vitrine",
            "priority": "haute",
            "title": "Reorganiser la vitrine cette semaine",
            "description": f"Semaine {week} — Privilegier les pieces colorees et les marques premium en vitrine pour maximiser l'attractivite.",
        },
        {
            "type": "publication_marketing",
            "priority": "haute",
            "title": "Publier le post Instagram de la semaine",
            "description": (
                "Le rapport marketing du lundi propose une publication hebdo (post Instagram + carrousel + "
                "story) autour d'une pièce hero de la boutique. Programmer la publication au créneau "
                "recommandé et préparer le visuel d'accompagnement."
            ),
            "deeplink": "/ia/marketing",
        },
        {
            "type": "commande",
            "priority": "faible",
            "title": "Anticiper les arrivages semaine prochaine",
            "description": "Verifier les niveaux de stock par categorie et contacter les fournisseurs si necessaire pour maintenir la variete.",
        },
    ]

    # Optionally enrich with Claude if API key is available
    anthropic_key = settings.ANTHROPIC_API_KEY or ""
    ai_summary = None
    if anthropic_key:
        try:
            import anthropic
            client_ai = anthropic.AsyncAnthropic(api_key=anthropic_key)
            product_summary = "\n".join(
                f"- {p['name']} (prix: {p['sale_price']}€, score: {p.get('trend_score', 'N/A')})"
                for p in mise_en_avant_products[:5]
            )
            prompt = f"""Tu es un expert en boutique de seconde main premium.
Semaine {week}/{year}. Voici un résumé des produits en boutique:

Produits à faible score (à mettre en avant):
{product_summary or 'Aucun'}

INTERDICTION ABSOLUE : ne propose JAMAIS de baisse de prix, de markdown, de
soldes ou de remise. La boutique fixe le prix correct dès la mise en rayon.
Tes leviers : visibilité (vitrine, mise en avant), composition de rayon,
mise en scène, rotation, publication Instagram. Pas de pricing.

Génère 2-3 recommandations concrètes et actionnables pour améliorer les ventes cette semaine. Sois bref et pratique (max 100 mots)."""
            msg = await client_ai.messages.create(
                model="claude-haiku-4-5",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            ai_summary = msg.content[0].text if msg.content else None
        except Exception:
            ai_summary = None

    result = {
        "week": week,
        "year": year,
        "generated_at": now.isoformat(),
        "ai_summary": ai_summary,
        "checklist": checklist,
    }
    # Cache result for the week
    await _set_setting(db, "ai_checklist_cache", json.dumps(result, ensure_ascii=False))
    await db.commit()
    return result


# ---------------------------------------------------------------------------
# Fashion Trends
# ---------------------------------------------------------------------------

@router.get("/trends")
async def get_fashion_trends(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    force_refresh: bool = Query(False, description="Force regeneration even if cache is fresh"),
):
    """Get fashion trends for the current season. Generated by AI on Mondays, cached for the week."""
    now = datetime.now(timezone.utc)
    week = now.isocalendar()[1]
    year = now.year
    is_monday = now.weekday() == 0

    # Return cached version unless it's Monday or forced
    if not is_monday and not force_refresh:
        cached = await _get_setting(db, "ai_trends_mode_cache")
        if cached:
            try:
                data = json.loads(cached)
                if data.get("week") == week and data.get("year") == year:
                    return data
            except (json.JSONDecodeError, KeyError):
                pass

    # Also check cache when it's Monday but data already regenerated today
    if is_monday:
        cached = await _get_setting(db, "ai_trends_mode_cache")
        if cached:
            try:
                data = json.loads(cached)
                cached_at = datetime.fromisoformat(data.get("generated_at", "2000-01-01"))
                if (cached_at.date() == now.date()):
                    return data
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

    anthropic_key = settings.ANTHROPIC_API_KEY or ""
    # Determine the current fashion season (FR retail calendar).
    month = now.month
    if month in (3, 4, 5):
        season = "Printemps 2026"
    elif month in (6, 7, 8):
        season = "Été 2026"
    elif month in (9, 10, 11):
        season = "Automne 2026"
    else:
        season = "Hiver 2026"

    channels = None
    trends = None
    brands = None
    if anthropic_key:
        try:
            import anthropic as _anthropic
            client_ai = _anthropic.AsyncAnthropic(api_key=anthropic_key)
            prompt = f"""Tu es Camille Berthier, rédactrice en chef d'un magazine mode indépendant et
ancienne acheteuse pour Galeries Lafayette. Tu écris pour Vintiz — boutique de seconde
main premium à Vernon (Normandie) — le Fashion Book de la semaine.

Saison en cours : {season}.

Produis un rapport ÉDITORIAL au format JSON, avec exactement cette structure :
{{
  "season": "{season}",
  "editorial_intro": "Édito personnel 2-3 phrases qui pose le ton de la saison",
  "trends": [
    {{
      "id": "slug-court",
      "title": "Titre de tendance ≤6 mots",
      "key_words": ["mot-clé1", "mot-clé2", "mot-clé3"],
      "source": "Vogue / Vinted / Pinterest / Insta @nom / Le Bon Marché …",
      "article": "3-4 phrases qui décrivent la tendance, son origine, les pièces signature, qui la porte. Ton magazine — incarné, pas marketing.",
      "visual_prompt": "Prompt photographique en 1 phrase pour générer un visuel hero (utilisable Midjourney/Imagen/DALL-E)",
      "categories": ["robe", "pantalon", "veste"],
      "colors": ["camel", "écru"],
      "match_keywords": ["lin", "midi", "taille haute"]
    }}
    // 4 à 5 entrées au total — 5 max
  ],
  "brands": [
    {{
      "name": "Sandro",
      "tier": "premium",
      "why": "Pourquoi cette marque est tendance maintenant en 1 phrase",
      "logo_query": "sandro paris logo svg"
    }}
    // 5 à 8 marques tendances de la saison, mix premium / luxe / contemporain
  ]
}}

Contraintes :
- Maximum 5 tendances. Préfère 4 fortes plutôt que 5 médiocres.
- Cite une vraie source identifiable par tendance (pas "tendances générales").
- Les `match_keywords` servent à matcher l'inventaire boutique (mots simples, FR).
- INTERDICTION : ne mentionne aucune stratégie prix, markdown, soldes,
  remises ou évolution tarifaire. La boutique pratique un prix juste dès
  la mise en rayon. Si tu veux parler de "valeur perçue", reste sur la
  matière, l'origine, l'usage — jamais sur l'arbitrage prix.
- Réponds UNIQUEMENT avec le JSON, sans markdown ni commentaire."""
            msg = await client_ai.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text if msg.content else "{}"
            data = json.loads(raw)
            trends = data.get("trends") or None
            brands = data.get("brands") or None
            editorial_intro = data.get("editorial_intro")

            # Backwards-compat: also produce the old "channels" shape from trends
            if trends:
                top_items = []
                colors_set: list[str] = []
                for t in trends[:5]:
                    if t.get("title"):
                        top_items.append(t["title"])
                    for c in t.get("colors") or []:
                        if c not in colors_set:
                            colors_set.append(c)
                channels = {
                    "reseaux_sociaux": {
                        "summary": editorial_intro or "Tendances mode actuelles",
                        "top_items": top_items[:5],
                        "colors": colors_set[:5],
                    },
                    "vinted": {
                        "summary": "Dynamique seconde-main fortement liée aux tendances de la saison.",
                        "top_categories": list({c for t in trends for c in (t.get("categories") or [])})[:3],
                        "price_trends": "Hausse soutenue sur les marques premium françaises",
                    },
                    "retail": {
                        "summary": editorial_intro or "Saison retail en cours",
                        "key_trends": [t.get("title", "") for t in trends[:3] if t.get("title")],
                    },
                }
        except Exception:
            channels = None
            trends = None
            brands = None

    if trends is None:
        # Editorial fallback — used when no Anthropic key OR JSON parsing failed.
        # Hand-curated for the current French retail calendar.
        editorial_intro = (
            "Le quiet luxury continue d'irriguer la garde-robe, mais cette saison "
            "il s'allège : silhouettes fluides, broderies discrètes, lin écru. "
            "À Vernon, la seconde main premium suit la même partition."
        )
        trends = [
            {
                "id": "quiet-luxury-light",
                "title": "Quiet luxury allégé",
                "key_words": ["camel", "écru", "blazer"],
                "source": "Vogue Paris (édito mars) / Le Bon Marché vitrines",
                "article": "Le quiet luxury survit à 2026, mais perd ses épaules carrées au profit de blazers déstructurés et de pantalons larges en lin. La pièce qui signe : blazer oversize couleur camel sans rembourrage, porté ouvert.",
                "visual_prompt": "Editorial fashion photography, woman in unstructured camel blazer over white linen, soft daylight, neutral wall, 35mm film aesthetic",
                "categories": ["veste", "blazer", "pantalon"],
                "colors": ["camel", "écru", "blanc cassé"],
                "match_keywords": ["blazer", "lin", "camel"],
            },
            {
                "id": "linen-renaissance",
                "title": "Renaissance du lin",
                "key_words": ["lin", "broderie", "midi"],
                "source": "Pinterest trend report Q2 / Sézane SS26",
                "article": "Le lin n'est plus l'apanage de l'été : robes midi, chemises oversize, ensembles deux-pièces. Il devient une signature de lifestyle premium, qui s'adapte à toutes les saisons grâce aux superpositions.",
                "visual_prompt": "Linen midi dress, soft beige tone, woman walking through olive grove, golden hour, editorial style, natural texture close-up",
                "categories": ["robe", "chemise", "ensemble"],
                "colors": ["écru", "beige", "blanc"],
                "match_keywords": ["lin", "robe midi", "chemise"],
            },
            {
                "id": "vert-sauge-statement",
                "title": "Vert sauge qui s'impose",
                "key_words": ["vert sauge", "monochrome", "denim"],
                "source": "Instagram @hodakhone / Vinted top searches mars",
                "article": "Le vert sauge passe de couleur d'accent à teinte primaire, surtout sur les pièces denim et les manteaux mi-saison. Il rivalise avec le bordeaux comme statement-color de la saison.",
                "visual_prompt": "Sage green oversized denim jacket on minimalist beige background, model from waist up, studio light, magazine cover composition",
                "categories": ["veste", "manteau", "denim"],
                "colors": ["vert sauge", "kaki"],
                "match_keywords": ["vert", "sauge", "denim"],
            },
            {
                "id": "sacoche-utilitaire",
                "title": "La sacoche utilitaire premium",
                "key_words": ["sac", "bandoulière", "cuir"],
                "source": "TikTok #premiumsecondhand / The Row SS26",
                "article": "Après le tote bag, la sacoche bandoulière en cuir grainé. Compacte, fonctionnelle, intemporelle : c'est l'investissement seconde-main de la saison, surtout en marques françaises premium (A.P.C., Polène, Sézane).",
                "visual_prompt": "Premium leather crossbody bag in caramel brown, hanging on chair back, soft Parisian café ambiance, depth of field shallow",
                "categories": ["sac", "accessoire"],
                "colors": ["caramel", "noir", "bordeaux"],
                "match_keywords": ["sac", "bandoulière", "cuir"],
            },
            {
                "id": "broderie-artisanale",
                "title": "Broderie artisanale discrète",
                "key_words": ["broderie", "artisanal", "détail"],
                "source": "Le Monde du Lin / Sandro édito avril",
                "article": "La broderie revient en finition discrète sur les blouses, robes courtes et vestes en jean. On valorise la main, l'artisanat, le détail repérable de près. Idéal sur les pièces vintage à upcycler.",
                "visual_prompt": "Hand embroidery floral detail on white cotton blouse, macro photography, natural soft light, hand stitching visible",
                "categories": ["blouse", "robe", "veste"],
                "colors": ["blanc", "écru", "bleu pâle"],
                "match_keywords": ["brodé", "broderie", "vintage"],
            },
        ]
        brands = [
            {"name": "Sandro", "tier": "premium", "why": "Demande seconde-main +18% sur 30j (Vinted FR)", "logo_query": "sandro paris logo"},
            {"name": "Maje", "tier": "premium", "why": "Bestseller sur les robes midi printemps", "logo_query": "maje paris logo"},
            {"name": "Sézane", "tier": "premium", "why": "Lin et broderies, alignement parfait avec la saison", "logo_query": "sezane logo"},
            {"name": "Ba&sh", "tier": "premium", "why": "Reprise forte des modèles drapés", "logo_query": "bash logo paris"},
            {"name": "Polène", "tier": "luxury-affordable", "why": "Sac bandoulière numéro un sur les recherches TikTok", "logo_query": "polene paris logo"},
            {"name": "A.P.C.", "tier": "premium", "why": "Pieces denim minimalistes très recherchées", "logo_query": "apc logo"},
            {"name": "The Frankie Shop", "tier": "contemporary", "why": "Blazer oversize et silhouette utilitaire", "logo_query": "frankie shop logo"},
        ]
        if not channels:
            channels = {
                "reseaux_sociaux": {
                    "summary": editorial_intro,
                    "top_items": [t["title"] for t in trends[:5]],
                    "colors": ["Camel", "Écru", "Vert sauge", "Caramel", "Bleu pâle"],
                },
                "vinted": {
                    "summary": "Dynamique seconde-main fortement liée aux tendances de la saison.",
                    "top_categories": ["Robes", "Blazers", "Sacs"],
                    "price_trends": "Hausse soutenue sur les marques françaises premium",
                },
                "retail": {
                    "summary": editorial_intro,
                    "key_trends": [t["title"] for t in trends[:3]],
                },
            }
    else:
        editorial_intro = (data or {}).get("editorial_intro") if 'data' in locals() else None
        if not editorial_intro:
            editorial_intro = "Tendances mode actuelles"

    # Inventory match — find products whose name/category/material/color contains
    # any match_keyword for each trend. Lightweight — best-effort, capped to 6.
    inventory_matches: dict[str, list[dict]] = {}
    try:
        from app.models.product import Product

        for t in trends:
            kws = [k.lower() for k in (t.get("match_keywords") or []) if k]
            if not kws:
                inventory_matches[t.get("id", "")] = []
                continue
            from sqlalchemy import or_, func as _func
            conditions = []
            for kw in kws[:5]:
                like = f"%{kw}%"
                conditions.append(_func.lower(Product.name).like(like))
                conditions.append(_func.lower(_func.coalesce(Product.color, "")).like(like))
                conditions.append(_func.lower(_func.coalesce(Product.brand, "")).like(like))
                conditions.append(_func.lower(_func.coalesce(Product.description, "")).like(like))
            stmt = (
                select(Product)
                .where(Product.status.in_([ProductStatus.stock, ProductStatus.display]))
                .where(or_(*conditions))
                .order_by(Product.created_at.desc())
                .limit(6)
            )
            rows = (await db.execute(stmt)).scalars().all()
            inventory_matches[t.get("id", "")] = [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "barcode": p.barcode,
                    "price_eur": float(p.sale_price or 0),
                    "brand": p.brand,
                    "size": p.size,
                    "color": p.color,
                    "photo_url": p.photo_url,
                }
                for p in rows
            ]
    except Exception:
        inventory_matches = {}

    result = {
        "week": week,
        "year": year,
        "season": season,
        "generated_at": now.isoformat(),
        "editorial_intro": editorial_intro,
        "channels": channels,  # legacy shape for the old UI
        "trends": trends,
        "brands": brands,
        "inventory_matches": inventory_matches,
    }
    await _set_setting(db, "ai_trends_mode_cache", json.dumps(result, ensure_ascii=False))
    await db.commit()
    return result


# ---------------------------------------------------------------------------
# Persona Marketing
# ---------------------------------------------------------------------------

async def _build_marketing_persona_report(db: AsyncSession) -> dict:
    """Generate the bicephalous marketing persona report.

    Pure function (no auth, no caching) — called both by the GET endpoint
    fallback and by the Monday cron via app.jobs.run_weekly_marketing_report.
    """
    now = datetime.now(timezone.utc)

    # Collect boutique metrics
    total_products_result = await db.execute(
        select(func.count(Product.id)).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display])
        )
    )
    total_products = total_products_result.scalar_one() or 0

    avg_score_result = await db.execute(
        select(func.avg(Product.trend_score)).where(
            Product.trend_score.is_not(None)
        )
    )
    avg_score = float(avg_score_result.scalar_one() or 0)

    total_clients_result = await db.execute(select(func.count(Client.id)))
    total_clients = total_clients_result.scalar_one() or 0

    # Recent CA (last 30 days)
    from datetime import timedelta
    thirty_days_ago = now - timedelta(days=30)
    ca_result = await db.execute(
        select(func.sum(Transaction.total_ttc)).where(
            Transaction.created_at >= thirty_days_ago
        )
    )
    ca_30d = float(ca_result.scalar_one() or 0)

    sold_count_result = await db.execute(
        select(func.count(Product.id)).where(Product.status == ProductStatus.sold)
    )
    sold_count = sold_count_result.scalar_one() or 0

    context = {
        "articles_en_vente": total_products,
        "score_tendance_moyen": round(avg_score, 1),
        "total_clients": total_clients,
        "ca_30_derniers_jours": round(ca_30d, 2),
        "articles_vendus_total": sold_count,
    }

    # Pull a "hero product" candidate for the Insta post (highest trend_score in stock)
    hero_product = None
    try:
        hero_stmt = (
            select(Product)
            .where(Product.status.in_([ProductStatus.stock, ProductStatus.display]))
            .order_by(Product.trend_score.desc().nullslast())
            .limit(1)
        )
        hero_row = (await db.execute(hero_stmt)).scalar_one_or_none()
        if hero_row:
            hero_product = {
                "id": str(hero_row.id),
                "name": hero_row.name,
                "barcode": hero_row.barcode,
                "brand": hero_row.brand,
                "size": hero_row.size,
                "color": hero_row.color,
                "price_eur": float(hero_row.sale_price or 0),
                "photo_url": hero_row.photo_url,
                "trend_score": float(hero_row.trend_score or 0),
            }
    except Exception:
        hero_product = None

    # Determine the next 3 months for the retail director note
    from datetime import timedelta
    months_fr = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    next_three_months = []
    for k in range(3):
        m = (now.month - 1 + k) % 12
        next_three_months.append(months_fr[m])

    anthropic_key = settings.ANTHROPIC_API_KEY or ""
    digital_marketing = None
    retail_director = None
    if anthropic_key:
        try:
            import anthropic
            client_ai = anthropic.AsyncAnthropic(api_key=anthropic_key)
            prompt = f"""Tu produis un rapport bicéphale pour la boutique Vintiz (Vernon, Normandie — seconde main premium).

Données actuelles :
- Articles en vente : {context['articles_en_vente']}
- Score tendance moyen : {context['score_tendance_moyen']}/100
- Clients inscrits : {context['total_clients']}
- CA 30 derniers jours : {context['ca_30_derniers_jours']} €
- Articles vendus total : {context['articles_vendus_total']}
- Pièce hero candidate : {hero_product['name'] if hero_product else 'aucune'}{(' — ' + (hero_product or {}).get('brand', '')) if hero_product and hero_product.get('brand') else ''}{(' (' + (hero_product or {}).get('color', '') + ')') if hero_product and hero_product.get('color') else ''}{(' à ' + str((hero_product or {}).get('price_eur', 0)) + ' €') if hero_product else ''}

Mois courant : {months_fr[now.month - 1]}.
Trois prochains mois : {' / '.join(next_three_months)}.

Tu prends DEUX personas successifs et tu réponds en JSON :

{{
  "digital_marketing": {{
    "persona": "Léa Martin, Responsable Marketing Digital indépendante (ex Sézane)",
    "post_de_la_semaine": {{
      "produit_id": "{hero_product['id'] if hero_product else ''}",
      "produit_nom": "{(hero_product or {}).get('name', '')}",
      "angle_editorial": "L'angle (1 phrase) — ce que cette pièce raconte",
      "caption_instagram": "Caption Instagram complète (3 paragraphes courts, emoji modéré, CTA, hashtags pertinents en fin)",
      "hashtags": ["#vintiz", "..."],
      "best_time_post": "ex : mardi 18h30",
      "story_idea": "Une idée de story (avant-après, behind-the-scenes…)",
      "visual_brief": "Prompt photo en 1 phrase pour générer le visuel hero (style, cadrage, lumière, ambiance)",
      "carousel_slides": [
        "Slide 1 : titre + détail produit",
        "Slide 2 : zoom sur la matière ou la coupe",
        "Slide 3 : look stylisé porté",
        "Slide 4 : CTA + lien profil"
      ]
    }},
    "actions_de_la_semaine": [
      "Action concrète 1 (story, reel, partenariat…)",
      "Action concrète 2",
      "Action concrète 3"
    ]
  }},
  "retail_director": {{
    "persona": "Jean-Marc Bellanger, Directeur Régional Retail Normandie (ex Galeries Lafayette, ex Sézane)",
    "conjoncture_mois_dernier": "État du marché retail mode au mois dernier en France (1 paragraphe synthétique, chiffres si possible : trafic, panier moyen, climat, inflation, tendance seconde-main)",
    "tendance_3_mois": [
      {{"mois": "{next_three_months[0]}", "tendance": "Description tendance (1-2 phrases)"}},
      {{"mois": "{next_three_months[1]}", "tendance": "Description tendance"}},
      {{"mois": "{next_three_months[2]}", "tendance": "Description tendance"}}
    ],
    "evenements_majeurs": [
      {{"date": "JJ/MM", "evenement": "Nom (ex : Black Friday, fête des mères, vacances scolaires zone B…)", "impact": "Impact retail attendu"}},
      {{"date": "JJ/MM", "evenement": "...", "impact": "..."}}
    ],
    "recommandations_boutique": [
      {{"priorite": "haute", "action": "...", "impact": "..."}},
      {{"priorite": "haute", "action": "...", "impact": "..."}},
      {{"priorite": "moyenne", "action": "...", "impact": "..."}}
    ],
    "kpi_cibles": {{"ca_mensuel_cible": 0, "nouveaux_clients_mois": 0, "taux_conversion_vitrine": "X%"}}
  }}
}}

INTERDICTION ABSOLUE : ne propose JAMAIS de baisse de prix, de markdown,
de soldes ou de stratégie tarifaire dynamique. La boutique fixe un prix
correct dès la mise en rayon — c'est un parti-pris. Tes leviers :
acquisition, visibilité, mise en scène, fidélisation, narratif éditorial,
événements, partenariats. Pas de pricing.

Réponds UNIQUEMENT avec le JSON, sans markdown."""
            msg = await client_ai.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text if msg.content else "{}"
            data = json.loads(raw)
            digital_marketing = data.get("digital_marketing")
            retail_director = data.get("retail_director")
        except Exception:
            digital_marketing = None
            retail_director = None

    # Fallbacks (used when no Anthropic key OR JSON parsing failed)
    if not digital_marketing:
        digital_marketing = {
            "persona": "Léa Martin, Responsable Marketing Digital indépendante",
            "post_de_la_semaine": {
                "produit_id": hero_product["id"] if hero_product else "",
                "produit_nom": (hero_product or {}).get("name", "(à choisir)"),
                "angle_editorial": "Une pièce qui raconte la patine du temps, sublimée par le geste de la seconde main.",
                "caption_instagram": (
                    f"✨ La trouvaille de la semaine.\n"
                    f"{(hero_product or {}).get('brand', 'Une marque')} {(hero_product or {}).get('color', '')} — {((hero_product or {}).get('size') or '')}.\n\n"
                    f"À retrouver en boutique à Vernon. Une pièce, une histoire.\n\n"
                    f"#vintiz #vernon #secondemainpremium #slowfashion"
                ),
                "hashtags": ["#vintiz", "#vernon", "#secondemainpremium", "#slowfashion", "#prelovedfashion"],
                "best_time_post": "Mardi 18h30",
                "story_idea": "Story avant/après : la pièce reçue brute → la pièce mise en scène en boutique.",
                "visual_brief": "Photo éditoriale, plan rapproché de la pièce sur cintre en bois, fond mur écru, lumière naturelle douce de fin d'après-midi.",
                "carousel_slides": [
                    "Slide 1 : titre + nom produit + prix",
                    "Slide 2 : zoom matière (coupe, finitions)",
                    "Slide 3 : look complet stylisé",
                    "Slide 4 : CTA boutique + lien bio",
                ],
            },
            "actions_de_la_semaine": [
                "Préparer une story Reel sur l'arrivée des nouvelles pièces",
                "Relancer la newsletter avec une sélection de 5 pièces tendance",
                "Identifier 3 micro-influenceuses Vernon/Évreux pour un partenariat",
            ],
        }

    if not retail_director:
        retail_director = {
            "persona": "Jean-Marc Bellanger, Directeur Régional Retail Normandie",
            "conjoncture_mois_dernier": (
                "Le mois dernier a vu le retail textile français reculer de 2 à 3 % en valeur sous "
                "l'effet d'une météo capricieuse et d'un pouvoir d'achat sous pression. La seconde "
                "main premium tire son épingle du jeu avec une croissance autour de +12 % "
                "(Vinted, dépôts-vente premium), portée par les 25-45 ans qui arbitrent en faveur "
                "de pièces de marques reconnues à prix doux."
            ),
            "tendance_3_mois": [
                {"mois": next_three_months[0], "tendance": "Saison commerciale clé : les clientes anticipent leurs vacances et cherchent des pièces fluides, lin, robes midi. Pic d'affluence le samedi après-midi."},
                {"mois": next_three_months[1], "tendance": "Mois de transition : faible affluence début de mois (vacances scolaires zone B), reprise forte à partir du 3e weekend. Privilégier les nouveautés petites quantités, fort renouvellement."},
                {"mois": next_three_months[2], "tendance": "Rentrée commerciale : retour des actifs, la demande se déplace vers les blazers, les pantalons larges, les sacs structurés. Vitrine à refaire le 1er mardi."},
            ],
            "evenements_majeurs": [
                {"date": "26/05", "evenement": "Fête des mères", "impact": "Pic acquisition cadeau, panier moyen +25 %, prévoir packaging cadeau."},
                {"date": "06-08/06", "evenement": "Vacances de la Pentecôte", "impact": "Affluence touristique sur Vernon (Giverny), trafic boutique +30 % le weekend."},
                {"date": "21/06", "evenement": "Fête de la Musique", "impact": "Trafic centre-ville en soirée — nocturne possible, vitrine été à valider."},
                {"date": "14/07", "evenement": "Fête nationale", "impact": "Boutique fermée. Programme retro le 13/07, soir."},
            ],
            "recommandations_boutique": [
                {"priorite": "haute", "action": "Lancer une mini-capsule lin pour mai", "impact": "+15 % de panier moyen sur la cible cadre 35-50"},
                {"priorite": "haute", "action": "Activer une opération fidélité ciblée champion+at_risk", "impact": "Réactivation 25 % des at_risk sous 30j"},
                {"priorite": "moyenne", "action": "Travailler la vitrine fête des mères mi-mai", "impact": "+30 % d'attractivité de passage"},
            ],
            "kpi_cibles": {
                "ca_mensuel_cible": int(ca_30d * 1.2) or 3500,
                "nouveaux_clients_mois": 12,
                "taux_conversion_vitrine": "14%",
            },
        }

    return {
        "generated_at": now.isoformat(),
        "week": now.isocalendar()[1],
        "year": now.year,
        "context": context,
        "hero_product": hero_product,
        "digital_marketing": digital_marketing,
        "retail_director": retail_director,
    }


@router.get("/persona/marketing")
async def get_marketing_persona(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return the cached weekly marketing report.

    Generation runs every Monday at 08:30 Paris via the cron
    ``run_weekly_marketing_report``. If the cache is empty (first deploy or
    during the week before the first Monday), generate on-the-fly and store.
    """
    cached = await _get_setting(db, "ai_marketing_persona_cache")
    if cached:
        try:
            data = json.loads(cached)
            now = datetime.now(timezone.utc)
            if data.get("week") == now.isocalendar()[1] and data.get("year") == now.year:
                return data
        except (json.JSONDecodeError, KeyError):
            pass

    result = await _build_marketing_persona_report(db)
    await _set_setting(db, "ai_marketing_persona_cache", json.dumps(result, ensure_ascii=False))
    await db.commit()
    return result


@router.post("/persona/marketing/regenerate")
async def regenerate_marketing_persona(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Manager-triggered manual regeneration. Use sparingly — the cron
    rebuilds this report every Monday at 08:30 Paris automatically."""
    result = await _build_marketing_persona_report(db)
    await _set_setting(db, "ai_marketing_persona_cache", json.dumps(result, ensure_ascii=False))
    await db.commit()
    return result


# ---------------------------------------------------------------------------
# Zone Products
# ---------------------------------------------------------------------------

@router.get("/mapping/zones/{zone_id}/products")
async def get_zone_products(
    zone_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get all products currently assigned to a store zone."""
    zone_result = await db.execute(select(StoreZone).where(StoreZone.id == zone_id))
    zone = zone_result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone non trouvée")

    products_result = await db.execute(
        select(Product)
        .where(
            Product.zone_id == zone_id,
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
        )
        .order_by(Product.trend_score.desc().nulls_last())
    )
    products = products_result.scalars().all()

    return {
        "zone_id": zone_id,
        "zone_name": zone.name,
        "products": [
            {
                "id": str(p.id),
                "barcode": p.barcode,
                "name": p.name,
                "brand": p.brand,
                "size": p.size,
                "color": p.color,
                "sale_price": float(p.sale_price),
                "status": p.status.value,
                "trend_score": p.trend_score,
                "photo_url": p.photo_url,
            }
            for p in products
        ],
    }


# ---------------------------------------------------------------------------
# [REMOVED] Persona Juridique (RGPD/CNIL) - feature removed per business request
# ---------------------------------------------------------------------------

# The /ai/persona/juridique endpoint has been removed.
# If you need GDPR compliance information, please consult a legal professional.

# ---------------------------------------------------------------------------
# Persona Juridique placeholder (returns 410 Gone)
# ---------------------------------------------------------------------------

@router.post("/persona/juridique")
async def generate_legal_persona_removed(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """This feature has been removed."""
    raise HTTPException(status_code=410, detail="Cette fonctionnalité a été supprimée.")


# ---------------------------------------------------------------------------
# Persona Gestion de magasin — audit du module d'entrée produit
# ---------------------------------------------------------------------------

@router.get("/persona/store-ops")
async def get_store_ops_persona(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Audit du module d'entrée produit par la persona Responsable de magasin.

    Renvoie le rapport caché de la semaine s'il existe (régénéré au besoin),
    sinon le construit à la volée. Les métriques reflètent l'état temps réel
    de l'inventaire (photo, analyse IA, zone, dates) ; la narration est
    générée par Claude avec un repli déterministe.
    """
    from app.services.store_ops_audit import build_store_ops_report

    cached = await _get_setting(db, "ai_store_ops_persona_cache")
    if cached:
        try:
            data = json.loads(cached)
            now = datetime.now(timezone.utc)
            if data.get("week") == now.isocalendar()[1] and data.get("year") == now.year:
                return data
        except (json.JSONDecodeError, KeyError):
            pass

    result = await build_store_ops_report(db)
    await _set_setting(db, "ai_store_ops_persona_cache", json.dumps(result, ensure_ascii=False))
    await db.commit()
    return result


@router.post("/persona/store-ops/regenerate")
async def regenerate_store_ops_persona(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Régénération manuelle de l'audit Responsable de magasin (manager)."""
    from app.services.store_ops_audit import build_store_ops_report

    result = await build_store_ops_report(db)
    await _set_setting(db, "ai_store_ops_persona_cache", json.dumps(result, ensure_ascii=False))
    await db.commit()
    return result


# ---------------------------------------------------------------------------
# AI Companion — briefing / chat / tasks
# ---------------------------------------------------------------------------


def _greeting_for(now: datetime, user_name: str | None) -> str:
    hour = now.hour
    weekday = now.weekday()  # 0=Mon..6=Sun
    name = user_name or "collaborateur"
    if 5 <= hour < 12:
        prefix = "Bonjour"
    elif 12 <= hour < 18:
        prefix = "Bon apres-midi"
    else:
        prefix = "Bonsoir"
    day_label = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][weekday]
    if weekday == 4 and hour >= 14:
        tail = "bien finir la semaine"
    elif weekday in (5, 6):
        tail = "profiter d'un weekend actif"
    elif weekday == 0 and hour < 11:
        tail = "bien demarrer la semaine"
    else:
        tail = "rythmer ta journee"
    return f"{prefix} {name}, {day_label} — voici ce qu'il faut savoir pour {tail}."


@router.get("/briefing")
async def get_daily_briefing(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return a context-rich daily briefing for the collaborator."""
    now = datetime.now(timezone.utc)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_yesterday = start_today - timedelta(days=1)

    # Yesterday stats
    y_res = await db.execute(
        select(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.total_ttc), 0),
        ).where(
            Transaction.created_at >= start_yesterday,
            Transaction.created_at < start_today,
            Transaction.transaction_type == TransactionType.sale,
        )
    )
    y_count, y_revenue = y_res.one()

    # Today so far
    t_res = await db.execute(
        select(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.total_ttc), 0),
        ).where(
            Transaction.created_at >= start_today,
            Transaction.transaction_type == TransactionType.sale,
        )
    )
    t_count, t_revenue = t_res.one()

    # Active products in stock/display
    active_res = await db.execute(
        select(func.count(Product.id)).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display])
        )
    )
    active_products = active_res.scalar_one() or 0

    # Stale: on display for > 45 days
    stale_cutoff = now - timedelta(days=45)
    stale_res = await db.execute(
        select(func.count(Product.id)).where(
            Product.status == ProductStatus.display,
            Product.shelf_date < stale_cutoff,
        )
    )
    stale_count = stale_res.scalar_one() or 0

    # Top 3 zones by occupancy imbalance
    zones_res = await db.execute(select(StoreZone))
    zone_alerts: list[dict] = []
    for z in zones_res.scalars():
        if not z.capacity:
            continue
        count_res = await db.execute(
            select(func.count(Product.id)).where(Product.zone_id == z.id)
        )
        count = count_res.scalar_one() or 0
        pct = (count / z.capacity) * 100.0
        if pct < 35 or pct > 98:
            zone_alerts.append({
                "zone_id": str(z.id),
                "zone_name": z.name,
                "occupancy_pct": round(pct, 1),
                "status": "sous_occupee" if pct < 35 else "saturee",
            })

    # Compose 3 priorities (heuristic without AI call)
    priorities: list[dict] = []
    if stale_count > 0:
        priorities.append({
            "title": f"{stale_count} article(s) en rayon depuis 45+ jours",
            "body": "Envisage une demarque douce ou un changement d'emplacement pour les relancer.",
            "action_url": "/ia?tab=pricing",
            "type": "markdown",
            "priority": 4 if stale_count >= 5 else 3,
        })
    if zone_alerts:
        za = zone_alerts[0]
        priorities.append({
            "title": f"Zone {za['zone_name']} {za['status'].replace('_', ' ')}",
            "body": f"Occupation {za['occupancy_pct']}% — pense a rééquilibrer avec les autres espaces.",
            "action_url": f"/zones/{za['zone_id']}",
            "type": "zone_alert",
            "priority": 3,
        })
    if t_revenue < (y_revenue or 0) * 0.6 and now.hour >= 14:
        priorities.append({
            "title": "Rythme de journee sous la moyenne",
            "body": "Propose les pieces qui ont bien marche hier en vitrine, ou sollicite tes clients fideles par SMS.",
            "action_url": "/crm",
            "type": "mise_en_avant",
            "priority": 4,
        })
    # Fill up to 3 with fallback
    while len(priorities) < 3:
        priorities.append({
            "title": "Consulte ta checklist hebdomadaire",
            "body": "La checklist IA du lundi contient des actions validees par les donnees de la semaine.",
            "action_url": "/ia?tab=checklist",
            "type": "checklist",
            "priority": 2,
        })

    return {
        "greeting": _greeting_for(now, getattr(current_user, "username", None)),
        "date": now.date().isoformat(),
        "today": {
            "revenue": float(t_revenue or 0),
            "transactions": int(t_count or 0),
        },
        "yesterday": {
            "revenue": float(y_revenue or 0),
            "transactions": int(y_count or 0),
        },
        "stock": {
            "active": active_products,
            "stale_45d": stale_count,
        },
        "zone_alerts": zone_alerts,
        "priorities": priorities[:3],
    }


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    context: Optional[dict] = None


@router.post("/chat")
async def ai_chat(
    payload: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Conversational companion. Passes the current store context to Claude."""
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY manquante — le chat IA est desactive.",
        )

    import anthropic  # lazy import

    # Build lightweight store context
    active_res = await db.execute(
        select(func.count(Product.id)).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display])
        )
    )
    active_products = active_res.scalar_one() or 0
    zones_res = await db.execute(select(StoreZone))
    zones = [{"name": z.name, "capacity": z.capacity} for z in zones_res.scalars()]

    store_context = {
        "boutique": "Vintiz — Vernon, Normandie — seconde main premium",
        "active_products": active_products,
        "zones": zones,
    }
    if payload.context:
        store_context["page_context"] = payload.context

    system = (
        "Tu es le compagnon IA de la boutique Vintiz a Vernon. "
        "Tu t'adresses aux collaboratrices et collaborateurs de la boutique avec un ton "
        "chaleureux, direct, concret et plein de bon sens commercial. Tes reponses sont "
        "courtes (3 a 6 lignes max sauf si on te demande plus), avec des actions "
        "concretes et chiffrees. Tu ne reponds jamais en markdown lourd, juste des "
        "paragraphes courts. "
        f"Contexte boutique a prendre en compte : {json.dumps(store_context, ensure_ascii=False)}"
    )

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        message = await client.messages.create(
            model=os.environ.get("ANTHROPIC_CHAT_MODEL", "claude-haiku-4-5"),
            max_tokens=600,
            system=system,
            messages=[{"role": m.role, "content": m.content} for m in payload.messages],
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Chat IA indisponible: {exc}")

    reply = ""
    for block in message.content:
        if getattr(block, "type", None) == "text":
            reply += getattr(block, "text", "")
    return {"reply": reply or "(reponse vide)"}


class TaskCreate(BaseModel):
    type: str
    title: str
    body: str | None = None
    priority: int = 3
    action_url: str | None = None
    payload: dict | None = None
    source: str | None = None
    due_date: datetime | None = None


@router.get("/tasks")
async def list_ai_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: str = Query("open", description="open | snoozed | done | all"),
):
    """List AI companion tasks."""
    stmt = select(AITask).order_by(AITask.priority.desc(), AITask.created_at.desc())
    if status == "open":
        stmt = stmt.where(AITask.status.in_(["pending", "accepted"]))
    elif status == "snoozed":
        stmt = stmt.where(AITask.status == "snoozed")
    elif status == "done":
        stmt = stmt.where(AITask.status.in_(["completed", "dismissed"]))
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "type": t.type,
            "title": t.title,
            "body": t.body,
            "priority": t.priority,
            "status": t.status,
            "action_url": t.action_url,
            "payload": t.payload,
            "source": t.source,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "snoozed_until": t.snoozed_until.isoformat() if t.snoozed_until else None,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]


@router.post("/tasks", status_code=201)
async def create_ai_task(
    payload: TaskCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = AITask(
        type=payload.type,
        title=payload.title,
        body=payload.body,
        priority=payload.priority,
        action_url=payload.action_url,
        payload=payload.payload,
        source=payload.source,
        due_date=payload.due_date,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": str(task.id), "status": task.status}


class TaskSnoozePayload(BaseModel):
    days: int = 1


@router.post("/tasks/{task_id}/accept")
async def accept_task(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = await db.get(AITask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "completed"}


@router.post("/tasks/{task_id}/snooze")
async def snooze_task(
    task_id: uuid.UUID,
    payload: TaskSnoozePayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = await db.get(AITask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "snoozed"
    task.snoozed_until = datetime.now(timezone.utc) + timedelta(days=max(1, payload.days))
    await db.commit()
    return {"status": "snoozed", "until": task.snoozed_until.isoformat()}


@router.post("/tasks/{task_id}/dismiss")
async def dismiss_task(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = await db.get(AITask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "dismissed"
    await db.commit()
    return {"status": "dismissed"}
