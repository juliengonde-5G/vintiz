"""Lightweight in-memory rate limiter.

Designed for single-process deployments. For multi-worker production use,
replace `_buckets` with a Redis-backed counter (TODO in correction plan).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger("vintiz")

# key -> deque of attempt timestamps
_buckets: dict[str, deque[float]] = defaultdict(deque)
_lock = asyncio.Lock()


async def _check(key: str, max_attempts: int, window_seconds: int) -> int:
    """Record a hit and return remaining attempts. Raises 429 if exceeded."""
    now = time.monotonic()
    cutoff = now - window_seconds
    async with _lock:
        bucket = _buckets[key]
        # Drop expired entries
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_attempts:
            retry_after = max(1, int(bucket[0] + window_seconds - now))
            logger.warning(
                "Rate limit exceeded for key=%s (attempts=%d, window=%ds)",
                key,
                len(bucket),
                window_seconds,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Trop de tentatives. Réessayez dans "
                    f"{retry_after} secondes."
                ),
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)
        return max_attempts - len(bucket)


def _client_key(request: Request, prefix: str) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )
    return f"{prefix}:{ip}"


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
    async with _lock:
        _buckets.pop(key, None)
