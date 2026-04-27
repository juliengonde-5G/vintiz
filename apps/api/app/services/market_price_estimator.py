"""Estimate the median market price (Vinted / LeBonCoin) for a product.

Used by the v3 scoring engine for the *Positionnement prix* criterion.

Strategy:
1. Cached estimate stored on the product (column ``market_price_estimate``)
   refreshed weekly or when the manager edits the product.
2. Fresh estimate via Claude Haiku given category + brand + condition + color.
3. Fallback : average sale price of the same category in the catalogue
   (deterministic, no API key required, regression-safe).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductStatus


logger = logging.getLogger("vintiz")


_REFRESH_INTERVAL = timedelta(days=7)


def _is_estimate_fresh(updated_at: Optional[datetime]) -> bool:
    if updated_at is None:
        return False
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - updated_at < _REFRESH_INTERVAL


async def _category_average_price(db: AsyncSession, category_id) -> float | None:
    if category_id is None:
        return None
    result = await db.execute(
        select(func.avg(Product.sale_price)).where(
            Product.category_id == category_id,
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
        )
    )
    avg = result.scalar_one_or_none()
    return float(avg) if avg else None


async def _estimate_via_claude(
    *,
    category_name: str | None,
    brand: str | None,
    condition: str | None,
    color: str | None,
    sale_price: float,
) -> float | None:
    """Ask Claude Haiku for a median market price.

    Returns ``None`` if no API key configured or any error happens (caller
    falls back to the category average).
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        # Lazy import: anthropic SDK is optional in dev.
        import anthropic  # type: ignore
    except ImportError:
        logger.debug("market_price_estimator: anthropic SDK not installed")
        return None

    prompt = (
        "Estime en euros (nombre uniquement, pas de devise) le prix médian de "
        "vente sur Vinted / LeBonCoin pour ce vêtement de seconde main :\n"
        f"- Catégorie : {category_name or 'inconnue'}\n"
        f"- Marque : {brand or 'inconnue'}\n"
        f"- État : {condition or 'tres_bon'}\n"
        f"- Couleur : {color or 'inconnue'}\n"
        f"- Prix actuel boutique : {sale_price:.2f} €\n"
        "Réponds par un seul nombre décimal."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=64,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in msg.content:
            if getattr(block, "type", None) == "text":
                text += block.text
        text = text.strip().replace(",", ".").replace("€", "")
        # Pull the first floatish token (Claude sometimes adds a sentence)
        token = ""
        for ch in text:
            if ch.isdigit() or ch == ".":
                token += ch
            elif token:
                break
        value = float(token) if token else None
        return value if value and value > 0 else None
    except Exception as exc:
        logger.warning("market_price_estimator: Claude call failed: %s", exc)
        return None


async def get_or_refresh_estimate(
    db: AsyncSession,
    product: Product,
    *,
    force_refresh: bool = False,
) -> float | None:
    """Return the cached or freshly computed estimate for the product.

    Persists the new estimate on the product (caller is responsible for the
    surrounding transaction/commit).
    """
    if not force_refresh and _is_estimate_fresh(getattr(product, "market_price_updated_at", None)):
        return float(product.market_price_estimate) if product.market_price_estimate else None

    category_name = product.category.name if product.category else None
    estimate = await _estimate_via_claude(
        category_name=category_name,
        brand=product.brand,
        condition=getattr(product, "condition", None),
        color=getattr(product, "color", None),
        sale_price=float(product.sale_price),
    )
    if estimate is None:
        estimate = await _category_average_price(db, product.category_id)

    if estimate is not None:
        product.market_price_estimate = estimate
        product.market_price_updated_at = datetime.now(timezone.utc)

    return estimate


async def refresh_stale_estimates(db: AsyncSession, *, limit: int = 200) -> int:
    """Refresh estimates older than ``_REFRESH_INTERVAL`` (or never set).

    Returns the number of products updated. Used by the weekly Monday cron.
    """
    cutoff = datetime.now(timezone.utc) - _REFRESH_INTERVAL
    result = await db.execute(
        select(Product)
        .where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
        )
        .limit(limit)
    )
    products = result.scalars().all()
    updated = 0
    for p in products:
        ts = getattr(p, "market_price_updated_at", None)
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts is None or ts < cutoff:
            await get_or_refresh_estimate(db, p, force_refresh=True)
            updated += 1
    return updated
