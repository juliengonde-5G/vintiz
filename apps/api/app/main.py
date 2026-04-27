import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import engine
from app.core.logging_config import setup_logging
from app.core.middleware import (
    AuditContextMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.services.audit import register_audit_listeners
from app.models import Base
from app.api.auth.router import router as auth_router
from app.api.inventory.router import router as inventory_router
from app.api.pos.router import router as pos_router
from app.api.crm.router import router as crm_router
from app.api.reporting.router import router as reporting_router
from app.api.admin.router import router as admin_router
from app.api.ai.router import router as ai_router
from app.api.hardware.router import router as hardware_router
from app.api.seo.router import router as seo_router
from app.api.newsletter.router import router as newsletter_router
from app.api.cahier.router import router as cahier_router
from app.api.checklist.router import router as checklist_router

setup_logging()
logger = logging.getLogger("vintiz")


from app.jobs import register_all_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_audit_listeners()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler(timezone="Europe/Paris")
        register_all_jobs(scheduler)
        scheduler.start()
        logger.info("Vintiz API started — tables ready, scheduler started")
        yield
        scheduler.shutdown(wait=False)
    except ImportError:
        logger.warning("APScheduler not installed — crons disabled")
        yield

    logger.info("Vintiz API shutting down")


app = FastAPI(
    title="Vintiz API",
    description="Boutique Management API for Vintiz",
    version="0.1.0",
    lifespan=lifespan,
)

# Middlewares are applied bottom-up: SecurityHeaders runs last (outermost),
# then RequestId, then CORS innermost so it touches the actual response.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(AuditContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


# Domain exception → HTTP translation (must be registered before the catch-all below)
from app.core.exceptions import (
    AuthenticationError, CartEmpty, InsufficientBalance, InvalidOperation,
    InvalidState, PaymentShortfall, PermissionDenied, ProductNotAvailable,
    RefundError, ResourceConflict, ResourceNotFound, VintizError,
)
from fastapi import HTTPException as _HTTPException
from fastapi.responses import JSONResponse as _JSONResponse

_DOMAIN_STATUS: dict[type, int] = {
    ResourceNotFound: 404,
    ResourceConflict: 409,
    InvalidState: 409,
    InsufficientBalance: 400,
    CartEmpty: 400,
    PaymentShortfall: 400,
    ProductNotAvailable: 400,
    RefundError: 400,
    AuthenticationError: 401,
    PermissionDenied: 403,
    InvalidOperation: 422,
}


@app.exception_handler(VintizError)
async def domain_exception_handler(request: Request, exc: VintizError):
    status_code = next(
        (v for k, v in _DOMAIN_STATUS.items() if isinstance(exc, k)), 422
    )
    return _JSONResponse(status_code=status_code, content={"detail": str(exc)})


# Global exception handler — ensures CORS headers are present even on 500.
# In production we hide the exception type/message to avoid information disclosure;
# in development we keep them for easier debugging. The full traceback is always logged.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "-")
    logger.error(
        "[%s] Unhandled exception on %s %s: %s\n%s",
        request_id,
        request.method,
        request.url.path,
        exc,
        traceback.format_exc(),
    )
    if settings.is_production:
        body = {
            "detail": "Une erreur interne est survenue.",
            "request_id": request_id,
        }
    else:
        body = {
            "detail": f"{type(exc).__name__}: {str(exc)}",
            "request_id": request_id,
        }
    return JSONResponse(status_code=500, content=body)

# Routers
app.include_router(auth_router, prefix="/api")
app.include_router(inventory_router, prefix="/api")
app.include_router(pos_router, prefix="/api")
app.include_router(crm_router, prefix="/api")
app.include_router(reporting_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(hardware_router, prefix="/api")
app.include_router(seo_router, prefix="/api")
app.include_router(newsletter_router, prefix="/api")
app.include_router(cahier_router, prefix="/api")
app.include_router(checklist_router, prefix="/api")

# Static files for product photo uploads (P1-008 follow-up). The folder is
# created on demand by the upload handler, but we mount it eagerly so missing
# folders don't 500 — StaticFiles raises if the directory is missing at boot.
_UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_UPLOADS_DIR), name="uploads")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
