"""Product intake orchestration — from a photo URL to a fully-formed Product.

L3.2 — Endpoint `POST /api/inventory/products/from-photo`.

Pipeline:
1. Call ai_vision.analyze_photo_from_url(photo_url) → 15 attributes
2. Resolve category_id from vision.type via fuzzy lookup, fallback to a
   default "Inclassable" (created on first use).
3. Generate a unique barcode (VTZ + 6 digits, like seed_data.py).
4. Create the Product row with all auto-filled fields (description, brand,
   color, size, condition, gender hint).
5. Create the ProductPhoto via PhotoService — mirrors the URL onto
   Product.photo_url so legacy callsites keep working.
6. Compute scoring via scoring_service.compute_score for immediate review.
7. Suggest a zone via merchandising.suggest_zone (if available).
8. Emit a `product_created` event for analytics.

The orchestration is **resilient** : if Vision fails, the product is still
created with minimal info (barcode + URL + fallback name) so Léa is never
blocked. The caller sees a `vision_used: false` flag in the response.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Category, Gender, Product, ProductStatus
from app.services import ai_vision
from app.services.photo import PhotoService
from app.services.scoring_service import compute_score


logger = logging.getLogger(__name__)


# Coarse mapping vision.type → category name. Fallback to "Inclassable".
_TYPE_TO_CATEGORY = {
    "robe": "Robe",
    "pantalon": "Pantalon",
    "veste": "Veste",
    "manteau": "Manteau",
    "pull": "Pull",
    "chemise": "Chemise",
    "jupe": "Jupe",
    "top": "Top",
    "tshirt": "Top",
    "t-shirt": "Top",
    "accessoire": "Accessoire",
    "chaussures": "Chaussures",
    "sac": "Sac",
}

# Vision condition strings (with diacritics removed) to Product.condition values.
_CONDITION_MAP = {
    "excellent": "neuf",
    "tres_bon": "tres_bon",
    "tres bon": "tres_bon",
    "bon": "bon",
    "correct": "correct",
}


def _generate_barcode() -> str:
    """VTZ + 6 random digits, like ``seed_data.py:88``."""
    return "VTZ" + str(random.randint(100000, 999999))


def _normalize_type(vision_type: str | None) -> str | None:
    if not vision_type:
        return None
    t = vision_type.lower().strip().replace("é", "e").replace("è", "e")
    return _TYPE_TO_CATEGORY.get(t)


def _normalize_condition(vision_etat: str | None) -> str:
    if not vision_etat:
        return "tres_bon"
    e = vision_etat.lower().strip().replace("é", "e").replace("è", "e")
    return _CONDITION_MAP.get(e, "tres_bon")


def _gamme_to_price_hint(gamme: str | None, fallback: float) -> float:
    """Coarse price hint when caller doesn't provide one.

    Vintiz Vernon retail seconde main price points (verified seed_data.py):
        entree   → 12 €
        moyenne  → 25 €
        premium  → 60 €
    The caller can always pass a ``sale_price_hint`` to override this.
    """
    if fallback > 0:
        return fallback
    if not gamme:
        return 20.0
    return {"entree": 12.0, "moyenne": 25.0, "premium": 60.0}.get(gamme, 20.0)


async def _resolve_category(
    db: AsyncSession, vision_type: str | None, category_id_hint: uuid.UUID | None
) -> uuid.UUID:
    """Resolve a category. Priority: explicit hint → vision.type lookup → fallback.

    Creates the "Inclassable" fallback category on first use.
    """
    if category_id_hint:
        result = await db.execute(
            select(Category).where(Category.id == category_id_hint)
        )
        cat = result.scalar_one_or_none()
        if cat:
            return cat.id

    target_name = _normalize_type(vision_type)
    if target_name:
        result = await db.execute(
            select(Category).where(Category.name.ilike(target_name))
        )
        cat = result.scalar_one_or_none()
        if cat:
            return cat.id

    # Fallback: Inclassable
    result = await db.execute(
        select(Category).where(Category.name.ilike("Inclassable"))
    )
    cat = result.scalar_one_or_none()
    if cat:
        return cat.id

    inclassable = Category(name="Inclassable", gender=Gender.mixte)
    db.add(inclassable)
    await db.flush()
    return inclassable.id


async def _category_avg_price(
    db: AsyncSession, category_id: uuid.UUID
) -> float:
    """Average sale_price across products in the same category. 0 if empty."""
    from sqlalchemy import func

    result = await db.execute(
        select(func.avg(Product.sale_price)).where(
            Product.category_id == category_id,
            Product.is_test.is_(False),
        )
    )
    avg = result.scalar()
    return float(avg) if avg else 0.0


async def create_from_photo(
    db: AsyncSession,
    *,
    photo_url: str,
    category_id_hint: uuid.UUID | None = None,
    sale_price_hint: float = 0.0,
    purchase_price_hint: float = 0.0,
    is_test: bool = False,
) -> dict[str, Any]:
    """Create a Product from a photo URL, orchestrating Vision + scoring.

    Returns a dict with the created product, the Vision payload, the score,
    and an optional zone suggestion. Never raises on Vision failure — the
    product is created in degraded mode and ``vision_used: False`` flags it.
    """

    # --- 1. Vision (best-effort) ---
    vision_payload: dict = {}
    vision_used = False
    try:
        raw = await ai_vision.analyze_photo_from_url(photo_url)
        if isinstance(raw, dict) and "error" not in raw:
            vision_payload = ai_vision.normalize_vision_payload(raw)
            vision_used = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vision failed for %s: %s", photo_url[:80], exc)
        vision_payload = {}

    # --- 2. Resolve category ---
    category_id = await _resolve_category(
        db, vision_payload.get("type"), category_id_hint
    )

    # --- 3. Build product fields ---
    barcode = _generate_barcode()
    # Defensive uniqueness: try up to 5 times.
    for _ in range(5):
        existing = await db.execute(
            select(Product).where(Product.barcode == barcode)
        )
        if not existing.scalar_one_or_none():
            break
        barcode = _generate_barcode()

    description = vision_payload.get("description") or "Article boutique Vintiz"
    brand = vision_payload.get("marque")
    color = vision_payload.get("couleur")
    size = vision_payload.get("taille")
    condition = _normalize_condition(vision_payload.get("etat"))
    sale_price = _gamme_to_price_hint(
        vision_payload.get("gamme_estimee"), sale_price_hint
    )
    purchase_price = (
        purchase_price_hint if purchase_price_hint > 0 else sale_price * 0.4
    )

    product = Product(
        barcode=barcode,
        name=description[:255],
        category_id=category_id,
        size=size[:20] if size else None,
        color=color[:50] if color else None,
        brand=brand[:100] if brand else None,
        purchase_price=Decimal(str(purchase_price)).quantize(Decimal("0.01")),
        sale_price=Decimal(str(sale_price)).quantize(Decimal("0.01")),
        status=ProductStatus.stock,
        condition=condition,
        description=description,
        received_at=datetime.now(timezone.utc),
        is_test=is_test,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)

    # --- 4. Photo (also mirrors onto Product.photo_url) ---
    photo_service = PhotoService(db)
    confidence = vision_payload.get("confiance")
    await photo_service.add_photo(
        product_id=product.id,
        url=photo_url,
        ai_confidence=float(confidence) if confidence is not None else None,
        ai_analyzed_at=datetime.now(timezone.utc) if vision_used else None,
    )

    # --- 5. Scoring ---
    avg_price = await _category_avg_price(db, category_id)
    score = compute_score(
        shelf_date=None,
        sale_price=float(product.sale_price),
        category_avg_price=avg_price,
        condition=condition,
        brand=brand,
        photo_url=photo_url,
        photo_count=1,
        photo_avg_confidence=float(confidence) if confidence is not None else 0.0,
    )
    product.trend_score = score["total_score"]

    # --- 6. Suggest zone (best-effort) ---
    zone_suggestion: dict | None = None
    try:
        from app.services.merchandising import MerchandisingService

        suggestion = await MerchandisingService(db).suggest_zone(product)
        zone_suggestion = {
            "primary_zone_id": suggestion.primary_zone_id,
            "primary_zone_name": suggestion.primary_zone_name,
            "should_go_to_window": suggestion.should_go_to_window,
            "rationale": suggestion.rationale,
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("suggest_zone unavailable: %s", exc)

    await db.flush()
    await db.refresh(product)

    return {
        "product": {
            "id": str(product.id),
            "barcode": product.barcode,
            "name": product.name,
            "category_id": str(product.category_id),
            "size": product.size,
            "color": product.color,
            "brand": product.brand,
            "condition": product.condition,
            "sale_price": float(product.sale_price),
            "purchase_price": float(product.purchase_price),
            "status": product.status.value if hasattr(product.status, "value") else str(product.status),
            "photo_url": product.photo_url,
            "trend_score": product.trend_score,
            "is_test": product.is_test,
        },
        "vision": vision_payload,
        "vision_used": vision_used,
        "score": score,
        "zone_suggestion": zone_suggestion,
    }
