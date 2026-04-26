"""Reservation endpoints (P4-005).

Manager-side: list / create / cancel.
Public: lookup by client email so the customer can see her holds on
``/account/data``.

Reservation redemption from the POS sale flow is left to a follow-up
PR — for the MVP, the cashier visually checks the held reservation in
the manager UI before ringing up the sale.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker, get_current_user
from app.models.client import Client
from app.models.reservation import (
    DEFAULT_HOLD_HOURS,
    Reservation,
    ReservationStatus,
)
from app.models.user import User
from app.services.reservation import (
    ReservationDTO,
    ReservationError,
    cancel_reservation,
    create_reservation,
    list_reservations,
)


router = APIRouter(prefix="/reservations", tags=["reservations"])

manager_only = RoleChecker(["manager"])


def _serialise(dto: ReservationDTO) -> dict:
    return {
        "id": str(dto.id),
        "client_id": str(dto.client_id),
        "client_name": dto.client_name,
        "client_email": dto.client_email,
        "product_id": str(dto.product_id),
        "product_name": dto.product_name,
        "product_barcode": dto.product_barcode,
        "sale_price": dto.sale_price,
        "status": dto.status,
        "expires_at": dto.expires_at.isoformat() if dto.expires_at else None,
        "created_at": dto.created_at.isoformat() if dto.created_at else None,
        "notes": dto.notes,
    }


class CreateReservationRequest(BaseModel):
    client_id: uuid.UUID
    product_id: uuid.UUID
    hold_hours: int = Field(default=DEFAULT_HOLD_HOURS, ge=1, le=168)
    notes: str | None = Field(default=None, max_length=500)


class CancelReservationRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


_ERROR_MESSAGES = {
    "client_not_found": (404, "Cliente introuvable."),
    "product_not_found": (404, "Article introuvable."),
    "product_not_on_floor": (
        409,
        "L'article n'est pas en boutique (vendu, retiré ou retour tri).",
    ),
    "product_already_reserved": (
        409,
        "Cet article est déjà réservé. Annulez la réservation existante avant d'en créer une nouvelle.",
    ),
    "reservation_not_found": (404, "Réservation introuvable."),
    "reservation_not_active": (
        409,
        "Cette réservation n'est plus active.",
    ),
}


def _raise(exc: ReservationError) -> None:
    code = str(exc)
    status, message = _ERROR_MESSAGES.get(
        code, (400, "Action impossible sur cette réservation."),
    )
    raise HTTPException(status_code=status, detail=message)


# ---------------------------------------------------------------------------
# Manager endpoints
# ---------------------------------------------------------------------------


@router.get("", dependencies=[Depends(manager_only)])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    only_active: bool = Query(default=True),
):
    statuses = (ReservationStatus.active,) if only_active else None
    rows = await list_reservations(db, statuses=statuses, limit=200)
    return [_serialise(r) for r in rows]


@router.post("")
async def create(
    payload: CreateReservationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Manager-driven reservation. The cashier picks an article in the
    stock list and the cliente in the CRM, then validates."""
    if current_user.role.value != "manager":
        raise HTTPException(status_code=403, detail="Manager required")

    try:
        reservation = await create_reservation(
            db,
            client_id=payload.client_id,
            product_id=payload.product_id,
            manager_user_id=current_user.id,
            hold_hours=payload.hold_hours,
            notes=payload.notes,
        )
    except ReservationError as exc:
        _raise(exc)

    await db.commit()
    # Re-load with relationships for the DTO.
    rows = await list_reservations(
        db, statuses=(ReservationStatus.active,), limit=1,
        client_id=payload.client_id,
    )
    return _serialise(rows[0]) if rows else {"id": str(reservation.id)}


@router.post("/{reservation_id}/cancel", dependencies=[Depends(manager_only)])
async def cancel(
    reservation_id: uuid.UUID,
    payload: CancelReservationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        await cancel_reservation(db, reservation_id, reason=payload.reason)
    except ReservationError as exc:
        _raise(exc)
    await db.commit()
    return {"id": str(reservation_id), "cancelled": True}


# ---------------------------------------------------------------------------
# Public lookup — customer space
# ---------------------------------------------------------------------------


@router.get("/lookup")
async def public_lookup(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Return the active + recent reservations for a client identified
    by email. Same enumeration-resistant 404 message as the rest of the
    public CRM endpoints."""
    email_clean = email.strip().lower()
    if "@" not in email_clean or "." not in email_clean.split("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Adresse email invalide")

    client = (await db.execute(
        select(Client).where(Client.email == email_clean)
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    rows = await list_reservations(db, client_id=client.id, limit=20)
    return {
        "client_id": str(client.id),
        "reservations": [_serialise(r) for r in rows],
    }
