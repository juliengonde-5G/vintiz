"""APScheduler background jobs.

Each function is self-contained: it opens its own AsyncSession so it can be
called from the scheduler, from CLI scripts, or from admin trigger endpoints
without sharing session state with the request lifecycle.
"""

import logging

from app.core.database import engine

logger = logging.getLogger("vintiz")


async def run_daily_embedding_refresh() -> None:
    """Refresh product embeddings + customer taste profiles (P1-004).
    Runs daily at 04:00 Paris so the recommender sees the previous day's intake."""
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.models.client import Client
        from app.models.pos import Transaction, TransactionType
        from app.services.embeddings import EmbeddingService

        async with AsyncSession(engine) as db:
            svc = EmbeddingService(db)
            product_summary = await svc.recompute_all_products(only_missing=False)

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


async def run_daily_seo_snapshot() -> None:
    """Persist a daily SEO snapshot (P3-005). Runs at 05:00 Paris."""
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


async def run_weekly_social_posts() -> None:
    """Generate 4 social posts every Monday at 07:00 Paris (P3-004)."""
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


async def run_weekly_window_display() -> None:
    """Build Monday's window-display proposal (P2-007). Runs at 06:00 Paris."""
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


async def run_nightly_markdown_engine() -> None:
    """Apply markdown rules nightly at 01:00 Paris (P3-001)."""
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


async def run_daily_return_to_sorting() -> None:
    """Return aged unsold products to sorting centre at 02:00 Paris (P3-007)."""
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


async def run_daily_rgpd_purge() -> None:
    """Hard-delete clients whose 30-day deletion window has elapsed at 03:00 Paris."""
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


async def run_daily_anniversary_emails() -> None:
    """Send birthday coupon + email at 09:00 Paris (P4-008)."""
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


async def run_weekly_new_arrivals_emails() -> None:
    """Send weekly digest of new pieces every Friday at 10:00 Paris (P4-009)."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.new_arrivals import run_new_arrivals_pass

        async with AsyncSession(engine) as db:
            summary = await run_new_arrivals_pass(db)
            await db.commit()
            logger.info("New-arrivals cron summary: %s", summary)
    except Exception as exc:
        logger.error("New-arrivals cron failed: %s", exc)


async def run_monthly_rfm_segmentation() -> None:
    """Recompute RFM scores for all customers on the 1st of each month at 04:00 Paris (P4-007)."""
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


async def run_monthly_scoring() -> None:
    """Recompute trend scores for all active products (1st Wednesday of month at 06:00)."""
    try:
        from sqlalchemy import func, select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.models.product import Product, ProductPhoto, ProductStatus
        from app.services.brand_tiers import get_brand_score
        from app.services.category_trends import refresh_cache
        from app.services.scoring_service import compute_score

        async with AsyncSession(engine) as db:
            category_trends = await refresh_cache(db)

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
                    category_trend=category_trends.get(str(product.category_id), 50.0),
                    brand_score=brand_score,
                    photo_count=photo_count,
                    photo_avg_confidence=photo_avg_conf,
                )
                product.trend_score = score_data["total_score"]
            await db.commit()
            logger.info("Monthly scoring complete: %d products updated", len(products))
    except Exception as exc:
        logger.error("Monthly scoring job failed: %s", exc)


def register_all_jobs(scheduler) -> None:
    """Register all cron jobs with the given APScheduler instance."""
    from apscheduler.triggers.cron import CronTrigger

    scheduler.add_job(
        run_monthly_scoring,
        CronTrigger(day_of_week="wed", week="1", hour=6, minute=0),
        id="monthly_scoring",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_rgpd_purge,
        CronTrigger(hour=3, minute=0),
        id="daily_rgpd_purge",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_embedding_refresh,
        CronTrigger(hour=4, minute=0),
        id="daily_embedding_refresh",
        replace_existing=True,
    )
    scheduler.add_job(
        run_nightly_markdown_engine,
        CronTrigger(hour=1, minute=0),
        id="nightly_markdown_engine",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_return_to_sorting,
        CronTrigger(hour=2, minute=0),
        id="daily_return_to_sorting",
        replace_existing=True,
    )
    scheduler.add_job(
        run_weekly_window_display,
        CronTrigger(day_of_week="mon", hour=6, minute=0),
        id="weekly_window_display",
        replace_existing=True,
    )
    scheduler.add_job(
        run_weekly_social_posts,
        CronTrigger(day_of_week="mon", hour=7, minute=0),
        id="weekly_social_posts",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_seo_snapshot,
        CronTrigger(hour=5, minute=0),
        id="daily_seo_snapshot",
        replace_existing=True,
    )
    scheduler.add_job(
        run_monthly_rfm_segmentation,
        CronTrigger(day="1", hour=4, minute=0),
        id="monthly_rfm_segmentation",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_anniversary_emails,
        CronTrigger(hour=9, minute=0),
        id="daily_anniversary_emails",
        replace_existing=True,
    )
    scheduler.add_job(
        run_weekly_new_arrivals_emails,
        CronTrigger(day_of_week="fri", hour=10, minute=0),
        id="weekly_new_arrivals_emails",
        replace_existing=True,
    )
