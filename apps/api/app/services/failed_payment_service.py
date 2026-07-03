"""Service for the failed-payment retry queue (offline-mode groundwork).

Records CB checkouts that failed *recoverably* and re-attempts them later, as a
**payment-link** checkout (never a reader push — retrying rings nothing when no
customer is at the till). Used by:

- ``POST /api/pos/payments/cb/retry/{id}`` — manual retry from the caisse ;
- ``scripts/cron_retry_failed_payments.py`` / the APScheduler job — automatic
  retry of every due row.

All error text is stored redacted (``redact_sumup_error``). Rows are retained
with a terminal ``status`` (succeeded / exhausted / abandoned) for audit — never
hard-deleted.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.failed_payment import FailedPayment, FailedPaymentStatus
from app.services.sumup_service import SumUpService, redact_sumup_error

_log = logging.getLogger("vintiz")

# Cap the exponential-ish backoff so an old row still gets tried ~hourly.
_MAX_BACKOFF_MINUTES = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _backoff(attempt_count: int) -> timedelta:
    """5 min × attempt, capped at 1 h."""
    return timedelta(minutes=min(5 * max(attempt_count, 1), _MAX_BACKOFF_MINUTES))


class FailedPaymentService:
    """Create + retry failed CB payments."""

    def __init__(self, svc: SumUpService | None = None) -> None:
        # Injectable for tests; defaults to a fresh service (reads creds).
        self.svc = svc or SumUpService()

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------
    async def create_failed_payment(
        self,
        db: AsyncSession,
        *,
        amount: float,
        checkout_reference: str,
        error_detail: str | None = None,
        foreign_transaction_id: str | None = None,
        description: str | None = None,
        currency: str = "EUR",
        reader_id: str | None = None,
        cashier_id=None,
        is_recoverable: bool = True,
        max_attempts: int = 5,
    ) -> FailedPayment:
        """Persist a failed CB checkout for later retry.

        First retry is scheduled ~1 minute out (recoverable rows only); a
        non-recoverable row is stored as a dead letter (never auto-retried).
        """
        fp = FailedPayment(
            amount=amount,
            currency=currency,
            checkout_reference=checkout_reference,
            foreign_transaction_id=foreign_transaction_id,
            description=description,
            error_detail=redact_sumup_error(error_detail) if error_detail else None,
            reader_id=reader_id,
            cashier_id=cashier_id,
            is_recoverable=is_recoverable,
            max_attempts=max_attempts,
            status=FailedPaymentStatus.pending
            if is_recoverable
            else FailedPaymentStatus.abandoned,
            next_retry_at=(_now() + timedelta(minutes=1)) if is_recoverable else None,
        )
        db.add(fp)
        await db.flush()
        await db.refresh(fp)
        return fp

    # ------------------------------------------------------------------
    # Retry (single)
    # ------------------------------------------------------------------
    async def retry_one(self, db: AsyncSession, fp: FailedPayment) -> dict:
        """Attempt a single failed payment once. Mutates ``fp`` (no commit).

        Returns an outcome dict ``{failed_payment_id, status, ...}`` where
        ``status`` is SUCCESS | FAILED | EXHAUSTED | SKIPPED.
        """
        if fp.status != FailedPaymentStatus.pending or not fp.is_recoverable:
            return {
                "failed_payment_id": str(fp.id),
                "status": "SKIPPED",
                "reason": f"not retryable (status={fp.status.value})",
            }

        fp.attempt_count += 1
        fp.last_attempt_at = _now()
        try:
            result = await self.svc.create_checkout(
                amount=float(fp.amount),
                currency=fp.currency,
                description=fp.description or f"Rétentative {fp.checkout_reference}",
                reference=fp.checkout_reference,
                foreign_transaction_id=fp.foreign_transaction_id,
                prefer_link=True,  # never ring an unattended terminal
            )
        except Exception as exc:  # noqa: BLE001 — one bad row must not stop the batch
            _log.warning("retry_one create_checkout crashed for %s: %s", fp.id, exc)
            result = {"status": "FAILED", "error_detail": f"exception: {exc}"}

        if str(result.get("status", "")).upper() != "FAILED":
            fp.status = FailedPaymentStatus.succeeded
            fp.resolved_checkout_id = result.get("checkout_id")
            fp.next_retry_at = None
            return {
                "failed_payment_id": str(fp.id),
                "status": "SUCCESS",
                "checkout_id": result.get("checkout_id"),
            }

        fp.error_detail = redact_sumup_error(
            result.get("error_detail") or result.get("error_friendly") or "Échec"
        )
        if fp.attempt_count >= fp.max_attempts:
            fp.status = FailedPaymentStatus.exhausted
            fp.next_retry_at = None
            return {
                "failed_payment_id": str(fp.id),
                "status": "EXHAUSTED",
                "attempt": fp.attempt_count,
                "error": fp.error_detail,
            }

        fp.next_retry_at = _now() + _backoff(fp.attempt_count)
        return {
            "failed_payment_id": str(fp.id),
            "status": "FAILED",
            "attempt": fp.attempt_count,
            "next_retry_at": fp.next_retry_at.isoformat(),
            "error": fp.error_detail,
        }

    # ------------------------------------------------------------------
    # Retry (batch)
    # ------------------------------------------------------------------
    async def retry_failed_payments(self, db: AsyncSession) -> list[dict]:
        """Retry every due row (pending, recoverable, next_retry_at ≤ now).

        Commits at the end (owns the transaction — designed for the cron /
        scheduler). Skips entirely when SumUp isn't configured so we don't burn
        attempts on rows that can't possibly succeed yet.
        """
        if not self.svc.is_configured:
            _log.info("retry_failed_payments skipped: SumUp not configured")
            return []

        now = _now()
        rows = (
            await db.execute(
                select(FailedPayment)
                .where(
                    FailedPayment.status == FailedPaymentStatus.pending,
                    FailedPayment.is_recoverable.is_(True),
                    FailedPayment.attempt_count < FailedPayment.max_attempts,
                    or_(
                        FailedPayment.next_retry_at.is_(None),
                        FailedPayment.next_retry_at <= now,
                    ),
                )
                .order_by(FailedPayment.next_retry_at)
            )
        ).scalars().all()

        results: list[dict] = []
        for fp in rows:
            results.append(await self.retry_one(db, fp))

        # Flush the SumUp exchange diagnostics too (best-effort).
        try:
            from app.services.sumup_exchange_log import persist_sumup_exchanges

            await persist_sumup_exchanges(db, self.svc)
        except Exception:  # noqa: BLE001
            self.svc.drain_exchanges()

        await db.commit()
        return results

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------
    async def get_failed_payments(
        self,
        db: AsyncSession,
        *,
        status: FailedPaymentStatus | str | None = None,
        limit: int = 100,
    ) -> list[FailedPayment]:
        stmt = select(FailedPayment).order_by(FailedPayment.created_at.desc())
        if status is not None:
            if isinstance(status, str):
                status = FailedPaymentStatus(status)
            stmt = stmt.where(FailedPayment.status == status)
        stmt = stmt.limit(limit)
        return list((await db.execute(stmt)).scalars().all())
