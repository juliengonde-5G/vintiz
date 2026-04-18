import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine
from app.models import Base
from app.api.auth.router import router as auth_router
from app.api.inventory.router import router as inventory_router
from app.api.pos.router import router as pos_router
from app.api.crm.router import router as crm_router
from app.api.reporting.router import router as reporting_router
from app.api.admin.router import router as admin_router
from app.api.ai.router import router as ai_router
from app.api.seo.router import router as seo_router

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all DB tables on startup (idempotent — safe to run on every restart)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler — ensures CORS headers are present even on 500
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s\n%s", exc, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)}"},
    )

# Routers
app.include_router(auth_router, prefix="/api")
app.include_router(inventory_router, prefix="/api")
app.include_router(pos_router, prefix="/api")
app.include_router(crm_router, prefix="/api")
app.include_router(reporting_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(seo_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
