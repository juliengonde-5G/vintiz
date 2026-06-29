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


# ---------------------------------------------------------------------------
# Earning config (#1) — how points are earned + converted into a voucher.
# Editable from admin/operations. Defaults mirror the historical hard-coded
# constants so existing behaviour is unchanged until a manager edits them.
# ---------------------------------------------------------------------------

KEY_EURO_PER_POINT = "loyalty_euro_per_point"          # € spent to earn 1 point
KEY_VOUCHER_VALUE = "loyalty_voucher_value_cents"      # voucher value (cents)
KEY_VOUCHER_THRESHOLD = "loyalty_voucher_threshold"    # points per voucher
KEY_VOUCHER_VALID_DAYS = "loyalty_voucher_valid_days"  # voucher validity (days)
KEY_POINTS_EXPIRY_DAYS = "loyalty_points_expiry_days"  # points validity (days)

# Defaults = règles fidélité boutique : 1 € = 1 pt, 100 pts = chèque de 5 €.
DEFAULT_EURO_PER_POINT = 1
DEFAULT_VOUCHER_VALUE_CENTS = 500      # 5 €
DEFAULT_VOUCHER_THRESHOLD = 100        # 100 pts → 1 chèque cadeau
DEFAULT_VOUCHER_VALID_DAYS = 180       # 6 months
DEFAULT_POINTS_EXPIRY_DAYS = 730       # 24 months


@dataclass
class LoyaltyEarningConfig:
    euro_per_point: int = DEFAULT_EURO_PER_POINT
    voucher_value_cents: int = DEFAULT_VOUCHER_VALUE_CENTS
    voucher_threshold: int = DEFAULT_VOUCHER_THRESHOLD
    voucher_valid_days: int = DEFAULT_VOUCHER_VALID_DAYS
    points_expiry_days: int = DEFAULT_POINTS_EXPIRY_DAYS

    def to_dict(self) -> dict:
        return {
            "euro_per_point": self.euro_per_point,
            "voucher_value_cents": self.voucher_value_cents,
            "voucher_threshold": self.voucher_threshold,
            "voucher_valid_days": self.voucher_valid_days,
            "points_expiry_days": self.points_expiry_days,
        }


async def get_earning_config(db: AsyncSession) -> LoyaltyEarningConfig:
    """Read the loyalty earning config; defaults = historical constants."""
    return LoyaltyEarningConfig(
        euro_per_point=max(1, _to_int(
            await _get_setting(db, KEY_EURO_PER_POINT), DEFAULT_EURO_PER_POINT)),
        voucher_value_cents=max(0, _to_int(
            await _get_setting(db, KEY_VOUCHER_VALUE), DEFAULT_VOUCHER_VALUE_CENTS)),
        voucher_threshold=max(1, _to_int(
            await _get_setting(db, KEY_VOUCHER_THRESHOLD), DEFAULT_VOUCHER_THRESHOLD)),
        voucher_valid_days=max(1, _to_int(
            await _get_setting(db, KEY_VOUCHER_VALID_DAYS), DEFAULT_VOUCHER_VALID_DAYS)),
        points_expiry_days=max(1, _to_int(
            await _get_setting(db, KEY_POINTS_EXPIRY_DAYS), DEFAULT_POINTS_EXPIRY_DAYS)),
    )


async def set_earning_config(
    db: AsyncSession,
    *,
    euro_per_point: int,
    voucher_value_cents: int,
    voucher_threshold: int,
    voucher_valid_days: int,
    points_expiry_days: int,
) -> LoyaltyEarningConfig:
    """Persist the loyalty earning config (manager only). Validates positives."""
    if euro_per_point < 1:
        raise ValueError("euro_per_point doit être ≥ 1")
    if voucher_threshold < 1:
        raise ValueError("voucher_threshold doit être ≥ 1")
    if voucher_value_cents < 0:
        raise ValueError("voucher_value_cents doit être ≥ 0")
    if voucher_valid_days < 1 or points_expiry_days < 1:
        raise ValueError("les durées de validité doivent être ≥ 1 jour")
    await _set_setting(db, KEY_EURO_PER_POINT, str(euro_per_point))
    await _set_setting(db, KEY_VOUCHER_VALUE, str(voucher_value_cents))
    await _set_setting(db, KEY_VOUCHER_THRESHOLD, str(voucher_threshold))
    await _set_setting(db, KEY_VOUCHER_VALID_DAYS, str(voucher_valid_days))
    await _set_setting(db, KEY_POINTS_EXPIRY_DAYS, str(points_expiry_days))
    return await get_earning_config(db)


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
