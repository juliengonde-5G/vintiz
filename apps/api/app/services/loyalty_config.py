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
# Optional time window during which the configured mode applies. Outside the
# window we revert to the default ``free`` mode (anti-promo lockout).
KEY_WINDOW_START = "loyalty_subscription_window_start"  # ISO date YYYY-MM-DD
KEY_WINDOW_END = "loyalty_subscription_window_end"      # ISO date YYYY-MM-DD


@dataclass
class LoyaltyConfig:
    mode: str = "free"
    price_cents: int = 500
    first_purchase_threshold_cents: int = 3000
    window_start: str | None = None  # ISO date YYYY-MM-DD inclusive
    window_end: str | None = None    # ISO date YYYY-MM-DD inclusive

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "price_cents": self.price_cents,
            "first_purchase_threshold_cents": self.first_purchase_threshold_cents,
            "window_start": self.window_start,
            "window_end": self.window_end,
        }

    def effective_mode(self, today: "_date | None" = None) -> str:
        """Return the active mode given the current date.

        Outside the [window_start, window_end] range, fall back to ``free``
        (default mode). When no window is set, the configured mode applies
        unconditionally.
        """
        from datetime import date as _date_

        if not self.window_start or not self.window_end:
            return self.mode
        try:
            start = _date_.fromisoformat(self.window_start)
            end = _date_.fromisoformat(self.window_end)
        except ValueError:
            return self.mode
        d = today or _date_.today()
        if start <= d <= end:
            return self.mode
        return "free"


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
        window_start=(await _get_setting(db, KEY_WINDOW_START)) or None,
        window_end=(await _get_setting(db, KEY_WINDOW_END)) or None,
    )


def _validate_iso_date(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    from datetime import date as _date_

    try:
        _date_.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Date invalide (attendu YYYY-MM-DD) : {value}") from exc
    return value


async def set_subscription_config(
    db: AsyncSession,
    *,
    mode: str,
    price_cents: int,
    first_purchase_threshold_cents: int,
    window_start: str | None = None,
    window_end: str | None = None,
) -> LoyaltyConfig:
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid loyalty subscription mode: {mode}")
    if price_cents < 0 or first_purchase_threshold_cents < 0:
        raise ValueError("Negative cents not allowed")
    start = _validate_iso_date(window_start)
    end = _validate_iso_date(window_end)
    if (start and not end) or (end and not start):
        raise ValueError("La plage temporelle doit avoir un début ET une fin")
    if start and end and start > end:
        raise ValueError("La date de début doit précéder la date de fin")

    await _set_setting(db, KEY_MODE, mode)
    await _set_setting(db, KEY_PRICE, str(price_cents))
    await _set_setting(db, KEY_THRESHOLD, str(first_purchase_threshold_cents))
    await _set_setting(db, KEY_WINDOW_START, start or "")
    await _set_setting(db, KEY_WINDOW_END, end or "")
    return LoyaltyConfig(
        mode=mode,
        price_cents=price_cents,
        first_purchase_threshold_cents=first_purchase_threshold_cents,
        window_start=start,
        window_end=end,
    )
