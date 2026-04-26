"""Coupon issuance + redemption helpers (P4-008 + future POS).

Generation rules:
- Codes are uppercase alphanumeric, prefix-tagged so the cashier can
  recognise the source at a glance: ``ANNIV-XXXXXX``, ``WELCOME-XXXXXX``…
- We never reuse a code; on collision we re-draw (rare given 36^6
  combinations × prefix).
- Anniversary coupons are 7-day windows from issue.

The redemption side (POS validation, atomic redeem) is intentionally
left out of this PR — we land the model + the issuance flow now and
plug it into the POS in a follow-up.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coupon import Coupon, CouponDiscountType, CouponSource


_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no I/O/0/1 — easier to read on receipts


def _gen_code(prefix: str, length: int = 6) -> str:
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(length))
    return f"{prefix}-{suffix}"


async def _draw_unique_code(
    db: AsyncSession, prefix: str, max_attempts: int = 10
) -> str:
    for _ in range(max_attempts):
        code = _gen_code(prefix)
        existing = await db.execute(
            select(func.count()).select_from(Coupon).where(Coupon.code == code)
        )
        if (existing.scalar_one() or 0) == 0:
            return code
    raise RuntimeError("Couldn't draw a unique coupon code after 10 attempts")


async def issue_anniversary_coupon(
    db: AsyncSession,
    client_id: uuid.UUID,
    *,
    percent_off: float = 10.0,
    valid_days: int = 7,
    now: datetime | None = None,
) -> Coupon:
    """Create a percent-off coupon for the client's birthday.

    Idempotent over a calendar day: if the same client already received
    an anniversary coupon today (any year), we return the existing row
    so a re-run of the cron doesn't double-issue.
    """
    now = now or datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    existing = await db.execute(
        select(Coupon).where(
            Coupon.client_id == client_id,
            Coupon.source == CouponSource.anniversary,
            Coupon.created_at >= day_start,
            Coupon.created_at < day_end,
        )
    )
    found = existing.scalars().first()
    if found is not None:
        return found

    code = await _draw_unique_code(db, "ANNIV")
    coupon = Coupon(
        code=code,
        client_id=client_id,
        discount_type=CouponDiscountType.percent,
        discount_value=percent_off,
        source=CouponSource.anniversary,
        valid_from=now,
        valid_until=now + timedelta(days=valid_days),
        is_active=True,
    )
    db.add(coupon)
    await db.flush()
    return coupon
