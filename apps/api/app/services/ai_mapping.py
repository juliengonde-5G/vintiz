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
# Layout aligned with `plan.jpg` and the photo plate (Standard 1/2, Extra 1/2,
# Chaussures F/H, Hommes, Tendances, Vitrine). Coordinates are percentages of
# the canvas (0-100) ; the entrée is à droite, la vitrine tendance en façade.
DEFAULT_ZONES = [
    # ---- Mur du fond (back wall, top of plan), de droite (entrée) à gauche ----
    {
        "name": "Petits Prix 1", "description": "Mur du fond cote entree — femme, prix doux",
        "capacity": 200, "color_code": "#26A695", "icon": "shirt",
        "pos_x": 72, "pos_y": 2, "width": 24, "height": 12, "shape": "rect", "display_order": 1,
        "photo_url": "/zones/standard-1.jpeg",
    },
    {
        "name": "Petits Prix 2", "description": "Mur du fond centre — femme, prix doux",
        "capacity": 200, "color_code": "#26A695", "icon": "shirt",
        "pos_x": 46, "pos_y": 2, "width": 24, "height": 12, "shape": "rect", "display_order": 2,
        "photo_url": "/zones/standard-2.jpeg",
    },
    {
        "name": "Extra 1", "description": "Mur du fond — selection extra femme",
        "capacity": 150, "color_code": "#008678", "icon": "shirt",
        "pos_x": 24, "pos_y": 4, "width": 20, "height": 14, "shape": "rect", "display_order": 3,
        "photo_url": "/zones/extra-1.jpeg",
    },
    {
        "name": "Extra 2", "description": "Retour mur — selection extra femme",
        "capacity": 150, "color_code": "#008678", "icon": "shirt",
        "pos_x": 12, "pos_y": 18, "width": 12, "height": 22, "shape": "rect", "display_order": 4,
        "photo_url": "/zones/extra-2.jpeg",
    },
    # ---- Cote gauche (left wall + portants centraux femme) ----
    {
        "name": "Chaussures F", "description": "Mur gauche pres des cabines — chaussures femme",
        "capacity": 30, "color_code": "#FFC5DF", "icon": "bag",
        "pos_x": 12, "pos_y": 42, "width": 12, "height": 18, "shape": "rect", "display_order": 5,
        "photo_url": "/zones/chaussures-f.jpeg",
    },
    {
        "name": "Portants Standards 1", "description": "Portant central femme (haut)",
        "capacity": 120, "color_code": "#FF97C0", "icon": "grid",
        "pos_x": 44, "pos_y": 28, "width": 22, "height": 18, "shape": "rounded", "display_order": 6,
    },
    {
        "name": "Portants Standards 2", "description": "Portant central femme (bas)",
        "capacity": 120, "color_code": "#FF97C0", "icon": "grid",
        "pos_x": 22, "pos_y": 58, "width": 22, "height": 18, "shape": "rounded", "display_order": 7,
    },
    # ---- Mur facade (bottom of plan), de gauche a droite ----
    {
        "name": "Chaussures H", "description": "Coin facade gauche — chaussures homme",
        "capacity": 30, "color_code": "#3B82F6", "icon": "bag",
        "pos_x": 22, "pos_y": 80, "width": 14, "height": 15, "shape": "rect", "display_order": 8,
        "photo_url": "/zones/chaussures-h.jpeg",
    },
    {
        "name": "Hommes", "description": "Mur facade — collection homme complete",
        "capacity": 150, "color_code": "#1E3A8A", "icon": "shirt",
        "pos_x": 38, "pos_y": 82, "width": 18, "height": 13, "shape": "rect", "display_order": 9,
        "photo_url": "/zones/hommes.jpeg",
    },
    {
        "name": "Tendance", "description": "Tete de gondole facade — tendance femme",
        "capacity": 200, "color_code": "#CC4889", "icon": "sparkles",
        "pos_x": 58, "pos_y": 80, "width": 24, "height": 15, "shape": "rounded", "display_order": 10,
        "photo_url": "/zones/tendance.jpeg",
    },
    # ---- Vitrine (devanture cote entree, exposition uniquement) ----
    {
        "name": "Vitrine", "description": "Vitrine devanture cote entree — exposition uniquement",
        "capacity": 8, "color_code": "#006B61", "icon": "star",
        "pos_x": 84, "pos_y": 80, "width": 12, "height": 15, "shape": "rounded", "display_order": 11,
        "photo_url": "/zones/vitrine.jpeg",
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

La boutique est en forme de L, entree a droite, 11 zones :
1. Petits Prix 1 (mur du fond cote entree, femme, 200 pieces)
2. Petits Prix 2 (mur du fond centre, femme, 200 pieces)
3. Extra 1 (mur du fond, femme, 150 pieces)
4. Extra 2 (retour mur cote gauche, femme, 150 pieces)
5. Chaussures F (mur gauche pres des cabines, 30 paires)
6. Portants Standards 1 (portant central femme haut, 120 pieces)
7. Portants Standards 2 (portant central femme bas, 120 pieces)
8. Chaussures H (coin facade gauche, 30 paires homme)
9. Hommes (mur facade, collection homme complete, 150 pieces)
10. Tendance (tete de gondole facade femme, 200 pieces)
11. Vitrine (devanture cote entree, exposition uniquement, ~8 pieces)

Toutes les zones sont feminines a l'exception de Chaussures H et Hommes.

Principes merchandising :
- Vitrine et Tendance : pieces tendance haute, prix moyen-haut, rotation hebdo
- Petits Prix 1/2 : entree de gamme femme, fortes capacites, rotation rapide
- Extra 1/2 : selections premium femme, mise en valeur
- Portants Standards : mix tendance + nouveautes femme au centre
- Chaussures F/H : focus matiere et taille, peu de stock
- Hommes : zone homme dediee en facade
- Les produits stagnants sont deplaces vers Tendance/Vitrine ou demarques en Petits Prix

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
