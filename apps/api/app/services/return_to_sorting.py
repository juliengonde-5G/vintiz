"""Automatic return-to-sorting cron (P3-007).

Once a day, scan the catalogue for items that have been on display for
longer than the configured threshold (default 90 days) and whose trend
score has decayed below the floor. Each pick is moved to
``ProductStatus.returned_to_sorting`` via ``ProductLifecycleService`` so
the audit + analytics events fire, and the run summary is logged.

Pure data layer — the resulting "bon de retour" PDF generation is a
follow-up. For now Sophie picks the items via the events_log query
``event_type = 'product.returned_to_sorting' AND occurred_at = today``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductStatus
from app.services.product_lifecycle import ProductLifecycleService


logger = logging.getLogger("vintiz.return_to_sorting")


@dataclass
class ReturnPolicy:
    """Knobs controlling which products get auto-returned.

    A product is returned to sorting when *all* of:
    - status is one of ``eligible_statuses``
    - displayed_at is older than ``min_age_days``
    - trend_score is below ``score_floor`` (or unset)
    """

    min_age_days: int = 90
    score_floor: float = 30.0
    eligible_statuses: tuple[ProductStatus, ...] = (
        ProductStatus.displayed,
        ProductStatus.display,
        ProductStatus.discounted,
        ProductStatus.deep_discounted,
    )
    reason: str = "Cycle de vente terminé — retour automatique au centre de tri"


class ReturnToSortingService:
    def __init__(
        self,
        db: AsyncSession,
        policy: ReturnPolicy | None = None,
    ) -> None:
        self.db = db
        self.policy = policy or ReturnPolicy()

    async def find_eligible(self, *, now: datetime | None = None) -> list[Product]:
        """Return the products that today's run would touch."""
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self.policy.min_age_days)

        result = await self.db.execute(
            select(Product).where(
                Product.status.in_(self.policy.eligible_statuses),
                Product.displayed_at.is_not(None),
                Product.displayed_at <= cutoff,
            )
        )
        candidates = result.scalars().all()

        # Filter by trend score: keep products whose score is below the
        # floor, or whose score has never been computed (defensive — they
        # have spent 90+ days on the floor without scoring, return them).
        return [
            p for p in candidates
            if p.trend_score is None or p.trend_score < self.policy.score_floor
        ]

    async def run(self, *, now: datetime | None = None) -> dict:
        """Execute one pass. Returns a summary suitable for cron logging."""
        eligible = await self.find_eligible(now=now)
        if not eligible:
            return {
                "scanned": 0,
                "returned": 0,
                "policy": self._policy_dict(),
            }

        lifecycle = ProductLifecycleService(self.db)
        returned_ids: list[str] = []
        skipped_ids: list[str] = []
        for product in eligible:
            try:
                await lifecycle.transition(
                    product,
                    ProductStatus.returned_to_sorting,
                    reason=self.policy.reason,
                )
                returned_ids.append(str(product.id))
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning(
                    "return_to_sorting: skip product %s (%s)", product.id, exc
                )
                skipped_ids.append(str(product.id))

        return {
            "scanned": len(eligible),
            "returned": len(returned_ids),
            "returned_ids": returned_ids,
            "skipped_ids": skipped_ids,
            "policy": self._policy_dict(),
        }

    def _policy_dict(self) -> dict:
        return {
            "min_age_days": self.policy.min_age_days,
            "score_floor": self.policy.score_floor,
            "eligible_statuses": [s.value for s in self.policy.eligible_statuses],
        }
