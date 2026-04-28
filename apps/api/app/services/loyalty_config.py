"""Loyalty subscription configuration (PR1).

3 modes configurable from /settings (admin):

- ``free``           — adhésion gratuite (par défaut).
- ``paid``           — adhésion payante, prix en centimes (``price_cents``).
- ``first_purchase`` — offerte au 1er achat ≥ ``first_purchase_threshold_cents``.

Persisted as 3 rows in ``app_settings`` (seeded by migration 0031).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Settings


VALID_MODES = ("free", "paid", "first_purchase")

KEY_MODE = "loyalty_subscription_mode"
KEY_PRICE = "loyalty_subscription_price_cents"
KEY_THRESHOLD = "loyalty_first_purchase_threshold_cents"


@dataclass
class LoyaltyConfig:
    mode: str = "free"
    price_cents: int = 500
    first_purchase_threshold_cents: int = 3000

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "price_cents": self.price_cents,
            "first_purchase_threshold_cents": self.first_purchase_threshold_cents,
        }


async def _get_setting(db: AsyncSession, key: str) -> str | None:
    row = await db.execute(select(Settings).where(Settings.key == key))
    obj = row.scalar_one_or_none()
    return obj.value if obj else None


async def _set_setting(db: AsyncSession, key: str, value: str, description: str = "") -> None:
    row = await db.execute(select(Settings).where(Settings.key == key))
    obj = row.scalar_one_or_none()
    if obj is None:
        db.add(Settings(key=key, value=value, description=description or None))
    else:
        obj.value = value
    await db.flush()


def _to_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


async def get_subscription_config(db: AsyncSession) -> LoyaltyConfig:
    mode = await _get_setting(db, KEY_MODE) or "free"
    if mode not in VALID_MODES:
        mode = "free"
    return LoyaltyConfig(
        mode=mode,
        price_cents=_to_int(await _get_setting(db, KEY_PRICE), 500),
        first_purchase_threshold_cents=_to_int(
            await _get_setting(db, KEY_THRESHOLD), 3000
        ),
    )


async def set_subscription_config(
    db: AsyncSession,
    *,
    mode: str,
    price_cents: int,
    first_purchase_threshold_cents: int,
) -> LoyaltyConfig:
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid loyalty subscription mode: {mode}")
    if price_cents < 0 or first_purchase_threshold_cents < 0:
        raise ValueError("Negative cents not allowed")

    await _set_setting(db, KEY_MODE, mode)
    await _set_setting(db, KEY_PRICE, str(price_cents))
    await _set_setting(db, KEY_THRESHOLD, str(first_purchase_threshold_cents))
    return LoyaltyConfig(
        mode=mode,
        price_cents=price_cents,
        first_purchase_threshold_cents=first_purchase_threshold_cents,
    )
