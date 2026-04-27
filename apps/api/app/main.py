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
from app.api.reservation.router import router as reservation_router

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


async def _run_daily_seo_snapshot() -> None:
    """Background job (P3-005): persist a daily SEO snapshot at 05:00 Paris.

    Same logic as POST /api/seo/snapshots/run; lives here to plug into
    APScheduler without a circular import."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.api.seo.router import _run_seo_check_and_persist

        async with AsyncSession(engine) as db:
            payload = await _run_seo_check_and_persist(db)
            await db.commit()
            logger.info("SEO snapshot: score=%s fetched_at=%s",
                        payload.get("score"), payload.get("fetched_at"))
    except Exception as exc:
        logger.error("SEO snapshot job failed: %s", exc)


async def _run_weekly_social_posts() -> None:
    """Background job (P3-004): generate 4 social posts every Monday at
    07:00 Paris (1h after the window-display cron so Sophie sees both)."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.visibility import generate_weekly_social_posts

        async with AsyncSession(engine) as db:
            rows = await generate_weekly_social_posts(db)
            await db.commit()
            logger.info(
                "Social posts: %d posts proposed (used_llm=%s)",
                len(rows),
                all(r.used_llm for r in rows) if rows else False,
            )
    except Exception as exc:
        logger.error("Social posts job failed: %s", exc)


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


async def _run_nightly_markdown_engine() -> None:
    """Background job (P3-001): apply Camille's markdown rules.

    Runs daily at 01:00 Paris time — before the return-to-sorting cron
    so an item that's been discounted then sat too long can still
    transition to returned_to_sorting on the same night."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.markdown_engine import MarkdownEngineService

        async with AsyncSession(engine) as db:
            summary = await MarkdownEngineService(db).run_batch()
            await db.commit()
            logger.info(
                "Markdown engine: scanned=%d, matched=%d, applied=%d",
                summary.scanned,
                summary.matched,
                summary.applied,
            )
    except Exception as exc:
        logger.error("Markdown engine job failed: %s", exc)


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


async def _run_daily_anniversary_emails() -> None:
    """Background job: birthday coupon + email (P4-008). Runs daily at
    09:00 Paris time."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.anniversary import run_anniversary_pass

        async with AsyncSession(engine) as db:
            summary = await run_anniversary_pass(db)
            await db.commit()
            if summary["considered"]:
                logger.info(
                    "Anniversary cron: %d considered, %d coupons, %d emails, %d failures",
                    summary["considered"],
                    summary["coupons"],
                    summary["emails_sent"],
                    summary["failures"],
                )
    except Exception as exc:
        logger.error("Anniversary cron failed: %s", exc)


async def _run_weekly_new_arrivals_emails() -> None:
    """Background job: weekly digest of new pieces (P4-009). Runs every
    Friday at 10:00 Paris time."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.new_arrivals import run_new_arrivals_pass

        async with AsyncSession(engine) as db:
            summary = await run_new_arrivals_pass(db)
            await db.commit()
            logger.info("New-arrivals cron summary: %s", summary)
    except Exception as exc:
        logger.error("New-arrivals cron failed: %s", exc)


async def _run_hourly_reservation_expiry() -> None:
    """Background job: expire reservations whose 48h window has elapsed
    (P4-005). Runs every hour so a held article goes back on the floor
    quickly after timeout."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.reservation import expire_due

        async with AsyncSession(engine) as db:
            n = await expire_due(db)
            await db.commit()
            if n:
                logger.info("Reservation expiry: flipped %d row(s)", n)
    except Exception as exc:
        logger.error("Reservation expiry job failed: %s", exc)


async def _run_monthly_rfm_segmentation() -> None:
    """Background job: recompute RFM scores for all customers and stamp
    each ``Client.rfm_segment`` (P4-007). Runs the 1st of each month at
    04:00 Paris time."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.rfm import run_segmentation

        async with AsyncSession(engine) as db:
            summary = await run_segmentation(db)
            await db.commit()
            logger.info(
                "RFM segmentation: %d computed / %d updated, segments=%s",
                summary["computed"],
                summary["updated"],
                summary["segments"],
            )
    except Exception as exc:
        logger.error("RFM segmentation job failed: %s", exc)


async def _run_monthly_scoring() -> None:
    """Background job: recompute trend scores for all active products (1st Wednesday of month)."""
    try:
        from sqlalchemy import func, select
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.models.product import Product, ProductPhoto, ProductStatus
        from app.services.brand_tiers import get_brand_score
        from app.services.category_trends import refresh_cache
        from app.services.scoring_service import compute_score

        async with AsyncSession(engine) as db:
            # Refresh the per-category trend cache once for the whole batch
            # (P2-010) so each product gets the live signal instead of 50.0.
            category_trends = await refresh_cache(db)

            # Pre-compute photo aggregates once (P2-011) to avoid N+1.
            photo_agg = await db.execute(
                select(
                    ProductPhoto.product_id,
                    func.count(ProductPhoto.id).label("n"),
                    func.avg(ProductPhoto.ai_confidence).label("avg_conf"),
                ).group_by(ProductPhoto.product_id)
            )
            photo_data = {
                row[0]: (int(row[1]), float(row[2]) if row[2] is not None else None)
                for row in photo_agg.all()
            }

            result = await db.execute(
                select(Product).where(
                    Product.status.in_([ProductStatus.stock, ProductStatus.display])
                )
            )
            products = result.scalars().all()

            # Pre-compute avg sale_price per category in one query (avoids N+1).
            avg_by_cat_result = await db.execute(
                select(
                    Product.category_id,
                    func.avg(Product.sale_price).label("avg_price"),
                ).group_by(Product.category_id)
            )
            avg_by_category: dict[str, float] = {
                str(row[0]): float(row[1]) for row in avg_by_cat_result.all()
            }

            for product in products:
                avg_price = avg_by_category.get(str(product.category_id), float(product.sale_price))
                brand_score = await get_brand_score(db, product.brand)
                photo_count, photo_avg_conf = photo_data.get(product.id, (0, None))
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
                    brand_score=brand_score,
                    photo_count=photo_count,
                    photo_avg_confidence=photo_avg_conf,
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
            _run_nightly_markdown_engine,
            CronTrigger(hour=1, minute=0),
            id="nightly_markdown_engine",
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
        scheduler.add_job(
            _run_weekly_social_posts,
            CronTrigger(day_of_week="mon", hour=7, minute=0),
            id="weekly_social_posts",
            replace_existing=True,
        )
        scheduler.add_job(
            _run_daily_seo_snapshot,
            CronTrigger(hour=5, minute=0),
            id="daily_seo_snapshot",
            replace_existing=True,
        )
        scheduler.add_job(
            _run_monthly_rfm_segmentation,
            CronTrigger(day="1", hour=4, minute=0),
            id="monthly_rfm_segmentation",
            replace_existing=True,
        )
        scheduler.add_job(
            _run_daily_anniversary_emails,
            CronTrigger(hour=9, minute=0),
            id="daily_anniversary_emails",
            replace_existing=True,
        )
        scheduler.add_job(
            _run_weekly_new_arrivals_emails,
            CronTrigger(day_of_week="fri", hour=10, minute=0),
            id="weekly_new_arrivals_emails",
            replace_existing=True,
        )
        scheduler.add_job(
            _run_hourly_reservation_expiry,
            CronTrigger(minute=15),
            id="hourly_reservation_expiry",
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
app.include_router(reservation_router, prefix="/api")

# Static files for product photo uploads (P1-008 follow-up). The folder is
# created on demand by the upload handler, but we mount it eagerly so missing
# folders don't 500 — StaticFiles raises if the directory is missing at boot.
_UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_UPLOADS_DIR), name="uploads")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
