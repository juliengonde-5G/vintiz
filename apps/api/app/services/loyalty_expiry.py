"""Daily expiry job for loyalty points (PR1 / Q6).

Points expire after 24 months without a ``LoyaltyTransaction``. Implementation:
for each ``LoyaltyAccount`` with ``points > 0`` and no tx in the last 24mo,
insert an ``adjust`` row with ``points = -account.points`` and zero the
balance. Audit trail preserved through the ledger.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import LoyaltyAccount, LoyaltyTransaction, LoyaltyTxType


logger = logging.getLogger("vintiz.loyalty_expiry")

EXPIRY_DAYS = 730


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def expire_inactive_points(db: AsyncSession) -> int:
    """Zero stale balances. Returns the number of accounts affected.

    Idempotent: an account already at 0 points is skipped (no extra
    adjust row), and an account whose latest tx is the synthetic
    ``adjust`` we just inserted will not re-trigger because ``points``
    is now 0.
    """
    cutoff = _now() - timedelta(days=EXPIRY_DAYS)

    rows = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.points > 0)
    )
    accounts = list(rows.scalars().all())
    affected = 0

    for account in accounts:
        last_tx_row = await db.execute(
            select(func.max(LoyaltyTransaction.created_at)).where(
                LoyaltyTransaction.account_id == account.id
            )
        )
        last_tx = last_tx_row.scalar_one_or_none()
        anchor = last_tx or account.created_at
        if anchor and anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if anchor and anchor > cutoff:
            continue

        balance = int(account.points or 0)
        if balance <= 0:
            continue

        db.add(
            LoyaltyTransaction(
                account_id=account.id,
                tx_type=LoyaltyTxType.adjust,
                points=-balance,
                description="Auto-expiration 24 mois sans activite",
            )
        )
        account.points = 0
        affected += 1

    if affected:
        await db.flush()
        logger.info("loyalty_expiry: %d account(s) expired", affected)
    return affected
