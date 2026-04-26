"""HTTP middlewares for request tracking and security headers."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.audit_context import (
    reset_current_user_id,
    set_current_user_id,
)

logger = logging.getLogger("vintiz")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a UUID `X-Request-ID` to every request and structured access log line.

    The ID is exposed on `request.state.request_id` so handlers can include it
    in error responses.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        incoming = request.headers.get("x-request-id")
        request_id = incoming if incoming else uuid.uuid4().hex[:16]
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.exception(
                "request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers["x-request-id"] = request_id

        # Skip noisy health-check access logs but still record errors
        if request.url.path != "/api/health" or response.status_code >= 400:
            logger.info(
                "%s %s -> %d (%dms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        return response


class AuditContextMiddleware(BaseHTTPMiddleware):
    """Decode the JWT (best-effort) and stash the user id in the audit ContextVar.

    The SQLAlchemy event listeners that write AuditLog rows rely on this
    ContextVar to attribute changes. If the request is unauthenticated or
    the token is invalid, audit rows are written with user_id=NULL — that
    is intentional and matches the AuditLog schema (FK is nullable).
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        token_str: str | None = None
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            token_str = auth.split(" ", 1)[1].strip() or None

        user_id: uuid.UUID | None = None
        if token_str:
            # Lazy import to avoid pulling JWT deps at module import time.
            try:
                from app.core.security import verify_token

                payload = verify_token(token_str)
                sub = payload.get("sub")
                if sub:
                    try:
                        user_id = uuid.UUID(sub)
                    except (ValueError, TypeError):
                        user_id = None
            except Exception:
                # verify_token raises HTTPException on failure — swallow it
                # here so anonymous-friendly endpoints still work; downstream
                # auth deps will reject the request if needed.
                user_id = None

        token_handle = set_current_user_id(user_id)
        try:
            return await call_next(request)
        finally:
            reset_current_user_id(token_handle)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add basic security headers to every response."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        return response
