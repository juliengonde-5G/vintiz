"""AI Booster API endpoints.

Provides:
- Photo analysis (Claude Vision)
- Trend scoring
- Price suggestions
- Store mapping & recommendations
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.ai_vision import analyze_product_photo, analyze_photo_from_url
from app.services.ai_trend import compute_trend_scores, update_product_scores, get_stale_products
from app.services.ai_pricing import suggest_price, suggest_markdowns
from app.services.ai_mapping import (
    init_default_zones,
    get_zone_stats,
    generate_arrangement_recommendations,
    assign_product_to_zone,
)

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
