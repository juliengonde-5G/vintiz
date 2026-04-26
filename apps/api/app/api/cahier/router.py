"""Cahier de Travail — daily performance notebook endpoints.

Mounted at /api/cahier. Most reads are authenticated; mutations require manager role.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker, get_current_user
from app.models.user import User
from app.services import cahier_service as svc
from app.services.weather_service import get_current_weather

router = APIRouter(prefix="/cahier", tags=["cahier"])

manager_only = RoleChecker(["manager"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MonthlyTargetIn(BaseModel):
    year: int
    month: int
    target_eur: float
    notes: str | None = None


class DailyTextIn(BaseModel):
    date: date
    message_du_jour: str | None = None
    operation_en_cours: str | None = None


class SignatureIn(BaseModel):
    date: date
    collaborateur: str | None = None
    manager: str | None = None


# ---------------------------------------------------------------------------
# GET /api/cahier/{report_date}
# ---------------------------------------------------------------------------

@router.get("/{report_date}")
async def get_cahier(
    report_date: date,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Full daily notebook payload for report_date."""
    today = date.today()
    if report_date > today:
        raise HTTPException(status_code=400, detail="Date in the future not supported")

    # Monthly target setting
    target_key = f"cahier.monthly_target.{report_date.year:04d}-{report_date.month:02d}"
    target_row = await svc.read_setting_json(db, target_key)
    monthly_target = float(target_row["target_eur"]) if target_row and target_row.get("target_eur") is not None else None

    weights_data = await svc.get_weekday_weights(db)
    weights = weights_data["weights"]

    # Daily target (snapshot for past dates)
    if monthly_target is not None:
        live_daily = svc.compute_daily_target(monthly_target, weights, report_date)
        ca_objectif_jour: float | None = await svc.get_or_freeze_daily_target(db, report_date, live_daily)
    else:
        ca_objectif_jour = None

    ca_n1, ca_n1_source = await svc.compute_ca_n1(db, report_date)
    perf = await svc.compute_performance(db, report_date)
    zoning = await svc.compute_zones_today(db, report_date)
    crm_gold = await svc.compute_crm_gold(db, report_date)
    prog_horaire = await svc.compute_progression_horaire(db, report_date)
    cible_horaire = svc.compute_progression_cible(ca_objectif_jour or 0.0)
    prog_mois = await svc.compute_monthly_progress(db, report_date)

    # Read per-day texts and signature
    msg_key = f"cahier.message_du_jour.{report_date.isoformat()}"
    op_key = f"cahier.operation.{report_date.isoformat()}"
    sig_key = f"cahier.signature.{report_date.isoformat()}"
    msg_row = await svc.read_setting_json(db, msg_key)
    op_row = await svc.read_setting_json(db, op_key)
    sig_row = await svc.read_setting_json(db, sig_key)

    # Weather — only fetch live weather for today; older dates use stored snapshot
    weather: dict | None = None
    if report_date == today:
        try:
            weather = await get_current_weather()
        except Exception:
            weather = None
    else:
        # Try history (stored by /api/admin/weather)
        history = await svc.read_setting_json(db, "weather_history")
        if isinstance(history, list):
            for snap in history:
                if snap.get("date") == report_date.isoformat():
                    weather = snap
                    break

    # Performance table augmentation
    obj = ca_objectif_jour or 0.0
    prog_vs_obj_pct = round(perf["ca"] / obj * 100, 1) if obj > 0 else None
    delta_vs_n1_pct = round((perf["ca"] - ca_n1) / ca_n1 * 100, 1) if ca_n1 > 0 else None

    return {
        "date": report_date.isoformat(),
        "is_past": report_date < today,
        "weekday": svc.WEEKDAY_LABELS_FR[report_date.weekday()],
        "header": {
            "weather": weather,
            "message_du_jour": (msg_row or {}).get("text"),
            "operation_en_cours": (op_row or {}).get("text"),
        },
        "objectifs_valeur": {
            "ca_budget_mois": monthly_target,
            "ca_objectif_jour": ca_objectif_jour,
            "ca_n1_jour": round(ca_n1, 2),
            "ca_n1_source": ca_n1_source,
            "prog_ca_cumul_mois": round(prog_mois, 2),
            "reste_a_faire_mois": round(max(0.0, (monthly_target or 0) - prog_mois), 2) if monthly_target is not None else None,
        },
        "performance": {
            "obj": ca_objectif_jour,
            "ca": perf["ca"],
            "ca_n1": round(ca_n1, 2),
            "prog_vs_obj_pct": prog_vs_obj_pct,
            "delta_vs_n1_pct": delta_vs_n1_pct,
            "tx_crm_pct": perf["tx_crm_pct"],
            "gold_pct": perf["gold_pct"],
            "tk": perf["tk"],
            "iv": perf["iv"],
            "pm": perf["pm"],
            "prod": perf["prod"],
        },
        "zoning": zoning,
        "crm_gold": crm_gold,
        "progression_horaire": prog_horaire,
        "progression_cible_horaire": cible_horaire,
        "signature": sig_row or {"collaborateur": None, "manager": None, "signed_at": None},
    }


# ---------------------------------------------------------------------------
# Monthly target
# ---------------------------------------------------------------------------

@router.get("/monthly-target/{year}/{month}")
async def get_monthly_target(
    year: int,
    month: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    key = f"cahier.monthly_target.{year:04d}-{month:02d}"
    row = await svc.read_setting_json(db, key)
    return row or {"target_eur": None, "notes": None, "year": year, "month": month}


@router.put("/monthly-target")
async def set_monthly_target(
    payload: MonthlyTargetIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(manager_only)],
):
    if payload.month < 1 or payload.month > 12:
        raise HTTPException(status_code=400, detail="Invalid month")
    key = f"cahier.monthly_target.{payload.year:04d}-{payload.month:02d}"
    await svc.write_setting_json(
        db,
        key,
        {
            "target_eur": payload.target_eur,
            "notes": payload.notes,
            "year": payload.year,
            "month": payload.month,
            "updated_at": datetime.utcnow().isoformat(),
        },
    )
    return {"status": "ok", "key": key}


# ---------------------------------------------------------------------------
# Daily texts (message + opération)
# ---------------------------------------------------------------------------

@router.put("/daily-text")
async def set_daily_text(
    payload: DailyTextIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    today = date.today()
    if payload.date < today:
        raise HTTPException(
            status_code=403,
            detail="Les dates passées sont en lecture seule.",
        )
    now = datetime.utcnow().isoformat()
    if payload.message_du_jour is not None:
        key = f"cahier.message_du_jour.{payload.date.isoformat()}"
        await svc.write_setting_json(db, key, {"text": payload.message_du_jour, "updated_at": now})
    if payload.operation_en_cours is not None:
        key = f"cahier.operation.{payload.date.isoformat()}"
        await svc.write_setting_json(db, key, {"text": payload.operation_en_cours, "updated_at": now})
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------

@router.put("/signature")
async def set_signature(
    payload: SignatureIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    today = date.today()
    # Past dates: allow only if no previous signature yet (rattrapage J+1)
    if payload.date < today:
        key = f"cahier.signature.{payload.date.isoformat()}"
        existing = await svc.read_setting_json(db, key)
        if existing and (existing.get("collaborateur") or existing.get("manager")):
            raise HTTPException(
                status_code=403,
                detail="Signature déjà enregistrée pour cette date.",
            )
    key = f"cahier.signature.{payload.date.isoformat()}"
    await svc.write_setting_json(
        db,
        key,
        {
            "collaborateur": payload.collaborateur,
            "manager": payload.manager,
            "signed_at": datetime.utcnow().isoformat(),
        },
    )
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Weekday weights
# ---------------------------------------------------------------------------

@router.get("/weekday-weights")
async def get_weekday_weights(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    recompute: int = 0,
):
    return await svc.get_weekday_weights(db, force_recompute=bool(recompute))


# ---------------------------------------------------------------------------
# L2.4 — Cahier 2 temps : prévisionnel J + archive J-1 + historique
# ---------------------------------------------------------------------------


@router.get("/{report_date}/forecast")
async def get_day_forecast(
    report_date: date,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Bandeau prévisionnel pour le jour J (CA prévu, événements, opérations).

    Combine :
    - season_coef + holiday_coef + event_coef via local_calendar
    - weekday weight (recomputed from history)
    - monthly target (cahier_service)
    - active commercial operations on the date
    """
    from app.services.local_calendar import (
        active_operations,
        events_around,
        school_holiday_for,
        traffic_coef_for,
    )

    coef = await traffic_coef_for(db, report_date)
    holidays = coef["holiday"]
    events = coef["events"]
    operations = await active_operations(db, report_date)

    # Weekday weight
    ww = await svc.get_weekday_weights(db, force_recompute=False)
    weights = ww.get("weights", [])
    weekday_idx = report_date.weekday()  # 0..6
    weekday_weight = weights[weekday_idx] if weights and weekday_idx < len(weights) else 1.0

    # Monthly target → prorata day
    target = await svc.get_monthly_target(db, report_date.year, report_date.month)
    monthly_target = float(target.get("target_eur", 0)) if target else 0
    # Approximate per-day target = monthly × weekday_weight × final_coef
    day_forecast = monthly_target / 30 * weekday_weight * coef["final_coef"] if monthly_target else 0

    return {
        "date": report_date.isoformat(),
        "season_coef": coef["season_coef"],
        "weekday_weight": weekday_weight,
        "school_holiday": holidays,
        "events": events,
        "operations": operations,
        "monthly_target": monthly_target,
        "day_forecast_revenue": round(day_forecast, 2),
        "final_coef": coef["final_coef"],
    }


class CahierArchivePayload(BaseModel):
    report_date: date
    manager_morning_note: str | None = None
    manager_evening_comment: str | None = None
    forecast_revenue: float | None = None
    actual_revenue: float | None = None


@router.put("/archive", dependencies=[Depends(manager_only)])
async def upsert_cahier_archive(
    payload: CahierArchivePayload,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Save (or update) a cahier_day_archive row.

    The morning note can be saved in advance (J-1 evening or earlier).
    The evening comment is added the next day. After J+7, the row is
    locked (locked_at) and further edits are refused.
    """
    from app.models.local_calendar import CahierDayArchive
    from sqlalchemy import select as _select

    res = await db.execute(
        _select(CahierDayArchive).where(CahierDayArchive.report_date == payload.report_date)
    )
    row = res.scalar_one_or_none()
    if row and row.locked_at:
        raise HTTPException(status_code=403, detail="Cette page est archivée et verrouillée.")

    if not row:
        row = CahierDayArchive(report_date=payload.report_date)
        db.add(row)

    if payload.manager_morning_note is not None:
        row.manager_morning_note = payload.manager_morning_note
    if payload.manager_evening_comment is not None:
        row.manager_evening_comment = payload.manager_evening_comment
    if payload.forecast_revenue is not None:
        row.forecast_revenue = payload.forecast_revenue
    if payload.actual_revenue is not None:
        row.actual_revenue = payload.actual_revenue

    # Auto-lock à J+7
    days_since = (date.today() - payload.report_date).days
    if days_since >= 7:
        row.locked_at = datetime.now()

    await db.flush()
    await db.refresh(row)
    return {
        "report_date": row.report_date.isoformat(),
        "locked": row.locked_at is not None,
        "manager_morning_note": row.manager_morning_note,
        "manager_evening_comment": row.manager_evening_comment,
    }


@router.get("/archive/history")
async def cahier_archive_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 30,
):
    """List recent archived cahier days, newest first."""
    from app.models.local_calendar import CahierDayArchive
    from sqlalchemy import select as _select

    res = await db.execute(
        _select(CahierDayArchive)
        .order_by(CahierDayArchive.report_date.desc())
        .limit(limit)
    )
    rows = res.scalars().all()
    return [
        {
            "report_date": r.report_date.isoformat(),
            "forecast_revenue": float(r.forecast_revenue or 0),
            "actual_revenue": float(r.actual_revenue or 0),
            "delta_pct": (
                round(((float(r.actual_revenue or 0) - float(r.forecast_revenue or 0))
                       / float(r.forecast_revenue or 1)) * 100, 1)
                if r.forecast_revenue
                else None
            ),
            "manager_morning_note": r.manager_morning_note,
            "manager_evening_comment": r.manager_evening_comment,
            "locked": r.locked_at is not None,
        }
        for r in rows
    ]
