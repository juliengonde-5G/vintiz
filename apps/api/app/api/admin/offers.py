"""Admin CRUD for ``Offer`` rows (commercial operations platform).

Offers drive basket-level promotions evaluated by ``services/offers_engine.py``.
The manager edits them from ``/admin/operations``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker, get_current_user
from app.models.offer import Offer, OfferType
from app.models.user import User


router = APIRouter(tags=["admin"])

manager_only = RoleChecker(["manager"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class OfferRequest(BaseModel):
    name: str
    type: OfferType
    active: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    requires_loyalty: bool = False
    config: dict[str, Any] = {}
    priority: int = 100
    notes: str | None = None


def _serialize(o: Offer) -> dict:
    return {
        "id": str(o.id),
        "name": o.name,
        "type": o.type.value,
        "active": bool(o.active),
        "valid_from": o.valid_from.isoformat() if o.valid_from else None,
        "valid_until": o.valid_until.isoformat() if o.valid_until else None,
        "requires_loyalty": bool(o.requires_loyalty),
        "config": o.config or {},
        "priority": int(o.priority),
        "notes": o.notes,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/offers", dependencies=[Depends(manager_only)])
async def list_offers(
    db: Annotated[AsyncSession, Depends(get_db)],
    only_active: bool = Query(False),
):
    query = select(Offer).order_by(Offer.priority.asc(), Offer.created_at.desc())
    if only_active:
        query = query.where(Offer.active.is_(True))
    rows = (await db.execute(query)).scalars().all()
    return {"offers": [_serialize(o) for o in rows]}


@router.post(
    "/offers",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(manager_only)],
)
async def create_offer(
    payload: OfferRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    offer = Offer(
        name=payload.name,
        type=payload.type,
        active=payload.active,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        requires_loyalty=payload.requires_loyalty,
        config=payload.config,
        priority=payload.priority,
        notes=payload.notes,
        updated_by_user_id=current_user.id,
    )
    db.add(offer)
    await db.flush()
    await db.commit()
    return _serialize(offer)


@router.put(
    "/offers/{offer_id}",
    dependencies=[Depends(manager_only)],
)
async def update_offer(
    offer_id: uuid.UUID,
    payload: OfferRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    row = (
        await db.execute(select(Offer).where(Offer.id == offer_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Offer not found")

    row.name = payload.name
    row.type = payload.type
    row.active = payload.active
    row.valid_from = payload.valid_from
    row.valid_until = payload.valid_until
    row.requires_loyalty = payload.requires_loyalty
    row.config = payload.config
    row.priority = payload.priority
    row.notes = payload.notes
    row.updated_by_user_id = current_user.id
    await db.flush()
    await db.commit()
    return _serialize(row)


@router.delete(
    "/offers/{offer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(manager_only)],
)
async def delete_offer(
    offer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Soft delete: just mark as inactive so the engine ignores it."""
    row = (
        await db.execute(select(Offer).where(Offer.id == offer_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    row.active = False
    await db.flush()
    await db.commit()
    return None
