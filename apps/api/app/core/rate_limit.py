"""Rate limiter — Redis-backed with in-memory fallback.

In production with Redis available the counter is shared across all workers
and survives process restarts. When Redis is unreachable the module falls back
to the original single-process in-memory implementation automatically.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger("vintiz")

# ---------------------------------------------------------------------------
# Redis connection (lazy, module-level singleton)
# ---------------------------------------------------------------------------

_redis = None
_redis_available: bool | None = None  # None = not yet probed


async def _get_redis():
    """Return a connected Redis client, or None if Redis is unavailable."""
    global _redis, _redis_available
    if _redis_available is False:
        return None
    if _redis is not None:
        return _redis
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=0.5)
        await client.ping()
        _redis = client
        _redis_available = True
        logger.info("Rate limiter: Redis connected (%s)", settings.REDIS_URL)
        return _redis
    except Exception as exc:
        _redis_available = False
        logger.warning("Rate limiter: Redis unavailable (%s) — using in-memory fallback", exc)
        return None


# ---------------------------------------------------------------------------
# In-memory fallback (single-process only)
# ---------------------------------------------------------------------------

_buckets: dict[str, deque[float]] = defaultdict(deque)
_lock = asyncio.Lock()


async def _check_memory(key: str, max_attempts: int, window_seconds: int) -> int:
    now = time.monotonic()
    cutoff = now - window_seconds
    async with _lock:
        bucket = _buckets[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_attempts:
            retry_after = max(1, int(bucket[0] + window_seconds - now))
            _raise_429(key, len(bucket), window_seconds, retry_after)
        bucket.append(now)
        return max_attempts - len(bucket)


async def _reset_memory(key: str) -> None:
    async with _lock:
        _buckets.pop(key, None)


# ---------------------------------------------------------------------------
# Redis implementation
# ---------------------------------------------------------------------------

async def _check_redis(redis, key: str, max_attempts: int, window_seconds: int) -> int:
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    if count > max_attempts:
        ttl = await redis.ttl(key)
        retry_after = max(1, int(ttl))
        _raise_429(key, count, window_seconds, retry_after)
    return max_attempts - count


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _raise_429(key: str, attempts: int, window_seconds: int, retry_after: int) -> None:
    logger.warning(
        "Rate limit exceeded for key=%s (attempts=%d, window=%ds)",
        key, attempts, window_seconds,
    )
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            "Trop de tentatives. Réessayez dans "
            f"{retry_after} secondes."
        ),
        headers={"Retry-After": str(retry_after)},
    )


async def _check(key: str, max_attempts: int, window_seconds: int) -> int:
    redis = await _get_redis()
    if redis is not None:
        try:
            return await _check_redis(redis, key, max_attempts, window_seconds)
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Redis rate-limit error (%s) — falling back to memory", exc)
    return await _check_memory(key, max_attempts, window_seconds)


async def _reset(key: str) -> None:
    redis = await _get_redis()
    if redis is not None:
        try:
            await redis.delete(key)
            return
        except Exception:
            pass
    await _reset_memory(key)


def _client_key(request: Request, prefix: str) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )
    return f"{prefix}:{ip}"


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def login_rate_limit(request: Request) -> None:
    """FastAPI dependency: rate-limits the /auth/login endpoint per client IP."""
    key = _client_key(request, "login")
    await _check(
        key,
        max_attempts=settings.LOGIN_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )


async def reset_login_rate_limit(request: Request) -> None:
    """Reset the bucket for the current client (call on successful login)."""
    key = _client_key(request, "login")
    await _reset(key)
