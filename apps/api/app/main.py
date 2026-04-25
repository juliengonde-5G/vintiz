import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine
from app.core.logging_config import setup_logging
from app.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
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


async def _run_monthly_scoring() -> None:
    """Background job: recompute trend scores for all active products (1st Wednesday of month)."""
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.models.product import Product, ProductStatus
        from app.services.scoring_service import compute_score

        async with AsyncSession(engine) as db:
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


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
