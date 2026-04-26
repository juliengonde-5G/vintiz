"""Coupon issuance + redemption helpers (P4-008 + future POS).

Generation rules:
- Codes are uppercase alphanumeric, prefix-tagged so the cashier can
  recognise the source at a glance: ``ANNIV-XXXXXX``, ``WELCOME-XXXXXX``…
- We never reuse a code; on collision we re-draw (rare given 36^6
  combinations × prefix).
- Anniversary coupons are 7-day windows from issue.

Redemption:
- ``validate_coupon`` is read-only — surfaces eligibility + computed
  discount for the cashier preview.
- ``redeem_coupon`` is atomic, called from the transaction-creation
  flow after the sale is signed.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coupon import Coupon, CouponDiscountType, CouponSource


_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no I/O/0/1 — easier to read on receipts


class CouponError(ValueError):
    """Domain-level rejection — surfaced as 4xx by the API layer."""


@dataclass
class CouponPreview:
    coupon_id: uuid.UUID
    code: str
    discount_type: str          # "percent" | "amount"
    discount_value: float
    discount_amount: float      # what to actually subtract from cart_total
    new_total: float
    source: str
    valid_until: datetime


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


# ---------------------------------------------------------------------------
# Validation + redemption (POS)
# ---------------------------------------------------------------------------


def _compute_discount(coupon: Coupon, cart_total: float) -> float:
    """Cap the discount at the cart total so we never go negative."""
    if coupon.discount_type == CouponDiscountType.percent:
        raw = cart_total * float(coupon.discount_value) / 100.0
    else:
        raw = float(coupon.discount_value)
    return round(min(raw, cart_total), 2)


async def _load_by_code(db: AsyncSession, code: str) -> Coupon | None:
    result = await db.execute(
        select(Coupon).where(Coupon.code == code.strip().upper())
    )
    return result.scalar_one_or_none()


async def validate_coupon(
    db: AsyncSession,
    *,
    code: str,
    cart_total: float,
    client_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> CouponPreview:
    """Read-only validation. Raises ``CouponError`` with one of:

    - ``not_found``         — code unknown
    - ``inactive``          — manually disabled by manager
    - ``redeemed``          — already used
    - ``expired``           — past ``valid_until``
    - ``not_yet_valid``     — before ``valid_from``
    - ``wrong_client``      — coupon is nominative for another client
    - ``no_client``         — nominative coupon but no client at the till
    """
    now = now or datetime.now(timezone.utc)
    coupon = await _load_by_code(db, code)
    if coupon is None:
        raise CouponError("not_found")
    if not coupon.is_active:
        raise CouponError("inactive")
    if coupon.redeemed_at is not None:
        raise CouponError("redeemed")

    valid_from = coupon.valid_from
    valid_until = coupon.valid_until
    if valid_from.tzinfo is None:
        valid_from = valid_from.replace(tzinfo=timezone.utc)
    if valid_until.tzinfo is None:
        valid_until = valid_until.replace(tzinfo=timezone.utc)

    if now < valid_from:
        raise CouponError("not_yet_valid")
    if now > valid_until:
        raise CouponError("expired")

    if coupon.client_id is not None:
        if client_id is None:
            raise CouponError("no_client")
        if coupon.client_id != client_id:
            raise CouponError("wrong_client")

    discount = _compute_discount(coupon, cart_total)
    return CouponPreview(
        coupon_id=coupon.id,
        code=coupon.code,
        discount_type=coupon.discount_type.value,
        discount_value=float(coupon.discount_value),
        discount_amount=discount,
        new_total=round(max(0.0, cart_total - discount), 2),
        source=coupon.source.value,
        valid_until=valid_until,
    )


async def redeem_coupon(
    db: AsyncSession,
    coupon_id: uuid.UUID,
    transaction_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> Coupon:
    """Mark the coupon as used and link to the sale. Atomic — must be
    called inside the same transaction as the sale insert."""
    now = now or datetime.now(timezone.utc)
    coupon = (await db.execute(
        select(Coupon).where(Coupon.id == coupon_id)
    )).scalar_one_or_none()
    if coupon is None:
        raise CouponError("not_found")
    if coupon.redeemed_at is not None:
        raise CouponError("redeemed")
    coupon.redeemed_at = now
    coupon.redeemed_transaction_id = transaction_id
    await db.flush()
    return coupon
