"""Manager endpoints for immutable NF525 periodic closures."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker, get_current_user
from app.models.fiscal_closure import FiscalClosure
from app.models.user import User
from app.services.fiscal_closure import FiscalClosureService

router = APIRouter(prefix="/fiscal-closures", tags=["admin", "nf525"])
manager_only = RoleChecker(["manager"])


class FiscalClosureRequest(BaseModel):
    closure_type: str
    period_start: datetime
    period_end: datetime


@router.post("", dependencies=[Depends(manager_only)], status_code=201)
async def create_fiscal_closure(
    payload: FiscalClosureRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    closure = await FiscalClosureService(db).close_period(
        closure_type=payload.closure_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        user_id=current_user.id,
    )
    return FiscalClosureService.serialize(closure)


@router.get("", dependencies=[Depends(manager_only)])
async def list_fiscal_closures(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = (
        await db.execute(
            select(FiscalClosure).order_by(FiscalClosure.sequence_number.desc())
        )
    ).scalars().all()
    return {
        "closures": [FiscalClosureService.serialize(row) for row in rows],
        "integrity": await FiscalClosureService(db).verify_chain(),
    }


@router.get("/integrity", dependencies=[Depends(manager_only)])
async def fiscal_integrity(db: Annotated[AsyncSession, Depends(get_db)]):
    from app.services.fiscal import FiscalService

    fiscal = FiscalService(db)
    return {
        "transactions": await fiscal.verify_chain_integrity(),
        "z_reports": await fiscal.verify_z_chain_integrity(),
        "closures": await FiscalClosureService(db).verify_chain(),
    }


@router.get("/{closure_id}/archive", dependencies=[Depends(manager_only)])
async def download_fiscal_archive(
    closure_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    closure = await db.get(FiscalClosure, closure_id)
    if closure is None:
        raise HTTPException(status_code=404, detail="Clôture fiscale introuvable")
    filename = (
        f"vintiz-nf525-{closure.sequence_number:06d}-"
        f"{closure.closure_type}.json.gz"
    )
    return Response(
        content=closure.archive_content,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Archive-SHA256": closure.archive_sha256,
            "X-Closure-Hash": closure.hash,
        },
    )
