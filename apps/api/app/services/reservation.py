"""48h product hold orchestration (P4-005).

Caller surface:
- ``create_reservation``: places a new active hold. Validates the
  product is on the floor and not already held. Sends a confirmation
  email through the unified gateway.
- ``cancel_reservation``: terminal cancel, rebooked product returns to
  the POS pool.
- ``redeem_reservation``: marker called from the POS sale flow when a
  cart line points at a held product (linked by ``client_id`` ==
  reservation client). Atomic on the reservation row.
- ``expire_due``: cron sweep — any reservation whose ``expires_at`` has
  elapsed flips to ``expired`` so the SKU goes back on the floor.

Invariants:
- At most one ACTIVE reservation per product at any time. Enforced by a
  partial unique index in migration 0018; the service still checks
  defensively to return a clean 409 error message.
- Product status must be on the floor (``stock``, ``display``, or
  ``displayed``). Sold/donated/etc. are rejected.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.product import Product, ProductStatus
from app.models.reservation import (
    DEFAULT_HOLD_HOURS,
    Reservation,
    ReservationStatus,
)


logger = logging.getLogger("vintiz.reservation")


_FLOOR_STATUSES = (
    ProductStatus.stock,
    ProductStatus.display,
    ProductStatus.displayed,
    ProductStatus.discounted,
    ProductStatus.deep_discounted,
)


class ReservationError(ValueError):
    """Domain-level rejection — surfaced as 4xx by the API layer."""


@dataclass
class ReservationDTO:
    """Lightweight snapshot for API responses (avoids lazy-load surprises)."""

    id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    client_email: str | None
    product_id: uuid.UUID
    product_name: str
    product_barcode: str
    sale_price: float
    status: str
    expires_at: datetime
    created_at: datetime
    notes: str | None


def _to_dto(r: Reservation) -> ReservationDTO:
    return ReservationDTO(
        id=r.id,
        client_id=r.client_id,
        client_name=f"{r.client.first_name} {r.client.last_name}".strip()
        if r.client else "?",
        client_email=r.client.email if r.client else None,
        product_id=r.product_id,
        product_name=r.product.name if r.product else "?",
        product_barcode=r.product.barcode if r.product else "?",
        sale_price=float(r.product.sale_price) if r.product else 0.0,
        status=r.status.value,
        expires_at=r.expires_at,
        created_at=r.created_at,
        notes=r.notes,
    )


async def list_active_reservation_product_ids(
    db: AsyncSession, *, now: datetime | None = None
) -> set[uuid.UUID]:
    """Return the product ids that are currently held. Cheap helper for
    the POS search to filter results."""
    now = now or datetime.now(timezone.utc)
    rows = await db.execute(
        select(Reservation.product_id).where(
            Reservation.status == ReservationStatus.active,
            Reservation.expires_at > now,
        )
    )
    return {row[0] for row in rows.all()}


async def list_reservations(
    db: AsyncSession,
    *,
    statuses: Iterable[ReservationStatus] | None = None,
    client_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[ReservationDTO]:
    stmt = select(Reservation).order_by(Reservation.created_at.desc()).limit(limit)
    if statuses:
        stmt = stmt.where(Reservation.status.in_(list(statuses)))
    if client_id:
        stmt = stmt.where(Reservation.client_id == client_id)
    rows = await db.execute(stmt)
    return [_to_dto(r) for r in rows.scalars().all()]


async def _load_active_for_product(
    db: AsyncSession, product_id: uuid.UUID
) -> Reservation | None:
    rows = await db.execute(
        select(Reservation).where(
            Reservation.product_id == product_id,
            Reservation.status == ReservationStatus.active,
        )
    )
    return rows.scalars().first()


async def create_reservation(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    product_id: uuid.UUID,
    manager_user_id: uuid.UUID | None = None,
    hold_hours: int = DEFAULT_HOLD_HOURS,
    notes: str | None = None,
    now: datetime | None = None,
) -> Reservation:
    now = now or datetime.now(timezone.utc)

    client_row = (await db.execute(
        select(Client).where(Client.id == client_id)
    )).scalar_one_or_none()
    if client_row is None:
        raise ReservationError("client_not_found")

    product_row = (await db.execute(
        select(Product).where(Product.id == product_id)
    )).scalar_one_or_none()
    if product_row is None:
        raise ReservationError("product_not_found")

    if product_row.status not in _FLOOR_STATUSES:
        raise ReservationError("product_not_on_floor")

    existing = await _load_active_for_product(db, product_id)
    if existing is not None:
        raise ReservationError("product_already_reserved")

    reservation = Reservation(
        client_id=client_id,
        product_id=product_id,
        status=ReservationStatus.active,
        expires_at=now + timedelta(hours=hold_hours),
        manager_user_id=manager_user_id,
        notes=notes,
    )
    db.add(reservation)
    await db.flush()

    # Notify the client. Failure is logged but doesn't roll back the hold —
    # Camille can still re-send manually.
    if client_row.email:
        await _send_confirmation(client_row, product_row, reservation)
    return reservation


async def cancel_reservation(
    db: AsyncSession,
    reservation_id: uuid.UUID,
    *,
    reason: str | None = None,
) -> Reservation:
    row = (await db.execute(
        select(Reservation).where(Reservation.id == reservation_id)
    )).scalar_one_or_none()
    if row is None:
        raise ReservationError("reservation_not_found")
    if row.status != ReservationStatus.active:
        raise ReservationError("reservation_not_active")
    row.status = ReservationStatus.cancelled
    if reason:
        row.notes = (row.notes + " | " if row.notes else "") + f"cancel: {reason}"
    await db.flush()
    return row


async def redeem_reservation(
    db: AsyncSession,
    reservation_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> Reservation:
    row = (await db.execute(
        select(Reservation).where(Reservation.id == reservation_id)
    )).scalar_one_or_none()
    if row is None:
        raise ReservationError("reservation_not_found")
    if row.status != ReservationStatus.active:
        raise ReservationError("reservation_not_active")
    row.status = ReservationStatus.redeemed
    row.redeemed_transaction_id = transaction_id
    await db.flush()
    return row


async def expire_due(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    """Cron sweep: flip every active+past-expiry row to ``expired``."""
    now = now or datetime.now(timezone.utc)
    rows = await db.execute(
        select(Reservation).where(
            Reservation.status == ReservationStatus.active,
            Reservation.expires_at <= now,
        )
    )
    n = 0
    for r in rows.scalars().all():
        r.status = ReservationStatus.expired
        n += 1
    if n:
        await db.flush()
    return n


async def _send_confirmation(
    client: Client, product: Product, reservation: Reservation
) -> None:
    """Best-effort email — never raises. The unified gateway falls back
    to simulation when no provider is configured."""
    try:
        from app.services.email_gateway import EmailMessage, send_email

        body = (
            f"<p>Bonjour {client.first_name},</p>"
            f"<p>Votre pièce <strong>{product.name}</strong> "
            f"({float(product.sale_price):.2f} €) est réservée pour 48h "
            f"jusqu'au {reservation.expires_at.strftime('%d/%m/%Y %Hh%M')}.</p>"
            f"<p>Passez à Vintiz Vernon pour la récupérer — "
            f"36 rue d'Albuféra, ouvert mardi au samedi.</p>"
            f"<p>Si vous changez d'avis, prévenez-nous au plus vite "
            f"pour qu'une autre cliente puisse en profiter.</p>"
        )
        send_email(EmailMessage(
            to=client.email,
            to_name=f"{client.first_name} {client.last_name}".strip() or None,
            subject=f"🔖 Vintiz — votre pièce est réservée 48h",
            html=body,
        ))
    except Exception as exc:
        logger.warning("Reservation email failed for %s: %s", client.email, exc)
