"""AI Store mapping service.

Manages store zones and product placement recommendations.
Uses sales data and trend scores to optimize product placement.
"""

import json
import logging
from datetime import datetime, timedelta

import anthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Product, ProductStatus
from app.models.store import (
    AIRecommendation,
    StoreZone,
)

logger = logging.getLogger("vintiz.ai.mapping")

# Default zones for Vintiz boutique — Lot N°2, S. utile 183,95 m² (magasin 98,70 m²).
# Refonte 2026-05 : 14 zones avec règles d'affectation conditionnelles
# (genre / couleur / taille / catégorie / score tendance). Coordonnées en %
# du canvas (0-100) ; entrée à droite, mur du fond en haut, façade en bas.
#
# IMPORTANT — garder synchronisé sur les NOMS de zones avec :
#   - alembic/versions/0043_store_zone_rules_and_remap.py (TARGET_ZONES)
#   - apps/web/src/app/ia/page.tsx (ZONE_LAYOUT)
# product_types est stocké en chaîne JSON (colonne TEXT) ; match_* sont des
# listes Python (colonnes JSONType). "None/[] = pas de contrainte" sur l'axe.
DEFAULT_ZONES = [
    {
        "name": "Vitrine", "description": "Vitrine devanture cote entree — exposition tendance",
        "capacity": 8, "color_code": "#006B61", "icon": "star",
        "pos_x": 84, "pos_y": 80, "width": 12, "height": 15, "shape": "rounded", "display_order": 1,
        "photo_url": "/zones/vitrine.jpeg",
        "match_genders": None, "match_colors": None, "match_size_classes": None,
        "product_types": None, "min_trend_score": 75, "assignment_priority": 10,
    },
    {
        "name": "Chaussures droite femme", "description": "Mur droit — chaussures femme",
        "capacity": 48, "color_code": "#FFC5DF", "icon": "bag",
        "pos_x": 4, "pos_y": 22, "width": 13, "height": 20, "shape": "rect", "display_order": 2,
        "photo_url": "/zones/extra-2.jpeg",
        "match_genders": ["femme"], "match_colors": None, "match_size_classes": None,
        "product_types": json.dumps(["chaussures", "chaussure", "escarpin", "botte", "basket", "sandale"]),
        "min_trend_score": None, "assignment_priority": 20,
    },
    {
        "name": "Chaussures H", "description": "Coin facade gauche — chaussures homme",
        "capacity": 28, "color_code": "#3B82F6", "icon": "bag",
        "pos_x": 6, "pos_y": 80, "width": 14, "height": 15, "shape": "rect", "display_order": 3,
        "photo_url": "/zones/chaussures-h.jpeg",
        "match_genders": ["homme"], "match_colors": None, "match_size_classes": None,
        "product_types": json.dumps(["chaussures", "chaussure", "basket", "botte", "mocassin", "sneaker"]),
        "min_trend_score": None, "assignment_priority": 21,
    },
    {
        "name": "Portant Rond Homme", "description": "Portant rond homme — pieces structurees",
        "capacity": 100, "color_code": "#1E40AF", "icon": "grid",
        "pos_x": 24, "pos_y": 42, "width": 16, "height": 14, "shape": "rounded", "display_order": 4,
        "match_genders": ["homme"], "match_colors": None, "match_size_classes": None,
        "product_types": json.dumps(["polo", "chemise", "veste", "chemisette", "haut"]),
        "min_trend_score": None, "assignment_priority": 30,
    },
    {
        "name": "Portant Homme", "description": "Portant homme — basiques",
        "capacity": 280, "color_code": "#1E3A8A", "icon": "grid",
        "pos_x": 24, "pos_y": 60, "width": 18, "height": 15, "shape": "rounded", "display_order": 5,
        "match_genders": ["homme"], "match_colors": None, "match_size_classes": None,
        "product_types": json.dumps(["polo", "t-shirt", "tshirt", "tee-shirt", "bermuda", "short", "shirt"]),
        "min_trend_score": None, "assignment_priority": 31,
    },
    {
        "name": "Hommes", "description": "Mur facade — collection homme (fourre-tout)",
        "capacity": 210, "color_code": "#172554", "icon": "shirt",
        "pos_x": 24, "pos_y": 82, "width": 18, "height": 13, "shape": "rect", "display_order": 6,
        "photo_url": "/zones/hommes.jpeg",
        "match_genders": ["homme"], "match_colors": None, "match_size_classes": None,
        "product_types": None, "min_trend_score": None, "assignment_priority": 32,
    },
    {
        "name": "Tendance", "description": "Tete de gondole facade — selon scoring tendance",
        "capacity": 200, "color_code": "#CC4889", "icon": "sparkles",
        "pos_x": 46, "pos_y": 80, "width": 24, "height": 15, "shape": "rounded", "display_order": 7,
        "photo_url": "/zones/tendance.jpeg",
        "match_genders": None, "match_colors": None, "match_size_classes": None,
        "product_types": None, "min_trend_score": 70, "assignment_priority": 40,
    },
    {
        "name": "Droite 3", "description": "Mur droit fond — femme grandes tailles + robes longues",
        "capacity": 115, "color_code": "#008678", "icon": "shirt",
        "pos_x": 8, "pos_y": 4, "width": 20, "height": 14, "shape": "rect", "display_order": 8,
        "photo_url": "/zones/extra-1.jpeg",
        "match_genders": ["femme"], "match_colors": None, "match_size_classes": ["grande"],
        "product_types": None, "min_trend_score": None, "assignment_priority": 50,
    },
    {
        "name": "Portant 2", "description": "Portant femme — petites tailles, jupes/chemisiers/shirts",
        "capacity": 280, "color_code": "#FF97C0", "icon": "grid",
        "pos_x": 40, "pos_y": 44, "width": 18, "height": 14, "shape": "rounded", "display_order": 9,
        "match_genders": ["femme"], "match_colors": None, "match_size_classes": ["petite"],
        "product_types": json.dumps(["jupe", "jupes", "chemisier", "chemisiers", "shirt", "chemise"]),
        "min_trend_score": None, "assignment_priority": 51,
    },
    {
        "name": "Entrée", "description": "Entree cote droit — femme rose/rouge",
        "capacity": 85, "color_code": "#FF6FA5", "icon": "shirt",
        "pos_x": 76, "pos_y": 2, "width": 20, "height": 12, "shape": "rect", "display_order": 10,
        "match_genders": ["femme"], "match_colors": ["rose", "rouge"], "match_size_classes": None,
        "product_types": None, "min_trend_score": None, "assignment_priority": 60,
    },
    {
        "name": "Droite 1", "description": "Mur droit — femme bleu/blanc/violet",
        "capacity": 155, "color_code": "#26A695", "icon": "shirt",
        "pos_x": 53, "pos_y": 2, "width": 20, "height": 12, "shape": "rect", "display_order": 11,
        "photo_url": "/zones/standard-1.jpeg",
        "match_genders": ["femme"], "match_colors": ["bleu", "blanc", "violet"], "match_size_classes": None,
        "product_types": None, "min_trend_score": None, "assignment_priority": 61,
    },
    {
        "name": "Droite 2", "description": "Mur droit centre — femme vert/noir/marron",
        "capacity": 155, "color_code": "#1A7A6A", "icon": "shirt",
        "pos_x": 30, "pos_y": 2, "width": 20, "height": 12, "shape": "rect", "display_order": 12,
        "photo_url": "/zones/standard-2.jpeg",
        "match_genders": ["femme"], "match_colors": ["vert", "noir", "marron"], "match_size_classes": None,
        "product_types": None, "min_trend_score": None, "assignment_priority": 62,
    },
    {
        "name": "Portant 1", "description": "Portant femme — rouge/jaune/orange/marron",
        "capacity": 10, "color_code": "#F59E0B", "icon": "grid",
        "pos_x": 44, "pos_y": 26, "width": 16, "height": 13, "shape": "rounded", "display_order": 13,
        "match_genders": ["femme"], "match_colors": ["rouge", "jaune", "orange", "marron"], "match_size_classes": None,
        "product_types": None, "min_trend_score": None, "assignment_priority": 63,
    },
    {
        "name": "Portant Rond Femme", "description": "Portant rond femme — pieces structurees",
        "capacity": 100, "color_code": "#EC4899", "icon": "grid",
        "pos_x": 64, "pos_y": 28, "width": 16, "height": 14, "shape": "rounded", "display_order": 14,
        "match_genders": ["femme"], "match_colors": None, "match_size_classes": None,
        "product_types": json.dumps(["chemisier", "veste", "chemisette", "haut"]),
        "min_trend_score": None, "assignment_priority": 70,
    },
]


async def init_default_zones(db: AsyncSession) -> list[dict]:
    """Initialize the default store zones if none exist."""
    existing = await db.execute(select(func.count(StoreZone.id)))
    count = existing.scalar_one()
    if count > 0:
        zones = await db.execute(select(StoreZone))
        return [
            {
                "id": str(z.id),
                "name": z.name,
                "description": z.description,
                "capacity": z.capacity,
            }
            for z in zones.scalars().all()
        ]

    created = []
    for zone_data in DEFAULT_ZONES:
        zone = StoreZone(**zone_data)
        db.add(zone)
        await db.flush()
        await db.refresh(zone)
        created.append({
            "id": str(zone.id),
            "name": zone.name,
            "description": zone.description,
            "capacity": zone.capacity,
        })

    return created


async def get_zone_stats(db: AsyncSession) -> list[dict]:
    """Get stats for each zone: product count, total value, avg trend score."""
    zones_result = await db.execute(select(StoreZone))
    zones = zones_result.scalars().all()

    stats = []
    for zone in zones:
        # Count products in this zone
        prod_result = await db.execute(
            select(
                func.count(Product.id),
                func.coalesce(func.sum(Product.sale_price), 0),
                func.coalesce(func.avg(Product.trend_score), 0),
            ).where(
                Product.zone_id == zone.id,
                Product.status.in_([ProductStatus.stock, ProductStatus.display]),
            )
        )
        row = prod_result.one()

        stats.append({
            "zone_id": str(zone.id),
            "zone_name": zone.name,
            "description": zone.description,
            "capacity": zone.capacity,
            "product_count": row[0],
            "occupancy_percent": round(row[0] / zone.capacity * 100) if zone.capacity > 0 else 0,
            "total_value": float(row[1]),
            "avg_trend_score": round(float(row[2]), 1),
        })

    return stats


async def generate_arrangement_recommendations(db: AsyncSession) -> dict:
    """Use Claude to generate store arrangement recommendations.

    Analyzes current stock, trend scores, and sales data to suggest
    optimal product placement across zones.
    """
    # Gather context data
    zone_stats = await get_zone_stats(db)

    # Get top trending products
    trending_result = await db.execute(
        select(Product)
        .where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
            Product.trend_score.is_not(None),
        )
        .order_by(Product.trend_score.desc())
        .limit(20)
    )
    trending = [
        {
            "name": p.name,
            "category": p.category.name if p.category else "?",
            "price": float(p.sale_price),
            "trend_score": p.trend_score,
            "zone": None,
        }
        for p in trending_result.scalars().all()
    ]

    # Get stale products
    four_weeks_ago = datetime.now() - timedelta(weeks=4)
    stale_result = await db.execute(
        select(Product).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
            Product.created_at < four_weeks_ago,
        ).order_by(Product.created_at.asc()).limit(10)
    )
    stale = [
        {
            "name": p.name,
            "category": p.category.name if p.category else "?",
            "price": float(p.sale_price),
            "days_on_shelf": (datetime.now() - p.created_at.replace(tzinfo=None)).days,
        }
        for p in stale_result.scalars().all()
    ]

    # Recent top-selling categories
    two_weeks_ago = datetime.now() - timedelta(weeks=2)
    cat_sales = await db.execute(
        select(
            Product.category_id,
            func.count(TransactionItem.id).label("sales"),
        )
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .where(
            Transaction.created_at >= two_weeks_ago,
            Transaction.transaction_type == TransactionType.sale,
        )
        .group_by(Product.category_id)
        .order_by(func.count(TransactionItem.id).desc())
        .limit(5)
    )
    hot_categories = [{"category_id": str(r[0]), "sales": r[1]} for r in cat_sales.all()]

    if not settings.ANTHROPIC_API_KEY:
        return {
            "status": "no_api_key",
            "message": "Cle API Anthropic non configuree. Recommendations manuelles uniquement.",
        }

    # Build prompt for Claude
    context = {
        "zones": zone_stats,
        "trending_products": trending,
        "stale_products": stale,
        "hot_categories": hot_categories,
    }

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system="""Tu es un conseiller merchandising expert pour Vintiz, une boutique de vetements seconde main premium a Vernon (Lot N°2, surface utile 183,95 m² dont 98,70 m² magasin).

La boutique est en forme de L, entree a droite, 14 zones :
1. Entrée (mur droit cote entree, femme rose/rouge, 85 pieces)
2. Droite 1 (mur droit, femme bleu/blanc/violet, 155 pieces)
3. Droite 2 (mur droit centre, femme vert/noir/marron, 155 pieces)
4. Droite 3 (mur droit fond, femme grandes tailles + robes longues, 115 pieces)
5. Chaussures droite femme (mur droit, chaussures femme, 48 paires)
6. Portant 1 (portant femme rouge/jaune/orange/marron, 10 pieces)
7. Portant 2 (portant femme petites tailles, jupes/chemisiers/shirts, 280 pieces)
8. Portant Rond Femme (portant rond femme : chemisier/veste/chemisette/haut, 100 pieces)
9. Portant Rond Homme (portant rond homme : polo/chemise/veste/chemisette/haut, 100 pieces)
10. Portant Homme (portant homme : polo/t-shirt/bermuda/short/shirt, 280 pieces)
11. Hommes (mur facade, collection homme fourre-tout, 210 pieces)
12. Chaussures H (coin facade gauche, chaussures homme, 28 paires)
13. Tendance (tete de gondole facade, pieces a fort score tendance, 200 pieces)
14. Vitrine (devanture cote entree, exposition tendance, ~8 pieces)

Zones homme : Chaussures H, Portant Rond Homme, Portant Homme, Hommes. Le
reste est feminin. Tendance et Vitrine accueillent les pieces a fort score
tendance (tout genre), independamment du code couleur.

Principes merchandising :
- Vitrine et Tendance : pieces a fort score tendance, rotation hebdo
- Zones Droite 1/2 + Entrée : femme triees par code couleur, fortes capacites
- Droite 3 : femme grandes tailles et robes longues
- Portant 1/2 : portants femme (Portant 1 couleurs vives, Portant 2 petites tailles)
- Portant Rond Femme/Homme : pieces structurees (chemises, vestes, polos)
- Chaussures droite femme / Chaussures H : focus matiere et taille
- Hommes : mur homme fourre-tout en facade
- Les produits stagnants sont deplaces vers Tendance/Vitrine ou demarques

Reponds en JSON avec :
{
  "recommendations": [
    {
      "action": "deplacer|mettre_en_avant|demarquer|retirer",
      "product_name": "...",
      "from_zone": "..." ou null,
      "to_zone": "...",
      "reason": "..."
    }
  ],
  "zone_suggestions": [
    {
      "zone": "...",
      "theme_suggere": "...",
      "conseil": "..."
    }
  ],
  "resume": "Resume en 2-3 phrases des recommandations principales"
}""",
        messages=[
            {
                "role": "user",
                "content": f"Voici l'etat actuel de la boutique. Genere des recommandations de merchandising.\n\n{json.dumps(context, ensure_ascii=False, indent=2)}",
            }
        ],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse AI mapping response: %s", raw[:300])
        result = {"error": "Reponse IA invalide", "raw": raw[:500]}

    # Save recommendation
    recommendation = AIRecommendation(
        recommendation_type="arrangement",
        content=result,
        confidence=0.8,
    )
    db.add(recommendation)
    await db.flush()

    return result


async def assign_product_to_zone(
    db: AsyncSession, product_id: str, zone_id: str
) -> dict:
    """Assign a product to a store zone."""
    product = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    p = product.scalar_one_or_none()
    if not p:
        return {"error": "Produit non trouve"}

    zone = await db.execute(
        select(StoreZone).where(StoreZone.id == zone_id)
    )
    z = zone.scalar_one_or_none()
    if not z:
        return {"error": "Zone non trouvee"}

    p.zone_id = zone_id
    await db.flush()

    return {
        "product_id": str(p.id),
        "product_name": p.name,
        "zone_id": str(z.id),
        "zone_name": z.name,
    }
