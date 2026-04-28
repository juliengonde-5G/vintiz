"""Cahier de Travail — daily performance notebook service.

Pure helpers used by /api/cahier endpoints. No FastAPI dependencies; takes an
AsyncSession and returns plain dicts / primitives suitable for JSON.
"""
from __future__ import annotations

import calendar
import json
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Settings
from app.models.client import Client, LoyaltyAccount, LoyaltyTransaction, LoyaltyTxType
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Product
from app.models.store import StoreZone, ZoneProduct


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WEEKDAY_LABELS_FR = [
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"
]

# Fallback weekday distribution for a French fashion boutique
# (Monday weak, Saturday peak). Normalized so Σ = 1.
DEFAULT_WEEKDAY_WEIGHTS = [0.08, 0.09, 0.12, 0.13, 0.16, 0.27, 0.15]

SHOP_OPEN_HOUR = 10
SHOP_CLOSE_HOUR = 20  # we display cumulative up to 20h


# ---------------------------------------------------------------------------
# Settings I/O helpers — generic JSON blob in app_settings
# ---------------------------------------------------------------------------

async def read_setting_json(db: AsyncSession, key: str) -> dict | None:
    result = await db.execute(select(Settings).where(Settings.key == key))
    row = result.scalar_one_or_none()
    if row is None or not row.value:
        return None
    try:
        return json.loads(row.value)
    except Exception:
        return None


async def write_setting_json(db: AsyncSession, key: str, data: dict) -> None:
    payload = json.dumps(data, default=str)
    result = await db.execute(select(Settings).where(Settings.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        db.add(Settings(key=key, value=payload))
    else:
        row.value = payload
    await db.commit()


# ---------------------------------------------------------------------------
# Weekday distribution
# ---------------------------------------------------------------------------

async def get_weekday_weights(
    db: AsyncSession, force_recompute: bool = False
) -> dict:
    """Return cached or freshly-computed weekday weights (0=Mon … 6=Sun).

    Cache is refreshed once per day. Falls back to DEFAULT_WEEKDAY_WEIGHTS
    when the boutique lacks history.
    """
    cache_key = "cahier.weekday_weights.cache"
    today_str = date.today().isoformat()

    if not force_recompute:
        cached = await read_setting_json(db, cache_key)
        if cached and cached.get("computed_at") == today_str:
            return cached

    # Compute from the last 84 days (12 weeks).
    end = date.today()
    start = end - timedelta(days=84)
    day_start = datetime.combine(start, time.min)
    day_end = datetime.combine(end, time.min)

    rows = await db.execute(
        select(Transaction.created_at, Transaction.total_ttc).where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    buckets = [0.0] * 7
    total = 0.0
    for created_at, amount in rows.all():
        wd = created_at.weekday()
        val = float(amount or 0)
        buckets[wd] += val
        total += val

    if total > 0:
        weights = [b / total for b in buckets]
        source = "historical"
        sample_weeks = 12
    else:
        weights = list(DEFAULT_WEEKDAY_WEIGHTS)
        source = "default"
        sample_weeks = 0

    payload = {
        "computed_at": today_str,
        "weights": weights,
        "sample_size_weeks": sample_weeks,
        "source": source,
        "weekdays": WEEKDAY_LABELS_FR,
    }
    await write_setting_json(db, cache_key, payload)
    return payload


def compute_daily_target(
    monthly_target: float, weights: list[float], report_date: date
) -> float:
    """Distribute a monthly target across days using weekday weights.

    Guarantees Σ(daily_targets) == monthly_target for the month.
    """
    year, month = report_date.year, report_date.month
    days_in_month = calendar.monthrange(year, month)[1]
    # Count occurrences of each weekday inside the target month
    occurrences = [0] * 7
    for day_n in range(1, days_in_month + 1):
        occurrences[date(year, month, day_n).weekday()] += 1
    total_weight = sum(weights[wd] * occurrences[wd] for wd in range(7))
    if total_weight == 0:
        return 0.0
    return monthly_target * weights[report_date.weekday()] / total_weight


# ---------------------------------------------------------------------------
# CA lookups
# ---------------------------------------------------------------------------

async def _sum_sales_on(db: AsyncSession, target_date: date) -> float:
    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date + timedelta(days=1), time.min)
    result = await db.execute(
        select(func.coalesce(func.sum(Transaction.total_ttc), 0)).where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    return float(result.scalar_one() or 0)


async def compute_ca_n1(db: AsyncSession, report_date: date) -> tuple[float, str]:
    """Return (ca, source) with a fallback chain for new shops.

    source: same_date_last_year | same_weekday_last_week | rolling_4_weeks_avg | unavailable
    """
    # 1. Same calendar date year-1
    try:
        n1 = report_date.replace(year=report_date.year - 1)
        ca_n1 = await _sum_sales_on(db, n1)
        if ca_n1 > 0:
            return (ca_n1, "same_date_last_year")
    except ValueError:
        # Feb 29 edge case
        pass

    # 2. Same weekday last week
    lw = report_date - timedelta(days=7)
    ca_lw = await _sum_sales_on(db, lw)
    if ca_lw > 0:
        return (ca_lw, "same_weekday_last_week")

    # 3. Rolling 4-week avg on the same weekday
    samples = []
    for k in range(1, 5):
        d = report_date - timedelta(days=7 * k)
        v = await _sum_sales_on(db, d)
        if v > 0:
            samples.append(v)
    if samples:
        return (sum(samples) / len(samples), "rolling_4_weeks_avg")

    return (0.0, "unavailable")


async def sum_sales_in_range(
    db: AsyncSession, start: date, end_exclusive: date
) -> float:
    """Total TTC revenue across a half-open date range."""
    day_start = datetime.combine(start, time.min)
    day_end = datetime.combine(end_exclusive, time.min)
    result = await db.execute(
        select(func.coalesce(func.sum(Transaction.total_ttc), 0)).where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    return float(result.scalar_one() or 0)


# ---------------------------------------------------------------------------
# Performance KPIs for a given day
# ---------------------------------------------------------------------------

async def compute_performance(db: AsyncSession, report_date: date) -> dict:
    """CA, tk, IV, PM, PROD, tx_crm_pct, loyalty_pct for report_date."""
    day_start = datetime.combine(report_date, time.min)
    day_end = datetime.combine(report_date + timedelta(days=1), time.min)

    # Aggregate CA + tk
    agg = await db.execute(
        select(
            func.coalesce(func.sum(Transaction.total_ttc), 0),
            func.count(Transaction.id),
        ).where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    ca_row = agg.one()
    ca = float(ca_row[0] or 0)
    tk = int(ca_row[1] or 0)

    # Units sold (Σ quantity on sale transactions of the day)
    units_agg = await db.execute(
        select(func.coalesce(func.sum(TransactionItem.quantity), 0))
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    units = int(units_agg.scalar_one() or 0)

    iv = round(units / tk, 2) if tk > 0 else 0.0
    pm = round(ca / tk, 2) if tk > 0 else 0.0

    # CRM tag rate (tickets with a client_id)
    crm_agg = await db.execute(
        select(func.count(Transaction.id)).where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
            Transaction.client_id.is_not(None),
        )
    )
    crm_cnt = int(crm_agg.scalar_one() or 0)
    tx_crm_pct = round(crm_cnt / tk * 100, 1) if tk > 0 else 0.0

    # Loyalty member tickets (any client with a LoyaltyAccount).
    loyalty_agg = await db.execute(
        select(func.count(Transaction.id))
        .join(Client, Client.id == Transaction.client_id)
        .join(LoyaltyAccount, LoyaltyAccount.client_id == Client.id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    loyalty_cnt = int(loyalty_agg.scalar_one() or 0)
    loyalty_pct = round(loyalty_cnt / tk * 100, 1) if tk > 0 else 0.0

    return {
        "ca": round(ca, 2),
        "tk": tk,
        "iv": iv,
        "pm": pm,
        "prod": round(ca, 2),  # single operator; CA/vendor-hour not tracked yet
        "tx_crm_pct": tx_crm_pct,
        "loyalty_pct": loyalty_pct,
    }


# ---------------------------------------------------------------------------
# CRM / Fidelite block
# ---------------------------------------------------------------------------

async def compute_crm_loyalty(db: AsyncSession, report_date: date) -> dict:
    day_start = datetime.combine(report_date, time.min)
    day_end = datetime.combine(report_date + timedelta(days=1), time.min)

    fiches = await db.execute(
        select(func.count(Client.id)).where(
            Client.created_at >= day_start, Client.created_at < day_end
        )
    )
    fiches_creees = int(fiches.scalar_one() or 0)

    new_subs = await db.execute(
        select(func.count(LoyaltyAccount.id)).where(
            LoyaltyAccount.created_at >= day_start,
            LoyaltyAccount.created_at < day_end,
        )
    )
    adhesions_fidelite = int(new_subs.scalar_one() or 0)

    fidelo = await db.execute(
        select(func.count(LoyaltyTransaction.id)).where(
            LoyaltyTransaction.tx_type == LoyaltyTxType.redeem,
            LoyaltyTransaction.created_at >= day_start,
            LoyaltyTransaction.created_at < day_end,
        )
    )
    tickets_fidelo = int(fidelo.scalar_one() or 0)

    return {
        "fiches_creees": fiches_creees,
        "adhesions_fidelite": adhesions_fidelite,
        "reprints": 0,  # Receipt model has no reprint timestamp — best-effort
        "tickets_fidelo": tickets_fidelo,
    }


# ---------------------------------------------------------------------------
# Zones aggregation
# ---------------------------------------------------------------------------

async def _zones_ca_for_date(
    db: AsyncSession, report_date: date
) -> dict[str, tuple[float, int]]:
    """Return {zone_id_str: (ca, units)} for sales landed on report_date."""
    day_start = datetime.combine(report_date, time.min)
    day_end = datetime.combine(report_date + timedelta(days=1), time.min)

    rows = await db.execute(
        select(
            StoreZone.id,
            func.coalesce(func.sum(TransactionItem.line_total), 0),
            func.coalesce(func.sum(TransactionItem.quantity), 0),
        )
        .select_from(StoreZone)
        .join(ZoneProduct, ZoneProduct.zone_id == StoreZone.id)
        .join(Product, Product.id == ZoneProduct.product_id)
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
        .group_by(StoreZone.id)
    )
    return {str(zid): (float(ca or 0), int(units or 0)) for zid, ca, units in rows.all()}


async def compute_zones_today(db: AsyncSession, report_date: date) -> list[dict]:
    """Per-zone CA/OBJ/Delta for the requested date."""
    weights_data = await get_weekday_weights(db)
    weights = weights_data["weights"]

    zones_result = await db.execute(select(StoreZone).order_by(StoreZone.display_order))
    zones = list(zones_result.scalars().all())

    today_map = await _zones_ca_for_date(db, report_date)
    try:
        n1_date = report_date.replace(year=report_date.year - 1)
        n1_map = await _zones_ca_for_date(db, n1_date)
    except ValueError:
        n1_map = {}

    out: list[dict] = []
    for z in zones:
        zid = str(z.id)
        ca, units = today_map.get(zid, (0.0, 0))
        ca_n1, _ = n1_map.get(zid, (0.0, 0))
        monthly = float(z.sales_target_monthly or 0)
        obj_jour = round(compute_daily_target(monthly, weights, report_date), 2) if monthly else 0.0
        delta_pct = round((ca - ca_n1) / ca_n1 * 100, 1) if ca_n1 > 0 else None
        out.append({
            "zone_id": zid,
            "zone_name": z.name,
            "color_code": z.color_code or "#008678",
            "obj_jour": obj_jour,
            "ca": round(ca, 2),
            "ca_n1": round(ca_n1, 2),
            "delta_pct": delta_pct,
            "units": units,
        })
    return out


# ---------------------------------------------------------------------------
# Hourly progression (cumulative CA through the day + target curve)
# ---------------------------------------------------------------------------

async def compute_progression_horaire(
    db: AsyncSession, report_date: date
) -> list[dict]:
    """Cumulative CA per hour across shop opening hours."""
    day_start = datetime.combine(report_date, time.min)
    day_end = datetime.combine(report_date + timedelta(days=1), time.min)

    rows = await db.execute(
        select(Transaction.created_at, Transaction.total_ttc).where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    per_hour = [0.0] * 24
    for created_at, amount in rows.all():
        per_hour[created_at.hour] += float(amount or 0)

    out: list[dict] = []
    running = 0.0
    for h in range(SHOP_OPEN_HOUR, SHOP_CLOSE_HOUR + 1):
        running += per_hour[h]
        out.append({"hour": h, "ca_cumul": round(running, 2)})
    return out


def compute_progression_cible(
    daily_target: float, weights_horaires: list[float] | None = None
) -> list[dict]:
    """Target cumulative CA per hour. Uses a fallback triangular curve
    peaking at 16h if no historical hourly weights are provided.
    """
    hours = list(range(SHOP_OPEN_HOUR, SHOP_CLOSE_HOUR + 1))
    if weights_horaires and len(weights_horaires) == len(hours):
        raw = weights_horaires
    else:
        # Triangular weights — low at open/close, peak at 16h
        peak = 16
        raw = [1.0 - abs(h - peak) / 8.0 for h in hours]
        raw = [max(0.2, w) for w in raw]
    total = sum(raw) or 1.0
    shares = [w / total for w in raw]
    out: list[dict] = []
    running = 0.0
    for h, s in zip(hours, shares):
        running += daily_target * s
        out.append({"hour": h, "ca_target": round(running, 2)})
    return out


# ---------------------------------------------------------------------------
# Monthly progress cumul
# ---------------------------------------------------------------------------

async def compute_monthly_progress(db: AsyncSession, report_date: date) -> float:
    """Total CA from month start up to and including report_date."""
    month_start = date(report_date.year, report_date.month, 1)
    end_exclusive = report_date + timedelta(days=1)
    return await sum_sales_in_range(db, month_start, end_exclusive)


# ---------------------------------------------------------------------------
# Daily target snapshot (freeze historical value)
# ---------------------------------------------------------------------------

async def get_or_freeze_daily_target(
    db: AsyncSession, report_date: date, live_target: float
) -> float:
    """For past dates, snapshot the daily target the first time it's read
    after midnight so that editing the monthly target later doesn't rewrite
    history. Today's target stays live.
    """
    if report_date >= date.today():
        return round(live_target, 2)

    snap_key = f"cahier.daily_target_snapshot.{report_date.isoformat()}"
    existing = await read_setting_json(db, snap_key)
    if existing and "target_eur" in existing:
        return float(existing["target_eur"])

    await write_setting_json(
        db,
        snap_key,
        {"target_eur": round(live_target, 2), "frozen_at": datetime.utcnow().isoformat()},
    )
    return round(live_target, 2)
