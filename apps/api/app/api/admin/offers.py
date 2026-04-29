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
from app.models.audit import AuditLog
from app.models.offer import Offer, OfferType
from app.models.user import User


async def _log_offer_change(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    offer: Offer,
    extra: dict[str, Any] | None = None,
) -> None:
    """Persist an audit log entry for an offer mutation.

    ``action`` is one of: ``create``, ``update``, ``activate``, ``deactivate``,
    ``delete``. The ``data`` payload captures the offer state at the moment of
    the change so the timeline reads like an event log.
    """
    payload: dict[str, Any] = {
        "name": offer.name,
        "type": offer.type.value if hasattr(offer.type, "value") else str(offer.type),
        "active": bool(offer.active),
        "valid_from": offer.valid_from.isoformat() if offer.valid_from else None,
        "valid_until": offer.valid_until.isoformat() if offer.valid_until else None,
        "requires_loyalty": bool(offer.requires_loyalty),
        "priority": int(offer.priority),
        "config": offer.config or {},
    }
    if extra:
        payload.update(extra)
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity="offer",
            entity_id=offer.id,
            data=payload,
        )
    )


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
    await _log_offer_change(db, user_id=current_user.id, action="create", offer=offer)
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

    was_active = bool(row.active)
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
    # Choose a more specific action when the only meaningful change is the
    # active flag — gives a cleaner audit timeline.
    action = "update"
    if was_active != bool(payload.active):
        action = "activate" if payload.active else "deactivate"
    await db.flush()
    await _log_offer_change(db, user_id=current_user.id, action=action, offer=row)
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
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Soft delete: just mark as inactive so the engine ignores it."""
    row = (
        await db.execute(select(Offer).where(Offer.id == offer_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    row.active = False
    await db.flush()
    await _log_offer_change(db, user_id=current_user.id, action="deactivate", offer=row)
    await db.commit()
    return None


@router.get("/offers/{offer_id}/history", dependencies=[Depends(manager_only)])
async def offer_history(
    offer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=500),
):
    """Return the audit-log timeline of an offer (most recent first).

    Surfaced in /admin/operations as the "Historique" panel.
    """
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity == "offer", AuditLog.entity_id == offer_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    out: list[dict] = []
    for row in rows:
        out.append(
            {
                "id": str(row.id),
                "action": row.action,
                "user_id": str(row.user_id) if row.user_id else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "data": row.data or {},
            }
        )
    return {"offer_id": str(offer_id), "events": out}


@router.get("/offers/history", dependencies=[Depends(manager_only)])
async def all_offers_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(100, ge=1, le=500),
):
    """Return the recent timeline across all offers (admin overview)."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity == "offer")
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "events": [
            {
                "id": str(r.id),
                "offer_id": str(r.entity_id) if r.entity_id else None,
                "action": r.action,
                "user_id": str(r.user_id) if r.user_id else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "data": r.data or {},
            }
            for r in rows
        ]
    }
