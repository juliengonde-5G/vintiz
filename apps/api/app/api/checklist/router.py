"""Weekly checklist API (Lot 4).

GET /api/checklist/today           — tasks for today
GET /api/checklist/this-week       — tasks Mon → Sat for the current ISO week
POST /api/checklist/{id}/complete  — mark a task as done
POST /api/checklist/{id}/skip      — mark a task as skipped
POST /api/checklist/regenerate     — manually trigger one of the cron jobs
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.weekly_task import WeeklyTask, WeeklyTaskKind, WeeklyTaskStatus


router = APIRouter(prefix="/checklist", tags=["checklist"])


def _serialize(t: WeeklyTask) -> dict:
    return {
        "id": str(t.id),
        "kind": t.kind.value,
        "scheduled_for": t.scheduled_for.isoformat(),
        "status": t.status.value,
        "payload": t.payload or {},
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "completed_by_user_id": str(t.completed_by_user_id) if t.completed_by_user_id else None,
        "notes": t.notes,
    }


@router.get("/today")
async def list_today_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    today = datetime.now(timezone.utc).date()
    rows = (
        await db.execute(
            select(WeeklyTask)
            .where(WeeklyTask.scheduled_for == today)
            .order_by(WeeklyTask.kind.asc())
        )
    ).scalars().all()
    return {"date": today.isoformat(), "tasks": [_serialize(t) for t in rows]}


@router.get("/this-week")
async def list_this_week_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Tasks for the current ISO week (Mon → Sat)."""
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    saturday = monday + timedelta(days=5)
    rows = (
        await db.execute(
            select(WeeklyTask)
            .where(
                WeeklyTask.scheduled_for >= monday,
                WeeklyTask.scheduled_for <= saturday,
            )
            .order_by(WeeklyTask.scheduled_for.asc(), WeeklyTask.kind.asc())
        )
    ).scalars().all()

    grouped: dict[str, list[dict]] = {}
    for t in rows:
        key = t.scheduled_for.isoformat()
        grouped.setdefault(key, []).append(_serialize(t))

    return {
        "monday": monday.isoformat(),
        "saturday": saturday.isoformat(),
        "by_day": grouped,
    }


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = (
        await db.execute(select(WeeklyTask).where(WeeklyTask.id == task_id))
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = WeeklyTaskStatus.done
    task.completed_at = datetime.now(timezone.utc)
    task.completed_by_user_id = current_user.id
    await db.commit()
    return _serialize(task)


@router.post("/{task_id}/skip")
async def skip_task(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = (
        await db.execute(select(WeeklyTask).where(WeeklyTask.id == task_id))
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = WeeklyTaskStatus.skipped
    task.completed_at = datetime.now(timezone.utc)
    task.completed_by_user_id = current_user.id
    await db.commit()
    return _serialize(task)


@router.post("/regenerate")
async def regenerate_task(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    kind: WeeklyTaskKind = Query(...),
):
    """Manually trigger one of the cron-driven generators."""
    from app.services import checklist as svc

    if kind == WeeklyTaskKind.thursday_six_weeks_exit:
        result = await svc.run_thursday_six_weeks_exit(db)
    elif kind == WeeklyTaskKind.morning_restock:
        result = await svc.run_morning_restock(db)
    elif kind == WeeklyTaskKind.monday_scoring_update:
        result = await svc.run_monday_position_reco(db)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Generator not yet implemented for {kind.value}",
        )
    await db.commit()
    return {"kind": kind.value, "result": result}
