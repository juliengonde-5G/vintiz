"""Redis-backed cache helper with in-memory fallback.

Single source of truth for short-lived caches across the app — replaces the
ad-hoc TTL dicts and ``@functools.lru_cache`` shims that drifted across
services. Mirrors the pattern of ``app/core/rate_limit.py``: probe Redis
once, fall back to a process-local TTL dict when Redis is unreachable.

Usage
-----

    from app.core.cache import cache_get_or_set

    async def get_current_weather() -> dict:
        return await cache_get_or_set(
            key="weather:current:vernon",
            ttl=900,                      # 15 minutes
            factory=_call_openweather,    # async fn, called only on cache miss
        )

For mutation-driven invalidation:

    await cache_delete("brand_tier:LV")

Values are JSON-serialised so ``datetime`` and other non-trivial types must
be normalised by the caller (factory). The helper accepts ``dict``,
``list``, ``str``, ``int``, ``float``, ``bool``, ``None``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.config import settings


logger = logging.getLogger("vintiz")

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Redis singleton (probe once, cache the verdict)
# ---------------------------------------------------------------------------

_redis = None
_redis_available: bool | None = None  # None = not yet probed


async def _get_redis():
    global _redis, _redis_available
    if _redis_available is False:
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
        _redis_available = True
        logger.info("Cache: Redis connected (%s)", settings.REDIS_URL)
        return _redis
    except Exception as exc:
        _redis_available = False
        logger.warning("Cache: Redis unavailable (%s) — using in-memory fallback", exc)
        return None


# ---------------------------------------------------------------------------
# In-memory fallback (per-process)
# ---------------------------------------------------------------------------

_mem: dict[str, tuple[float, str]] = {}  # key -> (expires_at_monotonic, json_value)
_mem_lock = asyncio.Lock()


async def _mem_get(key: str) -> Any | None:
    async with _mem_lock:
        entry = _mem.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at < time.monotonic():
            _mem.pop(key, None)
            return None
        return json.loads(payload)


async def _mem_set(key: str, value: Any, ttl: int) -> None:
    async with _mem_lock:
        _mem[key] = (time.monotonic() + ttl, json.dumps(value))


async def _mem_delete(key: str) -> None:
    async with _mem_lock:
        _mem.pop(key, None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def cache_get(key: str) -> Any | None:
    """Read a cached value, or return ``None`` on miss."""
    redis = await _get_redis()
    if redis is not None:
        try:
            raw = await redis.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:
            logger.warning("cache_get(%s) failed, falling back to memory", key)
    return await _mem_get(key)


async def cache_set(key: str, value: Any, ttl: int) -> None:
    """Store ``value`` under ``key`` for ``ttl`` seconds.

    JSON-serialisable types only. ``ttl`` ≤ 0 is a no-op (lets callers
    disable a particular cache via config without branching).
    """
    if ttl <= 0:
        return
    redis = await _get_redis()
    payload = json.dumps(value)
    if redis is not None:
        try:
            await redis.set(key, payload, ex=ttl)
            return
        except Exception:
            logger.warning("cache_set(%s) failed, falling back to memory", key)
    await _mem_set(key, value, ttl)


async def cache_delete(key: str) -> None:
    """Invalidate one key (best effort — both Redis and memory)."""
    redis = await _get_redis()
    if redis is not None:
        try:
            await redis.delete(key)
        except Exception:
            logger.warning("cache_delete(%s) Redis failed", key)
    await _mem_delete(key)


async def cache_get_or_set(
    *,
    key: str,
    ttl: int,
    factory: Callable[[], Awaitable[T]],
) -> T:
    """Atomic-ish ``get -> on-miss-call-factory -> set`` flow.

    Two concurrent misses on the same key both call ``factory`` (no
    distributed lock here — overkill for the read-mostly paths we cache).
    The cost is one extra upstream call in a rare race window.
    """
    cached = await cache_get(key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    value = await factory()
    if value is not None:
        await cache_set(key, value, ttl)
    return value
