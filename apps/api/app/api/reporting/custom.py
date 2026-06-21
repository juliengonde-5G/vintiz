"""« Rapports sur-mesure » — embedded reporting API.

Three concerns:
  - ``GET /reports/custom/catalog``  : the queryable surface for the builder
    (datasets → dimensions + measures + chart types).
  - ``POST /reports/custom/query``   : the requêteur — run one widget spec and
    get aggregated ``{key,value}`` rows back (no SQL from the client).
  - ``/reports/custom/reports`` CRUD : save / load report definitions (a named
    page holding a layout of widgets).

Whitelisted by construction: every dataset/dimension/measure is declared in
``app.services.reporting_engine``; unknown keys answer 400, never 500.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.custom_report import CustomReport
from app.models.user import User
from app.services import reporting_engine

router = APIRouter(prefix="/custom", tags=["reporting"])


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class WidgetQuery(BaseModel):
    dataset: str
    measure: str
    dimension: str | None = None
    granularity: str = "month"
    date_from: datetime | None = None
    date_to: datetime | None = None
    range_days: int | None = None  # relative window; ignored if date_from set
    filters: dict[str, str] | None = None
    limit: int = 200


@router.get("/catalog")
async def get_catalog(current_user: Annotated[User, Depends(get_current_user)]):
    """Datasets, dimensions, measures, granularities and chart types."""
    return reporting_engine.catalog()


@router.get("/values")
async def get_dimension_values(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    dataset: str = Query(...),
    dimension: str = Query(...),
    limit: int = Query(200, ge=1, le=500),
):
    """Distinct values of a categorical dimension (for the filter dropdowns)."""
    try:
        return {"values": await reporting_engine.dimension_values(db, dataset, dimension, limit=limit)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/query")
async def run_widget_query(
    body: WidgetQuery,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Run one widget query and return aggregated rows."""
    date_from = _aware(body.date_from)
    date_to = _aware(body.date_to)
    if date_from is None and body.range_days:
        date_from = datetime.now(timezone.utc) - timedelta(days=max(1, body.range_days))
    try:
        return await reporting_engine.run_query(
            db,
            dataset=body.dataset,
            measure=body.measure,
            dimension=body.dimension,
            granularity=body.granularity,
            date_from=date_from,
            date_to=date_to,
            filters=body.filters,
            limit=body.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Saved report definitions
# ---------------------------------------------------------------------------


class ReportIn(BaseModel):
    name: str
    description: str | None = None
    layout: list[dict] = []


def _serialize(r: CustomReport) -> dict:
    return {
        "id": str(r.id),
        "name": r.name,
        "description": r.description,
        "layout": r.layout or [],
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("/reports")
async def list_reports(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    rows = (
        await db.execute(select(CustomReport).order_by(desc(CustomReport.updated_at)))
    ).scalars().all()
    return {"reports": [_serialize(r) for r in rows]}


@router.post("/reports", status_code=201)
async def create_report(
    body: ReportIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Le nom du rapport est requis")
    r = CustomReport(
        name=body.name.strip()[:120],
        description=body.description,
        layout=body.layout or [],
        created_by_id=current_user.id,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _serialize(r)


@router.get("/reports/{report_id}")
async def get_report(
    report_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    r = (await db.execute(select(CustomReport).where(CustomReport.id == report_id))).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    return _serialize(r)


@router.put("/reports/{report_id}")
async def update_report(
    report_id: uuid.UUID,
    body: ReportIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    r = (await db.execute(select(CustomReport).where(CustomReport.id == report_id))).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    if body.name.strip():
        r.name = body.name.strip()[:120]
    r.description = body.description
    r.layout = body.layout or []
    await db.commit()
    await db.refresh(r)
    return _serialize(r)


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    r = (await db.execute(select(CustomReport).where(CustomReport.id == report_id))).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    await db.delete(r)
    await db.commit()
    return {"deleted": True, "id": str(report_id)}
