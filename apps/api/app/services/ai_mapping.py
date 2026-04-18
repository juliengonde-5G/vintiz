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
    StoreArrangement,
    StoreZone,
    ZoneProduct,
)

logger = logging.getLogger("vintiz.ai.mapping")

# Default zones for Vintiz boutique (from architectural analysis)
# pos_x / pos_y / width / height : percentage of canvas (0-100), positioned on a L-shape floor plan.
DEFAULT_ZONES = [
    {
        "name": "Vitrine gauche", "description": "Exposition exterieure cote gauche",
        "capacity": 6, "color_code": "#008678", "icon": "sparkles",
        "pos_x": 4, "pos_y": 4, "width": 28, "height": 14, "shape": "rounded", "display_order": 1,
    },
    {
        "name": "Podium entree", "description": "Zone mise en avant a l'entree (6.5m2)",
        "capacity": 10, "color_code": "#FFC5DF", "icon": "star",
        "pos_x": 36, "pos_y": 8, "width": 20, "height": 20, "shape": "rounded", "display_order": 2,
    },
    {
        "name": "Mur gauche", "description": "Barres murales portants lineaires",
        "capacity": 30, "color_code": "#26A695", "icon": "shirt",
        "pos_x": 4, "pos_y": 22, "width": 14, "height": 50, "shape": "rect", "display_order": 3,
    },
    {
        "name": "Mur droit", "description": "Zone meuble caisse + stockage",
        "capacity": 15, "color_code": "#CC4889", "icon": "cash",
        "pos_x": 78, "pos_y": 32, "width": 18, "height": 30, "shape": "rect", "display_order": 4,
    },
    {
        "name": "Mur fond", "description": "Barres murales + etageres bois",
        "capacity": 25, "color_code": "#006B61", "icon": "bag",
        "pos_x": 22, "pos_y": 78, "width": 54, "height": 14, "shape": "rect", "display_order": 5,
    },
    {
        "name": "Zone centrale", "description": "Autour du pilier - portants libres",
        "capacity": 20, "color_code": "#FF97C0", "icon": "grid",
        "pos_x": 34, "pos_y": 40, "width": 34, "height": 28, "shape": "rounded", "display_order": 6,
    },
    {
        "name": "Cabine essayage", "description": "Zone fond boutique - suggestions",
        "capacity": 0, "color_code": "#B3DDD8", "icon": "door",
        "pos_x": 82, "pos_y": 6, "width": 14, "height": 18, "shape": "rounded", "display_order": 7,
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
        system="""Tu es un conseiller merchandising expert pour Vintiz, une boutique de vetements seconde main premium feminin a Vernon.

La boutique fait ~98m2 en forme de L avec 7 zones :
1. Vitrine gauche (exposition exterieure)
2. Podium entree (6.5m2, mise en avant)
3. Mur gauche (barres murales, portants lineaires)
4. Mur droit (meuble caisse + stockage)
5. Mur fond (barres murales + etageres)
6. Zone centrale (autour pilier, portants libres)
7. Cabine essayage (suggestions visuelles)

Principes merchandising :
- Vitrine et podium : pieces les plus attractives (tendance haute, prix moyen-haut)
- Entree droite/gauche : categories qui se vendent le mieux
- Fond : pieces a decouvrir, petits prix, destockage
- Zone centrale : mix tendance + nouveautes
- Les produits stagnants doivent etre deplaces vers des zones plus visibles ou demarques

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
    week_number = datetime.now().isocalendar()[1]
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
