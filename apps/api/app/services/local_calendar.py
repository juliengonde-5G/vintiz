"""Local calendar service — Vernon / Giverny events + school holidays (L2.4).

Provides :
- ``school_holidays_zone_b()`` : statut vacances scolaires zone B (Vernon)
   pour une date donnée
- ``events_around(date_target, days)`` : liste des LocalEvent à ±N jours
- ``traffic_coef_for(date_target)`` : coefficient global = saison × vacances
   × événement × météo, à multiplier au prévisionnel CA mensuel × poids jour

Vacances scolaires zone B 2025-2026 (Académie de Rouen) — pré-chargées via
``preload_school_holidays_2026.py`` ou saisie manuelle si année différente.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.local_calendar import CommercialOperation, LocalEvent


logger = logging.getLogger(__name__)


# Vacances scolaires zone B 2025-2026 (à mettre à jour annuellement).
SCHOOL_HOLIDAYS_ZONE_B_2025_2026 = [
    ("Toussaint", date(2025, 10, 18), date(2025, 11, 3), 5),
    ("Noël", date(2025, 12, 20), date(2026, 1, 5), 0),
    ("Hiver", date(2026, 2, 14), date(2026, 3, 2), 0),
    ("Printemps", date(2026, 4, 18), date(2026, 5, 4), 10),
    ("Été", date(2026, 7, 4), date(2026, 9, 1), 15),
]


async def school_holiday_for(
    db: AsyncSession, date_target: date
) -> dict[str, Any] | None:
    """Return the holiday dict if date_target falls within zone B holidays."""
    # First try DB (allows manual updates beyond 2025-2026).
    res = await db.execute(
        select(LocalEvent).where(
            LocalEvent.is_school_holiday.is_(True),
            LocalEvent.date_start <= date_target,
            LocalEvent.date_end >= date_target,
        ).limit(1)
    )
    row = res.scalar_one_or_none()
    if row:
        return {
            "name": row.title,
            "boost_pct": row.expected_traffic_boost_pct,
            "from_db": True,
        }

    # Fallback to hardcoded constants
    for name, start, end, boost in SCHOOL_HOLIDAYS_ZONE_B_2025_2026:
        if start <= date_target <= end:
            return {"name": name, "boost_pct": boost, "from_db": False}
    return None


async def events_around(
    db: AsyncSession, date_target: date, window_days: int = 1
) -> list[dict]:
    """Return LocalEvent rows overlapping ±window_days around date_target."""
    res = await db.execute(
        select(LocalEvent).where(
            and_(
                LocalEvent.date_start <= date_target + timedelta(days=window_days),
                LocalEvent.date_end >= date_target - timedelta(days=window_days),
            ),
            LocalEvent.is_school_holiday.is_(False),
        ).order_by(LocalEvent.date_start)
    )
    return [
        {
            "id": str(e.id),
            "title": e.title,
            "date_start": e.date_start.isoformat(),
            "date_end": e.date_end.isoformat(),
            "location": e.location,
            "boost_pct": e.expected_traffic_boost_pct,
            "description": e.description,
        }
        for e in res.scalars().all()
    ]


async def active_operations(
    db: AsyncSession, date_target: date
) -> list[dict]:
    """Return commercial operations active on date_target."""
    res = await db.execute(
        select(CommercialOperation).where(
            CommercialOperation.status == "active",
            CommercialOperation.date_start <= date_target,
            CommercialOperation.date_end >= date_target,
        ).order_by(CommercialOperation.date_start)
    )
    return [
        {
            "id": str(op.id),
            "name": op.name,
            "op_type": op.op_type,
            "discount_pct": op.discount_pct,
            "date_end": op.date_end.isoformat(),
            "applicable_categories": op.applicable_categories,
            "visible_pos": op.visible_pos,
            "visible_site": op.visible_site,
        }
        for op in res.scalars().all()
    ]


def season_coef(date_target: date) -> float:
    """Coarse seasonal coefficient (1.0 = baseline).

    - Soldes hiver (Jan) : +5%
    - Mars-Mai : +0% (printemps neutre)
    - Juin (préparation été) : +10%
    - Juillet (soldes) : +20%
    - Août (creux mais touristes Giverny) : +5%
    - Septembre (rentrée) : +15%
    - Octobre-Novembre : +5%
    - Décembre (cadeaux) : +25%
    """
    table = {1: 1.05, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.10,
             7: 1.20, 8: 1.05, 9: 1.15, 10: 1.05, 11: 1.05, 12: 1.25}
    return table.get(date_target.month, 1.0)


async def traffic_coef_for(
    db: AsyncSession, date_target: date
) -> dict[str, Any]:
    """Compute the global traffic multiplier for a given day.

    Returns a dict with each contribution + the final coefficient.
    """
    season = season_coef(date_target)
    holiday = await school_holiday_for(db, date_target)
    holiday_coef = 1.0 + (holiday["boost_pct"] / 100.0 if holiday else 0)
    events = await events_around(db, date_target, window_days=0)
    event_coef = 1.0 + sum(e["boost_pct"] for e in events) / 100.0
    final = round(season * holiday_coef * event_coef, 3)
    return {
        "date": date_target.isoformat(),
        "season_coef": season,
        "holiday": holiday,
        "holiday_coef": holiday_coef,
        "events": events,
        "event_coef": event_coef,
        "final_coef": final,
    }
