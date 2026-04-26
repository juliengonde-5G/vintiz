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

setup_logging()
logger = logging.getLogger("vintiz")


async def _run_daily_embedding_refresh() -> None:
    """Background job (P1-004): refresh product embeddings + customer taste
    profiles. Runs daily at 04:00 Paris time so the recommender always
    sees the previous day's intake."""
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.models.client import Client
        from app.services.embeddings import EmbeddingService

        async with AsyncSession(engine) as db:
            svc = EmbeddingService(db)
            product_summary = await svc.recompute_all_products(only_missing=False)

            # Refresh taste profiles for clients with at least one purchase.
            from app.models.pos import Transaction, TransactionType

            customer_ids = (await db.execute(
                select(Transaction.client_id)
                .where(
                    Transaction.client_id.is_not(None),
                    Transaction.transaction_type == TransactionType.sale,
                )
                .distinct()
            )).scalars().all()
            taste_count = 0
            for cid in customer_ids:
                profile = await svc.recompute_taste_profile(cid)
                if profile is not None:
                    taste_count += 1
            await db.commit()
            logger.info(
                "Embedding refresh: products=%d (recomputed=%d), tastes=%d",
                product_summary["scanned"],
                product_summary["recomputed"],
                taste_count,
            )
    except Exception as exc:
        logger.error("Embedding refresh job failed: %s", exc)


async def _run_weekly_window_display() -> None:
    """Background job (P2-007): build Monday's window-display proposal.

    Runs every Monday at 06:00 Paris time so Sophie sees a ready-made
    suggestion when she opens the iPad."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.merchandising import MerchandisingService

        async with AsyncSession(engine) as db:
            svc = MerchandisingService(db)
            proposal = await svc.propose_weekly_window()
            await db.commit()
            logger.info(
                "Window-display proposal: iso_week=%s, n_items=%d",
                proposal.iso_week,
                len(proposal.proposal.get("items", [])),
            )
    except Exception as exc:
        logger.error("Window-display job failed: %s", exc)


async def _run_daily_return_to_sorting() -> None:
    """Background job (P3-007): return aged unsold products to the sorting
    centre. Runs daily at 02:00 Paris — before the embedding refresh so the
    recommender sees the freshly-displayed inventory."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.return_to_sorting import ReturnToSortingService

        async with AsyncSession(engine) as db:
            summary = await ReturnToSortingService(db).run()
            await db.commit()
            logger.info(
                "Return-to-sorting: scanned=%d, returned=%d",
                summary["scanned"],
                summary["returned"],
            )
    except Exception as exc:
        logger.error("Return-to-sorting job failed: %s", exc)


async def _run_daily_rgpd_purge() -> None:
    """Background job: hard-delete clients whose 30-day deletion window
    has elapsed (P1-007). Runs daily at 03:00 Paris time."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.rgpd import RgpdService

        async with AsyncSession(engine) as db:
            svc = RgpdService(db)
            summary = await svc.purge_pending_deletions()
            await db.commit()
            if summary["purged_count"]:
                logger.info(
                    "RGPD purge: hard-deleted %d clients (ids=%s)",
                    summary["purged_count"],
                    summary["purged_ids"],
                )
            else:
                logger.info("RGPD purge: nothing to delete")
    except Exception as exc:
        logger.error("RGPD purge job failed: %s", exc)


async def _run_monthly_scoring() -> None:
    """Background job: recompute trend scores for all active products (1st Wednesday of month)."""
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.models.product import Product, ProductStatus
        from app.services.category_trends import refresh_cache
        from app.services.scoring_service import compute_score

        async with AsyncSession(engine) as db:
            # Refresh the per-category trend cache once for the whole batch
            # (P2-010) so each product gets the live signal instead of 50.0.
            category_trends = await refresh_cache(db)

            result = await db.execute(
                select(Product).where(
                    Product.status.in_([ProductStatus.stock, ProductStatus.display])
                )
            )
            products = result.scalars().all()
            for product in products:
                from sqlalchemy import func
                avg_result = await db.execute(
                    select(func.avg(Product.sale_price)).where(
                        Product.category_id == product.category_id
                    )
                )
                avg_price = float(avg_result.scalar_one_or_none() or product.sale_price)
                score_data = compute_score(
                    shelf_date=product.shelf_date,
                    sale_price=float(product.sale_price),
                    category_avg_price=avg_price,
                    condition=getattr(product, "condition", "tres_bon") or "tres_bon",
                    brand=product.brand,
                    photo_url=product.photo_url,
                    category_trend=category_trends.get(
                        str(product.category_id), 50.0
                    ),
                )
                product.trend_score = score_data["total_score"]
            await db.commit()
            logger.info("Monthly scoring complete: %d products updated", len(products))
    except Exception as exc:
        logger.error("Monthly scoring job failed: %s", exc)


_RUNTIME_MIGRATIONS = [
    # Store zones — plan 2D layout columns (added 2026-04)
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS pos_x INTEGER NOT NULL DEFAULT 10",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS pos_y INTEGER NOT NULL DEFAULT 10",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS width INTEGER NOT NULL DEFAULT 20",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS height INTEGER NOT NULL DEFAULT 20",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS shape VARCHAR(20) NOT NULL DEFAULT 'rounded'",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS icon VARCHAR(50)",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS photo_url VARCHAR(500)",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS sales_target_monthly NUMERIC(10, 2)",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 0",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register SQLAlchemy event listeners that auto-populate audit_logs.
    # Idempotent — safe across hot reloads.
    register_audit_listeners()

    # Create all DB tables on startup (idempotent — safe to run on every restart)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Apply lightweight runtime migrations for columns added after initial release.
        from sqlalchemy import text
        for stmt in _RUNTIME_MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception as exc:
                logger.warning("Runtime migration skipped (%s): %s", stmt, exc)

    # Start APScheduler for monthly scoring (1st Wednesday of month at 06:00)
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = AsyncIOScheduler(timezone="Europe/Paris")
        scheduler.add_job(
            _run_monthly_scoring,
            CronTrigger(day_of_week="wed", week="1", hour=6, minute=0),
            id="monthly_scoring",
            replace_existing=True,
        )
        scheduler.add_job(
            _run_daily_rgpd_purge,
            CronTrigger(hour=3, minute=0),
            id="daily_rgpd_purge",
            replace_existing=True,
        )
        scheduler.add_job(
            _run_daily_embedding_refresh,
            CronTrigger(hour=4, minute=0),
            id="daily_embedding_refresh",
            replace_existing=True,
        )
        scheduler.add_job(
            _run_daily_return_to_sorting,
            CronTrigger(hour=2, minute=0),
            id="daily_return_to_sorting",
            replace_existing=True,
        )
        scheduler.add_job(
            _run_weekly_window_display,
            CronTrigger(day_of_week="mon", hour=6, minute=0),
            id="weekly_window_display",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Vintiz API started — tables ready, scheduler started")
        yield
        scheduler.shutdown(wait=False)
    except ImportError:
        logger.warning("APScheduler not installed — monthly scoring cron disabled")
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

# Static files for product photo uploads (P1-008 follow-up). The folder is
# created on demand by the upload handler, but we mount it eagerly so missing
# folders don't 500 — StaticFiles raises if the directory is missing at boot.
_UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_UPLOADS_DIR), name="uploads")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
