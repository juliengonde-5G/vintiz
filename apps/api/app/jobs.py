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

        from app.models.pos import Transaction, TransactionType
        from app.services.customer_qualification import compute_qualification
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
            qualif_count = 0
            for cid in customer_ids:
                profile = await svc.recompute_taste_profile(cid)
                if profile is not None:
                    taste_count += 1
                # V2 — refresh the computed qualification signals (season,
                # price ceiling/sensitivity, trend affinity) in the same pass.
                if await compute_qualification(db, cid) is not None:
                    qualif_count += 1
            await db.commit()
            logger.info(
                "Embedding refresh: products=%d (recomputed=%d), tastes=%d, qualif=%d",
                product_summary["scanned"],
                product_summary["recomputed"],
                taste_count,
                qualif_count,
            )
    except Exception as exc:
        logger.exception("Embedding refresh job failed: %s", exc)


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
        logger.exception("SEO snapshot job failed: %s", exc)


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
        logger.exception("Social posts job failed: %s", exc)


async def run_monthly_capsule() -> None:
    """Régénère la capsule éditoriale du mois courant. 1er du mois 08:00 Paris."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.capsule import regenerate_capsule

        async with AsyncSession(engine) as db:
            row = await regenerate_capsule(db)
            await db.commit()
            logger.info(
                "Monthly capsule: iso_month=%s used_llm=%s trend=%d event=%d",
                row.iso_month,
                row.used_llm,
                len(row.proposal.get("trend_products") or []),
                len(row.proposal.get("event_products") or []),
            )
    except Exception as exc:
        logger.exception("Monthly capsule job failed: %s", exc)


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
        logger.exception("Window-display job failed: %s", exc)


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
        logger.exception("Return-to-sorting job failed: %s", exc)


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
        logger.exception("RGPD purge job failed: %s", exc)


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
        logger.exception("Anniversary cron failed: %s", exc)


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
        logger.exception("New-arrivals cron failed: %s", exc)


async def run_morning_restock() -> None:
    """Generate the daily morning restock checklist (8 a.m. Tue → Sat)."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.checklist import run_morning_restock as _run

        async with AsyncSession(engine) as db:
            payload = await _run(db)
            await db.commit()
            logger.info("Morning restock: %d products to display", payload.get("total", 0))
    except Exception as exc:
        logger.exception("Morning restock job failed: %s", exc)


async def run_monday_position_reco() -> None:
    """Generate the Monday repositioning checklist (after the 04:00 scoring)."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.checklist import run_monday_position_reco as _run

        async with AsyncSession(engine) as db:
            payload = await _run(db)
            await db.commit()
            logger.info("Monday position reco: %d products flagged", payload.get("total", 0))
    except Exception as exc:
        logger.exception("Monday position reco failed: %s", exc)


async def run_thursday_six_weeks_exit() -> None:
    """Sortie automatique des produits ≥ 6 semaines en rayon (jeudi 09:00)."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.checklist import run_thursday_six_weeks_exit as _run

        async with AsyncSession(engine) as db:
            payload = await _run(db)
            await db.commit()
            logger.info(
                "Thursday 6-weeks exit: %d eligible, %d transitioned",
                payload.get("total_eligible", 0),
                payload.get("transitioned", 0),
            )
    except Exception as exc:
        logger.exception("Thursday 6-weeks exit failed: %s", exc)


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
        logger.exception("RFM segmentation job failed: %s", exc)


async def run_weekly_scoring() -> None:
    """Recompute v3 trend scores for all stock+display products.

    Runs every Monday at 04:00 Paris (jour de fermeture). Refreshes:
      - category_trends (4-week sales signal)
      - category_velocity (90-day sales velocity per category)
      - market_price_estimate (Claude, batch refresh of stale entries)
      - then trend_score on every active product.
    """
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.models.product import Product, ProductStatus
        from app.services.brand_tiers import get_brand_score
        from app.services.category_trends import refresh_cache as refresh_trends
        from app.services.category_velocity import refresh_cache as refresh_velocity
        from app.services.market_price_estimator import (
            get_or_refresh_estimate,
            refresh_stale_estimates,
        )
        from app.services.scoring_config import get_scoring_config
        from app.services.scoring_service import compute_score

        async with AsyncSession(engine) as db:
            config = await get_scoring_config(db)
            category_trends = await refresh_trends(db)
            velocity_by_cat = await refresh_velocity(db)
            n_estimates = await refresh_stale_estimates(db, limit=500)

            result = await db.execute(
                select(Product).where(
                    Product.status.in_([ProductStatus.stock, ProductStatus.display])
                )
            )
            products = result.scalars().all()

            for product in products:
                trend = float(category_trends.get(str(product.category_id), 50.0))
                velocity = float(velocity_by_cat.get(str(product.category_id), 0.0))
                brand_score = await get_brand_score(db, product.brand)
                market_estimate = await get_or_refresh_estimate(db, product)
                score_data = compute_score(
                    shelf_date=product.shelf_date,
                    sale_price=float(product.sale_price),
                    market_price_estimate=market_estimate,
                    category_name=product.category.name if product.category else None,
                    category_trend=trend,
                    category_avg_velocity=velocity,
                    brand_score=brand_score,
                    condition=getattr(product, "condition", None),
                    config=config,
                )
                product.trend_score = score_data["total_score"]
            await db.commit()
            logger.info(
                "Weekly scoring complete: %d products scored, %d market prices refreshed",
                len(products),
                n_estimates,
            )
    except Exception as exc:
        logger.exception("Weekly scoring job failed: %s", exc)


async def run_daily_loyalty_expiry() -> None:
    """Expire loyalty points after 24mo of inactivity (PR1)."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.loyalty_expiry import expire_inactive_points

        async with AsyncSession(engine) as db:
            count = await expire_inactive_points(db)
            await db.commit()
            logger.info("Loyalty expiry: %d account(s) expired", count)
    except Exception as exc:
        logger.exception("Loyalty expiry job failed: %s", exc)


async def run_nightly_database_backup() -> None:
    """Full database backup at 03:00 Paris (gestionnaire de base de données).

    Skips when disabled in the manager settings. On failure the backup service
    records a 'failed' row and emails the alert recipient — this wrapper only
    guards the cron loop."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services import database_backup

        async with AsyncSession(engine) as db:
            cfg = await database_backup.get_config(db)
            await db.commit()
            if not cfg.enabled:
                logger.info("Nightly DB backup skipped (disabled in settings)")
                return
            backup = await database_backup.run_backup(db, trigger="auto")
            logger.info(
                "Nightly DB backup: status=%s file=%s", backup.status, backup.filename
            )
    except Exception as exc:
        logger.exception("Nightly DB backup job failed: %s", exc)


async def run_weekly_fashion_book() -> None:
    """Pre-generate the Fashion Book every Monday at 07:30 Paris.

    The /api/ai/trends endpoint serves the cached version directly — by
    refreshing it Monday morning before the boutique opens, the manager
    never waits for the Anthropic call when opening the IA tab.
    """
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.api.ai.router import get_fashion_trends

        async with AsyncSession(engine) as db:
            result = await get_fashion_trends(db=db, current_user=None, force_refresh=True)
            await db.commit()
            logger.info(
                "Fashion Book regenerated for week %s/%s — %d trends",
                result.get("week"),
                result.get("year"),
                len(result.get("trends") or []),
            )
    except Exception as exc:
        logger.exception("Fashion Book cron failed: %s", exc)


async def run_weekly_marketing_report() -> None:
    """Pre-generate the bicephalous marketing report every Monday at 08:30 Paris."""
    try:
        import json as _json
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.api.ai.router import _build_marketing_persona_report, _set_setting

        async with AsyncSession(engine) as db:
            result = await _build_marketing_persona_report(db)
            await _set_setting(
                db, "ai_marketing_persona_cache",
                _json.dumps(result, ensure_ascii=False),
            )
            await db.commit()
            logger.info(
                "Marketing report regenerated for week %s/%s",
                result.get("week"),
                result.get("year"),
            )
    except Exception as exc:
        logger.exception("Marketing report cron failed: %s", exc)


async def run_weekly_checklist() -> None:
    """Pre-generate the weekly checklist every Monday at 09:00 Paris."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.api.ai.router import get_weekly_checklist

        async with AsyncSession(engine) as db:
            result = await get_weekly_checklist(db=db, current_user=None, force_refresh=True)
            await db.commit()
            logger.info(
                "Weekly checklist regenerated for week %s/%s — %d items",
                result.get("week"),
                result.get("year"),
                len(result.get("checklist") or []),
            )
    except Exception as exc:
        logger.exception("Weekly checklist cron failed: %s", exc)


async def run_monthly_embeddings_cleanup() -> None:
    """Purge inactive + orphan customer taste profiles (C12).

    Runs on the 2nd of each month at 02:30 Paris (after the daily RGPD purge
    has settled). RGPD minimisation (Art. 5-1-c) : un profil de goûts
    n'a plus d'utilité pour une cliente inactive depuis 2 ans.
    """
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.embeddings_cleanup import (
            purge_inactive_taste_profiles,
            purge_orphan_taste_profiles,
        )

        async with AsyncSession(engine) as db:
            inactive = await purge_inactive_taste_profiles(db, dry_run=False)
            orphans = await purge_orphan_taste_profiles(db)
            await db.commit()
            logger.info(
                "Embeddings cleanup: %d inactive purged, %d orphans purged",
                inactive["deleted_count"],
                orphans,
            )
    except Exception as exc:
        logger.exception("Embeddings cleanup cron failed: %s", exc)


async def run_daily_trend_alerts() -> None:
    """Send trend product alerts to opt-in clients (PR2). 11:00 Paris."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.trend_alerts import run_trend_alerts

        async with AsyncSession(engine) as db:
            summary = await run_trend_alerts(db)
            await db.commit()
            logger.info("Trend alerts cron: %s", summary)
    except Exception as exc:
        logger.exception("Trend alerts cron failed: %s", exc)


async def run_retry_failed_payments() -> None:
    """Retry recoverable failed CB payments (offline groundwork). Every 5 min.

    Re-attempts each due ``FailedPayment`` as a payment-link checkout. No-op
    when SumUp is unconfigured or the queue is empty (cheap indexed query).
    """
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.failed_payment_service import FailedPaymentService

        async with AsyncSession(engine) as db:
            results = await FailedPaymentService().retry_failed_payments(db)
        if results:
            succeeded = sum(1 for r in results if r.get("status") == "SUCCESS")
            logger.info(
                "Failed-payment retry: %d processed, %d recovered",
                len(results), succeeded,
            )
    except Exception as exc:
        logger.exception("Failed-payment retry cron failed: %s", exc)


def register_all_jobs(scheduler) -> None:
    """Register all cron jobs with the given APScheduler instance."""
    from apscheduler.triggers.cron import CronTrigger

    scheduler.add_job(
        run_retry_failed_payments,
        CronTrigger(minute="*/5"),
        id="retry_failed_payments",
        replace_existing=True,
    )
    scheduler.add_job(
        run_weekly_scoring,
        CronTrigger(day_of_week="mon", hour=4, minute=0),
        id="weekly_scoring",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_rgpd_purge,
        CronTrigger(hour=3, minute=0),
        id="daily_rgpd_purge",
        replace_existing=True,
    )
    scheduler.add_job(
        run_nightly_database_backup,
        CronTrigger(hour=3, minute=0),
        id="nightly_database_backup",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_embedding_refresh,
        CronTrigger(hour=4, minute=0),
        id="daily_embedding_refresh",
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
        run_monthly_capsule,
        CronTrigger(day="1", hour=8, minute=0),
        id="monthly_capsule",
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
    # Lot 4 — checklist hebdo
    scheduler.add_job(
        run_morning_restock,
        CronTrigger(day_of_week="tue,wed,thu,fri,sat", hour=8, minute=0),
        id="morning_restock",
        replace_existing=True,
    )
    scheduler.add_job(
        run_monday_position_reco,
        CronTrigger(day_of_week="mon", hour=5, minute=0),
        id="monday_position_reco",
        replace_existing=True,
    )
    scheduler.add_job(
        run_thursday_six_weeks_exit,
        CronTrigger(day_of_week="thu", hour=9, minute=0),
        id="thursday_six_weeks_exit",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_loyalty_expiry,
        CronTrigger(hour=3, minute=30),
        id="daily_loyalty_expiry",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_trend_alerts,
        CronTrigger(hour=11, minute=0),
        id="daily_trend_alerts",
        replace_existing=True,
    )
    scheduler.add_job(
        run_monthly_embeddings_cleanup,
        CronTrigger(day="2", hour=2, minute=30),
        id="monthly_embeddings_cleanup",
        replace_existing=True,
    )
    # Weekly editorial briefs — Monday morning, before opening.
    scheduler.add_job(
        run_weekly_fashion_book,
        CronTrigger(day_of_week="mon", hour=7, minute=30),
        id="weekly_fashion_book",
        replace_existing=True,
    )
    scheduler.add_job(
        run_weekly_marketing_report,
        CronTrigger(day_of_week="mon", hour=8, minute=30),
        id="weekly_marketing_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_weekly_checklist,
        CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="weekly_checklist",
        replace_existing=True,
    )
