"""Semantic free-text search for the Personal Shopper (PR2).

Lets the customer type things like *« je cherche un t-shirt blanc taille M »*
and surfaces matching products from the live inventory. Pipeline:

1. **Normalize** the query (lowercase + collapse whitespace + strip
   punctuation) — used both as the cache key and to feed the LLM.
2. **Cache lookup** — Redis (24 h TTL) keyed on
   ``ps_search:sha1(norm)``. Missing in dev (no Redis) → in-memory
   fallback dict with a TTL guard.
3. **Filter extraction** via Claude Haiku 4.5 — extracts ``category``,
   ``color``, ``size`` and an optional ``max_price``. The LLM is
   instructed to return strict JSON; on parse failure we fall back to
   regex heuristics.
4. **Inventory query** — products with ``status ∈ {stock, display}``
   are filtered on the extracted attributes, ranked by ``trend_score``
   then a recency tiebreaker, top 8 returned.
5. **Result caching** — only the product ids are stored so a stale
   cache that catches a sold item still surfaces the rest of the
   ranking; the consumer (router) re-loads the live products before
   responding.

This service is only callable through the gated PS endpoints, so the
caller has already passed ``loyalty_active`` + ``profiling`` consent
checks (see :func:`PersonalShopperService._enforce_gating`).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import Product, ProductStatus


logger = logging.getLogger("vintiz.ps_search")

CACHE_TTL_SECONDS = 86400  # 24 h per the PR2 plan
SEARCH_TOP_N = 8
LLM_MODEL = "claude-haiku-4-5"
LLM_MAX_TOKENS = 256


@dataclass
class SearchFilters:
    category: str | None = None
    color: str | None = None
    size: str | None = None
    max_price_cents: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "color": self.color,
            "size": self.size,
            "max_price_cents": self.max_price_cents,
        }


# ---------------------------------------------------------------------------
# Cache (Redis, with in-memory fallback for dev/test)
# ---------------------------------------------------------------------------


_redis = None
_redis_probed = False
_memory_cache: dict[str, tuple[float, list[str]]] = {}
_memory_lock = asyncio.Lock()


async def _get_redis():
    """Lazy Redis client. Returns ``None`` if Redis is unavailable."""
    global _redis, _redis_probed
    if _redis_probed and _redis is None:
        return None
    if _redis is not None:
        return _redis
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True, socket_timeout=0.5
        )
        await client.ping()
        _redis = client
        _redis_probed = True
        logger.info("PS search cache: Redis connected (%s)", settings.REDIS_URL)
        return _redis
    except Exception as exc:
        _redis_probed = True
        logger.info("PS search cache: Redis unavailable (%s) — in-memory cache only", exc)
        return None


def _normalize(query: str) -> str:
    q = (query or "").strip().lower()
    q = re.sub(r"[^\w\sàâçéèêëîïôûùüÿñæœ-]", " ", q, flags=re.UNICODE)
    q = re.sub(r"\s+", " ", q).strip()
    # Sort tokens so "t-shirt blanc" and "blanc t-shirt" hit the same key.
    tokens = sorted(q.split(" ")) if q else []
    return " ".join(tokens)


def _cache_key(norm: str) -> str:
    return "ps_search:" + hashlib.sha1(norm.encode("utf-8")).hexdigest()


async def _cache_get(key: str) -> list[str] | None:
    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            raw = await redis_client.get(key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.debug("PS search cache GET failed: %s", exc)
            return None
        return None

    async with _memory_lock:
        entry = _memory_cache.get(key)
        if entry is None:
            return None
        expires_at, ids = entry
        if expires_at < time.time():
            _memory_cache.pop(key, None)
            return None
        return ids


async def _cache_set(key: str, ids: list[str]) -> None:
    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            await redis_client.setex(key, CACHE_TTL_SECONDS, json.dumps(ids))
            return
        except Exception as exc:
            logger.debug("PS search cache SET failed: %s", exc)

    async with _memory_lock:
        _memory_cache[key] = (time.time() + CACHE_TTL_SECONDS, ids)


# ---------------------------------------------------------------------------
# Filter extraction
# ---------------------------------------------------------------------------


_REGEX_SIZES = re.compile(r"\b(?:taille\s*)?(xs|s|m|l|xl|xxl|3[0-9]|4[0-9])\b", re.IGNORECASE)
_REGEX_COLORS = {
    "noir": ["noir", "noire", "black"],
    "blanc": ["blanc", "blanche", "white"],
    "rouge": ["rouge", "red"],
    "bleu": ["bleu", "bleue", "blue"],
    "vert": ["vert", "verte", "green"],
    "jaune": ["jaune", "yellow"],
    "rose": ["rose", "pink"],
    "marron": ["marron", "brun", "brown"],
    "beige": ["beige", "écru", "ecru"],
    "gris": ["gris", "grise", "grey", "gray"],
    "violet": ["violet", "mauve", "purple"],
    "orange": ["orange"],
}
_REGEX_CATEGORIES = {
    "robe": ["robe"],
    "t-shirt": ["t-shirt", "tshirt", "tee", "tee-shirt"],
    "pull": ["pull", "pullover", "sweater"],
    "chemise": ["chemise"],
    "jean": ["jean", "jeans", "denim"],
    "pantalon": ["pantalon", "pants"],
    "jupe": ["jupe", "skirt"],
    "veste": ["veste", "blazer"],
    "manteau": ["manteau", "coat"],
    "chaussures": ["chaussures", "shoes", "baskets"],
    "sac": ["sac", "bag"],
    "accessoire": ["accessoire", "echarpe", "écharpe", "ceinture"],
}
_REGEX_PRICE = re.compile(r"\b(?:moins de|sous|<|max(?:imum)?)\s*(\d{1,4})\s*(?:€|euros?)?\b", re.IGNORECASE)


def _regex_filters(query: str) -> SearchFilters:
    f = SearchFilters()
    q = query.lower()

    m = _REGEX_SIZES.search(q)
    if m:
        f.size = m.group(1).upper() if m.group(1).isalpha() else m.group(1)

    for canonical, variants in _REGEX_COLORS.items():
        for variant in variants:
            if re.search(rf"\b{re.escape(variant)}\b", q):
                f.color = canonical
                break
        if f.color:
            break

    for canonical, variants in _REGEX_CATEGORIES.items():
        for variant in variants:
            if re.search(rf"\b{re.escape(variant)}\b", q):
                f.category = canonical
                break
        if f.category:
            break

    m = _REGEX_PRICE.search(q)
    if m:
        try:
            f.max_price_cents = int(m.group(1)) * 100
        except ValueError:
            pass

    return f


async def _llm_filters(query: str) -> SearchFilters | None:
    """Ask Claude Haiku to extract structured filters from free text.

    Returns ``None`` when the API key is missing or the call fails — the
    caller falls back to ``_regex_filters`` so the search degrades
    gracefully even without Anthropic.
    """
    if not getattr(settings, "ANTHROPIC_API_KEY", None):
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = (
            "Extrais des filtres structurés à partir de la requête de "
            "shopping suivante en français. Réponds UNIQUEMENT avec un "
            "objet JSON, sans texte autour, sans backticks. Schéma : "
            '{"category": string|null, "color": string|null, '
            '"size": string|null, "max_price_eur": number|null}. '
            'Catégorie en minuscule (robe, t-shirt, pull, chemise, jean, '
            'pantalon, jupe, veste, manteau, chaussures, sac, accessoire). '
            'Couleur en français minuscule (noir, blanc, rouge…). '
            'Taille XS/S/M/L/XL/XXL ou nombre (34, 36, 38…).\n\n'
            f"Requête : {query}"
        )
        message = await asyncio.to_thread(
            client.messages.create,
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in message.content if hasattr(block, "text")
        ).strip()
        # Strip code-fence guards if the model ignored the instruction.
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
        data = json.loads(text)
    except Exception as exc:
        logger.info("PS search LLM extract failed (%s) — fallback to regex", exc)
        return None

    f = SearchFilters()
    cat = data.get("category")
    if isinstance(cat, str) and cat.strip():
        f.category = cat.strip().lower()
    col = data.get("color")
    if isinstance(col, str) and col.strip():
        f.color = col.strip().lower()
    size = data.get("size")
    if isinstance(size, str) and size.strip():
        f.size = size.strip().upper() if size.isalpha() else size.strip()
    price = data.get("max_price_eur")
    if isinstance(price, (int, float)) and price > 0:
        f.max_price_cents = int(price * 100)
    return f


# ---------------------------------------------------------------------------
# Inventory query
# ---------------------------------------------------------------------------


async def _query_inventory(
    db: AsyncSession, filters: SearchFilters, limit: int = SEARCH_TOP_N
) -> list[Product]:
    """Apply extracted filters against the live catalogue.

    Empty filters are tolerated: the search still surfaces the top
    trending items so a vague query (« quelque chose à offrir ») yields
    something rather than 0 results.
    """
    stmt = select(Product).where(
        Product.status.in_([ProductStatus.stock, ProductStatus.display])
    )
    if filters.category:
        cat = f"%{filters.category}%"
        stmt = stmt.where(
            or_(Product.name.ilike(cat), Product.description.ilike(cat))
        )
    if filters.color:
        stmt = stmt.where(Product.color.ilike(filters.color))
    if filters.size:
        stmt = stmt.where(Product.size.ilike(filters.size))
    if filters.max_price_cents:
        stmt = stmt.where(Product.sale_price <= filters.max_price_cents / 100)

    stmt = stmt.order_by(
        desc(Product.trend_score), desc(Product.shelf_date)
    ).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def search(
    db: AsyncSession, query: str, *, top_n: int = SEARCH_TOP_N
) -> dict[str, Any]:
    """Run a semantic Personal Shopper search.

    Returns ``{items, filters, cache_hit, normalized_query}`` where
    ``items`` is a list of ``{product_id, name, price_cents, photo_url,
    zone, score}`` dicts ready for the public site.
    """
    norm = _normalize(query)
    if not norm:
        return {
            "items": [],
            "filters": SearchFilters().to_dict(),
            "cache_hit": False,
            "normalized_query": "",
        }

    cache_key = _cache_key(norm)
    cached_ids = await _cache_get(cache_key)
    if cached_ids:
        # Re-load live products so anything sold since the cache write
        # disappears from the result set. Coerce to UUID so SQLAlchemy
        # binds the IN clause correctly across PG/SQLite backends.
        import uuid as _uuid

        coerced: list = []
        for raw in cached_ids:
            try:
                coerced.append(_uuid.UUID(raw))
            except (ValueError, AttributeError):
                continue
        if not coerced:
            cached_ids = None
        else:
            rows = await db.execute(
                select(Product).where(
                    Product.id.in_(coerced),
                    Product.status.in_([ProductStatus.stock, ProductStatus.display]),
                )
            )
            products = list(rows.scalars().all())
            # Preserve the cached order.
            products.sort(key=lambda p: cached_ids.index(str(p.id)) if str(p.id) in cached_ids else 999)
            return {
                "items": [_serialize(p) for p in products[:top_n]],
                "filters": {},
                "cache_hit": True,
                "normalized_query": norm,
            }

    filters = await _llm_filters(query)
    if filters is None:
        filters = _regex_filters(query)

    products = await _query_inventory(db, filters, limit=top_n)

    ids = [str(p.id) for p in products]
    if ids:
        await _cache_set(cache_key, ids)

    return {
        "items": [_serialize(p) for p in products],
        "filters": filters.to_dict(),
        "cache_hit": False,
        "normalized_query": norm,
    }


def _serialize(product: Product) -> dict[str, Any]:
    photo_url: str | None = None
    photos = getattr(product, "photos", None) or []
    if photos:
        photo = photos[0]
        photo_url = getattr(photo, "url", None)
    return {
        "product_id": str(product.id),
        "name": product.name,
        "price_cents": int(round(float(product.sale_price) * 100)),
        "photo_url": photo_url,
        "zone": str(product.zone_id) if product.zone_id else None,
        "score": float(product.trend_score or 0.0),
        "size": product.size,
        "color": product.color,
    }
