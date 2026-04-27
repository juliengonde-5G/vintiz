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
from app.services.ai_pricing import suggest_price, suggest_markdowns
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
    if len(image_data) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Image trop volumineuse (max 10 Mo)")

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
    purchase_price: float,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    brand: str | None = None,
    condition: str | None = None,
):
    """Suggest an optimal sale price for a product."""
    result = await suggest_price(db, category_id, purchase_price, brand, condition)
    return result


@router.get("/pricing/markdowns")
async def get_markdown_suggestions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get suggested markdowns for stale products."""
    suggestions = await suggest_markdowns(db)
    return {
        "count": len(suggestions),
        "total_potential_savings": sum(
            s["current_price"] - s["suggested_price"] for s in suggestions
        ),
        "suggestions": suggestions,
    }


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

    # Build overpriced list (sale_price > 1.5 * category avg)
    overpriced = []
    for p in low_score_products:
        cat_avg = avg_by_cat.get(str(p.category_id), float(p.sale_price))
        if cat_avg > 0 and float(p.sale_price) > 1.5 * cat_avg:
            overpriced.append({
                "id": str(p.id),
                "name": p.name,
                "sale_price": float(p.sale_price),
                "category_avg": round(cat_avg, 2),
                "suggested_price": round(cat_avg * 1.1, 2),
            })
    overpriced = overpriced[:10]

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
            "type": "reduction_prix",
            "priority": "moyenne",
            "title": f"Reduire le prix de {len(overpriced)} produits sur-evalues",
            "description": "Ces articles sont prix au-dessus de 1.5x la moyenne de leur categorie. Une reduction pourrait accelerer leur vente.",
            "products": overpriced,
        },
        {
            "type": "vitrine",
            "priority": "haute",
            "title": "Reorganiser la vitrine cette semaine",
            "description": f"Semaine {week} — Privilegier les pieces colorees et les marques premium en vitrine pour maximiser l'attractivite.",
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
            overpriced_summary = "\n".join(
                f"- {p['name']} (prix actuel: {p['sale_price']}€, suggere: {p['suggested_price']}€)"
                for p in overpriced[:5]
            )
            prompt = f"""Tu es un expert en boutique de seconde main premium.
Semaine {week}/{year}. Voici un résumé des produits en boutique:

Produits à faible score (à mettre en avant):
{product_summary or 'Aucun'}

Produits sur-évalués (à réduire):
{overpriced_summary or 'Aucun'}

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

    channels = None
    if anthropic_key:
        try:
            import anthropic as _anthropic
            client_ai = _anthropic.AsyncAnthropic(api_key=anthropic_key)
            prompt = """Tu es un expert en tendances mode pour une boutique de seconde main premium (Vintiz, Vernon, Normandie).
Nous sommes au printemps/été 2026.

Génère un rapport de tendances mode structuré en JSON avec exactement ce format:
{
  "reseaux_sociaux": {
    "summary": "résumé 1 phrase",
    "top_items": ["item1", "item2", "item3", "item4", "item5"],
    "colors": ["couleur1", "couleur2", "couleur3"]
  },
  "vinted": {
    "summary": "résumé 1 phrase",
    "top_categories": ["cat1", "cat2", "cat3"],
    "price_trends": "tendance prix en 1 phrase"
  },
  "retail": {
    "summary": "résumé 1 phrase",
    "key_trends": ["trend1", "trend2", "trend3"]
  }
}
Réponds UNIQUEMENT avec le JSON, sans markdown ni commentaire."""
            msg = await client_ai.messages.create(
                model="claude-haiku-4-5",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text if msg.content else "{}"
            channels = json.loads(raw)
        except Exception:
            channels = None

    if channels is None:
        # Static fallback for spring 2026
        channels = {
            "reseaux_sociaux": {
                "summary": "Le printemps 2026 est dominé par le 'quiet luxury' et les pièces structurées épurées.",
                "top_items": ["Blazer oversize", "Robe midi lin", "Pantalon large taille haute", "Veste en jean délavée", "Sac tote en cuir"],
                "colors": ["Camel", "Blanc cassé", "Vert sauge", "Abricot", "Bleu marine"],
            },
            "vinted": {
                "summary": "Les marques françaises premium (Sandro, Maje, Ba&sh) sont très recherchées avec des prix en hausse de 12%.",
                "top_categories": ["Robes", "Blazers", "Sacs à main"],
                "price_trends": "Hausse de 8-15% sur les pièces de marques françaises haut de gamme",
            },
            "retail": {
                "summary": "Les grandes enseignes misent sur le linen, la broderie et les imprimés botaniques pour l'été 2026.",
                "key_trends": ["Lin naturel et textures artisanales", "Imprimés floraux discrets", "Silhouettes fluides et structurées"],
            },
        }

    result = {
        "week": week,
        "year": year,
        "generated_at": now.isoformat(),
        "channels": channels,
    }
    await _set_setting(db, "ai_trends_mode_cache", json.dumps(result, ensure_ascii=False))
    await db.commit()
    return result


# ---------------------------------------------------------------------------
# Persona Marketing
# ---------------------------------------------------------------------------

@router.post("/persona/marketing")
async def generate_marketing_persona(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Generate a marketing manager persona report for the boutique."""
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

    anthropic_key = settings.ANTHROPIC_API_KEY or ""
    if anthropic_key:
        try:
            import anthropic
            client_ai = anthropic.AsyncAnthropic(api_key=anthropic_key)
            prompt = f"""Tu es un(e) directeur/directrice marketing externe mandaté(e) pour analyser la boutique Vintiz (Vernon, Normandie — seconde main premium).
Voici les données actuelles de la boutique :
- Articles en vente : {context['articles_en_vente']}
- Score tendance moyen du stock : {context['score_tendance_moyen']}/100
- Nombre de clients inscrits : {context['total_clients']}
- CA des 30 derniers jours : {context['ca_30_derniers_jours']} €
- Articles vendus au total : {context['articles_vendus_total']}

Génère un rapport marketing structuré en JSON avec exactement ce format :
{{
  "situation": "analyse en 2-3 phrases de la situation actuelle",
  "points_forts": ["force 1", "force 2", "force 3"],
  "points_faibles": ["faiblesse 1", "faiblesse 2", "faiblesse 3"],
  "recommandations": [
    {{"priorite": "haute", "action": "action concrète", "impact": "résultat attendu"}},
    {{"priorite": "haute", "action": "action concrète", "impact": "résultat attendu"}},
    {{"priorite": "moyenne", "action": "action concrète", "impact": "résultat attendu"}},
    {{"priorite": "faible", "action": "action concrète", "impact": "résultat attendu"}}
  ],
  "kpi_cibles": {{"ca_mensuel_cible": 0, "nouveaux_clients_mois": 0, "taux_conversion_vitrine": "X%"}}
}}
Réponds UNIQUEMENT avec le JSON, sans markdown."""
            msg = await client_ai.messages.create(
                model="claude-haiku-4-5",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            import json
            raw = msg.content[0].text if msg.content else "{}"
            report = json.loads(raw)
            return {
                "generated_at": now.isoformat(),
                "context": context,
                "report": report,
            }
        except Exception:
            pass

    # Static fallback
    return {
        "generated_at": now.isoformat(),
        "context": context,
        "report": {
            "situation": f"La boutique Vintiz dispose d'un stock de {total_products} articles en vente avec un score tendance moyen de {round(avg_score, 1)}/100. La base clients compte {total_clients} personnes avec un CA récent de {round(ca_30d, 2)} €.",
            "points_forts": [
                "Positionnement premium distinctif sur le marché de la seconde main",
                "Score tendance utilisé pour l'optimisation du stock",
                "Système de fidélité en place pour la rétention client",
            ],
            "points_faibles": [
                "Visibilité digitale à renforcer pour attirer de nouveaux clients",
                "Programme CRM à développer (email, SMS, espace client)",
                "Conversion vitrine à optimiser via le merchandising",
            ],
            "recommandations": [
                {"priorite": "haute", "action": "Lancer une campagne Instagram ciblée femmes 25-45 ans Vernon/Évreux", "impact": "+20% de nouveaux clients"},
                {"priorite": "haute", "action": "Créer une newsletter mensuelle avec les nouvelles arrivées", "impact": "+15% de taux de retour"},
                {"priorite": "moyenne", "action": "Développer des partenariats avec influenceurs mode locaux", "impact": "+10% CA mensuel"},
                {"priorite": "faible", "action": "Mettre en place un programme de parrainage clients", "impact": "Acquisition clients à moindre coût"},
            ],
            "kpi_cibles": {
                "ca_mensuel_cible": int(ca_30d * 1.2) or 3000,
                "nouveaux_clients_mois": 8,
                "taux_conversion_vitrine": "12%",
            },
        },
    }


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
            Transaction.type == TransactionType.sale,
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
            Transaction.type == TransactionType.sale,
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
