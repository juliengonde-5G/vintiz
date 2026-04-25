"""Newsletter subscription — RGPD-compliant.

Public endpoints:
- POST /api/newsletter/subscribe  (explicit consent required)
- GET  /api/newsletter/unsubscribe (1-click via signed token)

Admin endpoints (manager only):
- GET    /api/newsletter/subscribers          list + search + pagination
- GET    /api/newsletter/subscribers/export   CSV download
- DELETE /api/newsletter/subscribers/{id}     hard delete (right to erasure)
"""
from __future__ import annotations

import csv
import io
import re
import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker
from app.models.newsletter import NewsletterSubscriber
from app.models.user import User

router = APIRouter(prefix="/newsletter", tags=["newsletter"])

manager_only = RoleChecker(["manager"])

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SubscribeRequest(BaseModel):
    email: EmailStr
    consent: bool = Field(..., description="Must be true — explicit consent required (RGPD)")
    source: str | None = Field(None, max_length=50)


class SubscribeResponse(BaseModel):
    message: str
    already_subscribed: bool = False


class UnsubscribeResponse(BaseModel):
    message: str
    email: str | None = None


class SubscriberOut(BaseModel):
    id: str
    email: str
    consent_date: datetime
    consent_ip: str | None
    source: str
    is_active: bool
    unsubscribed_at: datetime | None
    created_at: datetime

    @classmethod
    def from_orm_row(cls, row: NewsletterSubscriber) -> "SubscriberOut":
        return cls(
            id=str(row.id),
            email=row.email,
            consent_date=row.consent_date,
            consent_ip=row.consent_ip,
            source=row.source,
            is_active=row.is_active,
            unsubscribed_at=row.unsubscribed_at,
            created_at=row.created_at,
        )


class SubscribersListResponse(BaseModel):
    total: int
    active: int
    unsubscribed: int
    results: list[SubscriberOut]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_ip(request: Request) -> str | None:
    """Extract client IP — respects X-Forwarded-For when behind reverse proxy (Caddy)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


CONSENT_TEXT = (
    "J'accepte de recevoir par e-mail les actualités de Vintiz (ouverture, "
    "ventes privées, nouveautés). Désinscription en un clic à tout moment."
)


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(
    payload: SubscribeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — creates or reactivates a subscriber with explicit consent."""
    if not payload.consent:
        raise HTTPException(
            status_code=400,
            detail="Le consentement explicite est obligatoire.",
        )

    email = payload.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Adresse e-mail invalide.")

    now = datetime.now(timezone.utc)
    ip = _client_ip(request)

    result = await db.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.is_active:
            return SubscribeResponse(
                message="Vous êtes déjà inscrite. Merci !",
                already_subscribed=True,
            )
        # Resubscribe — rotate token, refresh consent trail
        existing.is_active = True
        existing.unsubscribed_at = None
        existing.consent_date = now
        existing.consent_ip = ip
        existing.consent_text = CONSENT_TEXT
        existing.unsubscribe_token = secrets.token_urlsafe(32)
        await db.commit()
        return SubscribeResponse(
            message="Bienvenue de nouveau ! Votre inscription est réactivée.",
        )

    sub = NewsletterSubscriber(
        email=email,
        consent_date=now,
        consent_ip=ip,
        consent_text=CONSENT_TEXT,
        source=payload.source or "site_landing",
        unsubscribe_token=secrets.token_urlsafe(32),
        is_active=True,
    )
    db.add(sub)
    await db.commit()
    return SubscribeResponse(
        message="Merci ! Vous serez prévenue de l'ouverture.",
    )


@router.get("/unsubscribe", response_model=UnsubscribeResponse)
async def unsubscribe(
    token: str = Query(..., min_length=10, max_length=64),
    db: AsyncSession = Depends(get_db),
):
    """Public 1-click unsubscribe — no login required."""
    result = await db.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.unsubscribe_token == token)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Lien de désinscription invalide ou expiré.")

    if sub.is_active:
        sub.is_active = False
        sub.unsubscribed_at = datetime.now(timezone.utc)
        await db.commit()

    return UnsubscribeResponse(
        message="Vous êtes désinscrite. Vous ne recevrez plus d'e-mails de notre part.",
        email=sub.email,
    )


# ---------------------------------------------------------------------------
# Admin endpoints (manager only)
# ---------------------------------------------------------------------------

@router.get("/subscribers", response_model=SubscribersListResponse)
async def list_subscribers(
    current_user: Annotated[User, Depends(manager_only)],
    search: str | None = Query(None, max_length=320),
    status: str = Query("all", pattern="^(all|active|unsubscribed)$"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    base = select(NewsletterSubscriber)
    if search:
        needle = f"%{search.strip().lower()}%"
        base = base.where(NewsletterSubscriber.email.ilike(needle))
    if status == "active":
        base = base.where(NewsletterSubscriber.is_active.is_(True))
    elif status == "unsubscribed":
        base = base.where(NewsletterSubscriber.is_active.is_(False))

    total_active_res = await db.execute(
        select(func.count()).select_from(NewsletterSubscriber).where(
            NewsletterSubscriber.is_active.is_(True)
        )
    )
    total_all_res = await db.execute(select(func.count()).select_from(NewsletterSubscriber))
    active_count = total_active_res.scalar_one()
    total_count = total_all_res.scalar_one()

    rows_res = await db.execute(
        base.order_by(NewsletterSubscriber.created_at.desc()).limit(limit).offset(offset)
    )
    rows = rows_res.scalars().all()

    return SubscribersListResponse(
        total=total_count,
        active=active_count,
        unsubscribed=total_count - active_count,
        results=[SubscriberOut.from_orm_row(r) for r in rows],
    )


@router.get("/subscribers/export")
async def export_subscribers(
    current_user: Annotated[User, Depends(manager_only)],
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """CSV export — audit-ready (consent trail included)."""
    stmt = select(NewsletterSubscriber)
    if active_only:
        stmt = stmt.where(NewsletterSubscriber.is_active.is_(True))
    stmt = stmt.order_by(NewsletterSubscriber.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([
        "email", "consent_date", "consent_ip", "source",
        "is_active", "unsubscribed_at", "created_at",
    ])
    for r in rows:
        writer.writerow([
            r.email,
            r.consent_date.isoformat() if r.consent_date else "",
            r.consent_ip or "",
            r.source,
            "1" if r.is_active else "0",
            r.unsubscribed_at.isoformat() if r.unsubscribed_at else "",
            r.created_at.isoformat() if r.created_at else "",
        ])
    buf.seek(0)
    filename = f"vintiz-newsletter-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/subscribers/{subscriber_id}", status_code=204)
async def delete_subscriber(
    subscriber_id: str,
    current_user: Annotated[User, Depends(manager_only)],
    db: AsyncSession = Depends(get_db),
):
    """Right to erasure (RGPD art. 17) — hard delete."""
    result = await db.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.id == subscriber_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Abonnée introuvable.")
    await db.delete(sub)
    await db.commit()
    return None
