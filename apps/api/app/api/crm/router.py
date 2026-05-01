import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.client import (
    AvoirTransaction,
    Client,
    Consent,
    ConsentPurpose,
    LoyaltyAccount,
    LoyaltyTransaction,
    LoyaltyTxType,
)
from app.models.pos import Transaction
from app.models.product import Product, ProductStatus
from app.models.user import User

logger = logging.getLogger("vintiz")

router = APIRouter(prefix="/crm", tags=["crm"])

# Sub-routers (Sprint 3 #12 — split monolith).
from app.api.crm import account as _account_module  # noqa: E402
from app.api.crm.account import OnboardingRequest  # noqa: E402,F401 — re-used by manager-side endpoint
router.include_router(_account_module.router)

# ---------------------------------------------------------------------------
# Public endpoint for client extranet
# ---------------------------------------------------------------------------

@router.get("/clients/lookup")
async def lookup_client(
    email: str = Query(..., description="Client email address", min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Public lookup for client extranet.

    Returns client info, loyalty, and recent transactions. Returns a generic
    404 message when no account exists, to limit account enumeration. A proper
    fix requires a magic-link / OTP flow (see correction plan).
    """
    from app.services.client_lookup import get_client_by_email
    client = await get_client_by_email(db, email, raise_if_missing=True)

    loyalty_data = None
    if client.loyalty_account:
        la = client.loyalty_account
        # Calculate total earned/redeemed
        earn_result = await db.execute(
            select(LoyaltyTransaction).where(
                LoyaltyTransaction.account_id == la.id,
                LoyaltyTransaction.tx_type == LoyaltyTxType.earn,
            )
        )
        earned_txs = earn_result.scalars().all()
        total_earned = sum(t.points for t in earned_txs)

        redeem_result = await db.execute(
            select(LoyaltyTransaction).where(
                LoyaltyTransaction.account_id == la.id,
                LoyaltyTransaction.tx_type == LoyaltyTxType.redeem,
            )
        )
        redeemed_txs = redeem_result.scalars().all()
        total_redeemed = sum(t.points for t in redeemed_txs)

        loyalty_data = {
            "points": la.points,
            "total_earned": total_earned,
            "total_redeemed": total_redeemed,
            "membership_number": la.membership_number,
        }

    # Recent transactions
    tx_result = await db.execute(
        select(Transaction)
        .where(Transaction.client_id == client.id)
        .order_by(Transaction.created_at.desc())
        .limit(20)
    )
    transactions = tx_result.scalars().all()

    return {
        "client": {
            "id": str(client.id),
            "first_name": client.first_name,
            "last_name": client.last_name,
            "email": client.email,
            "phone": client.phone,
            "email_optin": client.email_optin,
            "sms_optin": client.sms_optin,
            "avoir_balance": float(client.avoir_credit or 0),
            "deletion_pending": client.deletion_requested_at is not None,
        },
        "loyalty": loyalty_data,
        "recent_transactions": [
            {
                "id": str(t.id),
                "transaction_number": t.transaction_number,
                "total_ttc": float(t.total_ttc),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in transactions
        ],
    }

# ---------------------------------------------------------------------------
# L2.3 — Enriched customer brief for POS upsell
# ---------------------------------------------------------------------------

@router.get("/clients/{client_id}/brief")
async def get_client_brief(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return the enriched LoyaltyCustomerCard payload for the POS.

    Same data than ``GET /clients/lookup`` but augmented with :
    - Last visit + days since
    - Lifetime value
    - Favorite categories / brands / colors / sizes
    - 3 Personal Shopper picks (with fallback to top-score)
    - Anniversary coupon
    - RFM segment

    See ``services/customer_brief.py`` for the aggregation logic.
    """
    from app.services.customer_brief import get_customer_brief

    brief = await get_customer_brief(db, client_id)
    if not brief:
        raise HTTPException(status_code=404, detail="Client not found")
    return brief

@router.get("/clients/lookup-brief")
async def lookup_client_brief(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Email-based lookup that returns the enriched brief in 1 call.

    Used by the POS at card scan : Sophie types/scans, instantly sees the
    `LoyaltyCustomerCard` panel with last visit, favorite categories, and
    3 PS picks ready to be tapped into the cart.
    """
    from app.services.client_lookup import get_client_by_email
    from app.services.customer_brief import get_customer_brief

    client = await get_client_by_email(db, email, raise_if_missing=True)
    brief = await get_customer_brief(db, client.id)
    return brief

# ---------------------------------------------------------------------------
# Authenticated CRM endpoints
# ---------------------------------------------------------------------------

class CreateClientRequest(BaseModel):
    first_name: str
    last_name: str
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    email_optin: bool = False
    sms_optin: bool = False
    # L3.4 — Allows seed scripts (witness clients) to flag rows for purge.
    # Only honored when the caller is a manager.
    is_test: bool = False

class UpdateClientRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    email_optin: bool | None = None
    sms_optin: bool | None = None

@router.post("/clients")
async def create_client(
    request: CreateClientRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new client."""
    # is_test honored only for manager users (admin seed scripts).
    is_test_flag = bool(
        request.is_test
        and getattr(current_user, "role", None)
        and str(current_user.role).lower().endswith("manager")
    )
    client = Client(
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
        email=request.email,
        notes=request.city,
        email_optin=request.email_optin,
        sms_optin=request.sms_optin,
        is_test=is_test_flag,
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)
    await db.commit()
    return {
        "id": str(client.id),
        "first_name": client.first_name,
        "last_name": client.last_name,
        "phone": client.phone,
        "email": client.email,
        "email_optin": client.email_optin,
        "sms_optin": client.sms_optin,
    }

@router.get("/clients")
async def list_clients(
    search: str | None = Query(None, description="Search by name, phone, or email"),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List clients with optional search — raw SQL to avoid ORM/async lazy-load issues."""
    from sqlalchemy import text

    where = ""
    params: dict = {"skip": skip, "limit": limit}
    if search:
        where = (
            "WHERE (c.first_name ILIKE :s OR c.last_name ILIKE :s "
            "OR c.phone ILIKE :s OR c.email ILIKE :s)"
        )
        params["s"] = f"%{search}%"

    # Try with optional optin columns; fall back if they don't exist yet in DB
    for optin_select in (
        "COALESCE(c.email_optin, false) AS email_optin, COALESCE(c.sms_optin, false) AS sms_optin,",
        "false AS email_optin, false AS sms_optin,",
    ):
        try:
            sql = text(f"""
                SELECT c.id, c.first_name, c.last_name, c.phone, c.email,
                       {optin_select}
                       la.points, la.membership_number
                FROM clients c
                LEFT JOIN loyalty_accounts la ON la.client_id = c.id
                {where}
                ORDER BY c.created_at DESC
                OFFSET :skip LIMIT :limit
            """)
            rows = (await db.execute(sql, params)).mappings().all()
            break
        except Exception:
            await db.rollback()
    else:
        return []

    return [
        {
            "id": str(r["id"]),
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "phone": r["phone"],
            "email": r["email"],
            "email_optin": bool(r["email_optin"]),
            "sms_optin": bool(r["sms_optin"]),
            "loyalty_active": r["points"] is not None,
            "loyalty_points": r["points"] or 0,
            "membership_number": r["membership_number"],
        }
        for r in rows
    ]

@router.get("/clients/{client_id}/full")
async def get_client_full(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregated client detail for the admin /clients/[id] page (PR4).

    Returns 6 sections in a single round-trip:
    - ``client``         — identity, contact, opt-ins, RFM, avoir.
    - ``loyalty``        — membership_number, points, mode, expiry.
    - ``transactions``   — last 50 sales/refunds with item names.
    - ``taste_profile``  — top categories/brands/colors/sizes (90d window).
    - ``consents``       — latest decision per RGPD purpose with metadata.
    - ``audit``          — last 50 audit_log rows scoped to this client.
    """
    from sqlalchemy.orm import selectinload

    from app.models.audit import AuditLog
    from app.models.coupon import Coupon
    from app.services.customer_brief import get_customer_brief

    row = await db.execute(
        select(Client)
        .options(selectinload(Client.loyalty_account))
        .where(Client.id == client_id)
    )
    client = row.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Reuse the existing brief — it already aggregates favorite
    # categories / brands / colors / sizes + last visit.
    brief = await get_customer_brief(db, client_id)
    taste = {
        "favorite_categories": (brief or {}).get("favorite_categories", []),
        "favorite_brands": (brief or {}).get("favorite_brands", []),
        "favorite_colors": (brief or {}).get("favorite_colors", []),
        "size_profile": (brief or {}).get("size_profile", {}),
        "lifetime_value": (brief or {}).get("lifetime_value", 0),
        "last_visit": (brief or {}).get("last_visit"),
        "days_since_last_visit": (brief or {}).get("days_since_last_visit"),
    }

    # Last 50 transactions with item names + payment summary.
    from app.models.pos import TransactionItem

    tx_rows = await db.execute(
        select(Transaction)
        .options(
            selectinload(Transaction.items).selectinload(TransactionItem.product),
            selectinload(Transaction.payments),
        )
        .where(Transaction.client_id == client_id)
        .order_by(Transaction.created_at.desc())
        .limit(50)
    )
    transactions = []
    for t in tx_rows.scalars().all():
        transactions.append({
            "id": str(t.id),
            "transaction_number": t.transaction_number,
            "transaction_type": t.transaction_type.value,
            "total_ttc": float(t.total_ttc or 0),
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "item_count": len(t.items or []),
            "payment_methods": sorted({p.method.value for p in (t.payments or [])}),
        })

    # Loyalty ledger — last 30 entries.
    loyalty_block = None
    if client.loyalty_account:
        ledger_rows = await db.execute(
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.account_id == client.loyalty_account.id)
            .order_by(LoyaltyTransaction.created_at.desc())
            .limit(30)
        )
        loyalty_block = {
            "membership_number": client.loyalty_account.membership_number,
            "points": int(client.loyalty_account.points or 0),
            "mode": client.loyalty_subscription_mode,
            "subscribed_at": client.loyalty_subscribed_at.isoformat()
            if client.loyalty_subscribed_at else None,
            "expires_at": client.loyalty_expires_at.isoformat()
            if client.loyalty_expires_at else None,
            "ledger": [
                {
                    "id": str(lt.id),
                    "type": lt.tx_type.value,
                    "points": int(lt.points or 0),
                    "description": lt.description,
                    "created_at": lt.created_at.isoformat() if lt.created_at else None,
                }
                for lt in ledger_rows.scalars().all()
            ],
        }

    # Consents — same shape as /account/consents (latest per purpose).
    consent_rows = await db.execute(
        select(Consent)
        .where(Consent.client_id == client_id)
        .order_by(Consent.created_at.desc())
    )
    latest_per_purpose: dict[ConsentPurpose, Consent] = {}
    for c in consent_rows.scalars().all():
        latest_per_purpose.setdefault(c.purpose, c)
    consents = [
        {
            "purpose": purpose.value,
            "granted": bool(latest_per_purpose[purpose].granted)
            if purpose in latest_per_purpose else False,
            "source": latest_per_purpose[purpose].source if purpose in latest_per_purpose else None,
            "policy_version": latest_per_purpose[purpose].policy_version
            if purpose in latest_per_purpose else None,
            "recorded_at": latest_per_purpose[purpose].created_at.isoformat()
            if purpose in latest_per_purpose and latest_per_purpose[purpose].created_at else None,
        }
        for purpose in ConsentPurpose
    ]

    # Audit log — entity_id == client.id is the simplest scoping; the
    # audit service writes one row per Client mutation already.
    audit_rows = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == client_id)
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    )
    audit = [
        {
            "id": str(a.id),
            "action": a.action,
            "entity": a.entity,
            "data": a.data,
            "user_id": str(a.user_id) if a.user_id else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in audit_rows.scalars().all()
    ]

    # Active coupons attached.
    coupon_rows = await db.execute(
        select(Coupon)
        .where(
            Coupon.client_id == client_id,
            Coupon.is_active.is_(True),
            Coupon.redeemed_at.is_(None),
        )
        .order_by(Coupon.valid_until.asc())
    )
    coupons = [
        {
            "code": c.code,
            "discount_type": c.discount_type.value,
            "discount_value": float(c.discount_value or 0),
            "source": c.source.value if c.source else None,
            "valid_until": c.valid_until.isoformat() if c.valid_until else None,
        }
        for c in coupon_rows.scalars().all()
    ]

    return {
        "client": {
            "id": str(client.id),
            "first_name": client.first_name,
            "last_name": client.last_name,
            "email": client.email,
            "phone": client.phone,
            "notes": client.notes,
            "email_optin": client.email_optin,
            "sms_optin": client.sms_optin,
            "rfm_segment": client.rfm_segment,
            "avoir_balance": float(client.avoir_credit or 0),
            "deletion_pending": client.deletion_requested_at is not None,
            "created_at": client.created_at.isoformat() if client.created_at else None,
        },
        "loyalty": loyalty_block,
        "taste_profile": taste,
        "transactions": transactions,
        "consents": consents,
        "coupons": coupons,
        "audit": audit,
    }

@router.get("/clients/{client_id}")
async def get_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get client details with purchase history."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Purchase history
    tx_result = await db.execute(
        select(Transaction)
        .where(Transaction.client_id == client_id)
        .order_by(Transaction.created_at.desc())
        .limit(50)
    )
    transactions = tx_result.scalars().all()

    loyalty_data = None
    if client.loyalty_account:
        loyalty_data = {
            "points": client.loyalty_account.points,
            "membership_number": client.loyalty_account.membership_number,
        }

    return {
        "id": str(client.id),
        "first_name": client.first_name,
        "last_name": client.last_name,
        "phone": client.phone,
        "email": client.email,
        "notes": client.notes,
        "email_optin": client.email_optin,
        "sms_optin": client.sms_optin,
        "loyalty": loyalty_data,
        "avoir_balance": float(client.avoir_credit or 0),
        "purchases": [
            {
                "id": str(t.id),
                "transaction_number": t.transaction_number,
                "total_ttc": float(t.total_ttc),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in transactions
        ],
    }

@router.put("/clients/{client_id}")
async def update_client(
    client_id: uuid.UUID,
    request: UpdateClientRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update client information."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if request.first_name is not None:
        client.first_name = request.first_name
    if request.last_name is not None:
        client.last_name = request.last_name
    if request.phone is not None:
        client.phone = request.phone
    if request.email is not None:
        client.email = request.email
    if request.city is not None:
        client.notes = request.city
    if request.email_optin is not None:
        client.email_optin = request.email_optin
    if request.sms_optin is not None:
        client.sms_optin = request.sms_optin

    await db.flush()
    await db.refresh(client)
    await db.commit()
    return {
        "id": str(client.id),
        "first_name": client.first_name,
        "last_name": client.last_name,
        "phone": client.phone,
        "email": client.email,
        "email_optin": client.email_optin,
        "sms_optin": client.sms_optin,
    }

@router.post("/clients/{client_id}/loyalty/activate")
async def activate_loyalty(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Activate a loyalty account for a client."""
    from app.services.loyalty import LoyaltyService
    account = await LoyaltyService(db).activate(client_id)
    return {
        "account_id": str(account.id),
        "client_id": str(account.client_id),
        "points": account.points,
        "membership_number": account.membership_number,
    }

@router.get("/clients/{client_id}/loyalty")
async def get_loyalty(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get loyalty balance for a client."""
    from app.services.loyalty import LoyaltyService
    svc = LoyaltyService(db)
    account = await svc.get_account(client_id)
    return svc.serialize(account)

class LoyaltyPointsRequest(BaseModel):
    points: int
    description: str

@router.post("/clients/{client_id}/loyalty/earn")
async def earn_loyalty_points(
    client_id: uuid.UUID,
    request: LoyaltyPointsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add points to a client's loyalty account."""
    from app.services.loyalty import LoyaltyService
    account = await LoyaltyService(db).earn(client_id, request.points, request.description)
    return {
        "account_id": str(account.id),
        "client_id": str(client_id),
        "points": account.points,
        "earned": request.points,
    }

@router.post("/clients/{client_id}/loyalty/redeem")
async def redeem_loyalty_points(
    client_id: uuid.UUID,
    request: LoyaltyPointsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Redeem points from a client's loyalty account."""
    from app.services.loyalty import LoyaltyService
    account = await LoyaltyService(db).redeem(client_id, request.points, request.description)
    return {
        "account_id": str(account.id),
        "client_id": str(client_id),
        "points": account.points,
        "redeemed": request.points,
    }

# ---------------------------------------------------------------------------
# Email / SMS sending
# ---------------------------------------------------------------------------

class SendEmailRequest(BaseModel):
    client_id: uuid.UUID
    subject: str
    body: str
    type: str = "marketing"  # "ticket" | "marketing"

class SendSMSRequest(BaseModel):
    client_id: uuid.UUID
    message: str

@router.post("/send-email")
async def send_email(
    request: SendEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send an email to a client through the unified gateway (P4-003).
    Brevo > SMTP > simulation depending on what's configured."""
    from app.services.email_gateway import (
        EmailDeliveryError,
        EmailMessage,
        send_email as _gateway_send,
    )

    result = await db.execute(select(Client).where(Client.id == request.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.email:
        raise HTTPException(status_code=400, detail="Client has no email address")

    try:
        outcome = _gateway_send(EmailMessage(
            to=client.email,
            to_name=f"{client.first_name} {client.last_name}".strip() or None,
            subject=request.subject,
            html=request.body,
        ))
    except EmailDeliveryError as exc:
        logger.warning("send-email gateway error for client_id=%s: %s",
                       request.client_id, exc)
        raise HTTPException(
            status_code=502,
            detail="L'envoi de l'email a échoué. Réessayez plus tard.",
        )

    return {
        "status": outcome.status,
        "backend": outcome.backend,
        "message": f"Email '{request.subject}' → {client.email}",
        "client_id": str(request.client_id),
        "type": request.type,
        "sent_at": outcome.sent_at,
    }

@router.post("/send-sms")
async def send_sms(
    request: SendSMSRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send an SMS to a client. Uses Twilio if configured, otherwise simulates."""
    result = await db.execute(select(Client).where(Client.id == request.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.phone:
        raise HTTPException(status_code=400, detail="Client has no phone number")

    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM:
        try:
            from twilio.rest import Client as TwilioClient

            twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            message = twilio_client.messages.create(
                body=request.message,
                from_=settings.TWILIO_FROM,
                to=client.phone,
            )
            return {
                "status": "sent",
                "message": f"SMS envoye au {client.phone}",
                "client_id": str(request.client_id),
                "sid": message.sid,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            logger.exception("send-sms failed for client_id=%s", request.client_id)
            raise HTTPException(
                status_code=502,
                detail="L'envoi du SMS a échoué. Réessayez plus tard.",
            )
    else:
        # Simulated send
        return {
            "status": "simulated",
            "message": f"[SIMULATION] SMS envoye au {client.phone} ({client.first_name} {client.last_name}): '{request.message}'",
            "client_id": str(request.client_id),
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

WELCOME_EMAIL_TEMPLATE = """\
<html><body style="font-family: Georgia, serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #2C2C2C;">
<h1 style="color: #1A7A6A; font-size: 24px;">Bienvenue chez Vintiz, {first_name} !</h1>
<p style="font-size: 16px; line-height: 1.6;">
  Nous sommes ravis de vous accueillir dans notre boutique de mode premium de seconde main,
  au cœur de Vernon. Chaque pièce que nous sélectionnons a été choisie avec soin pour vous
  offrir qualité, style et responsabilité.
</p>
<p style="font-size: 16px; line-height: 1.6;">
  Retrouvez-nous au <strong>6 rue Saint-Jacques, 27200 Vernon</strong> ou découvrez nos
  nouvelles arrivées sur notre site.
</p>
<p style="font-size: 14px; color: #666; margin-top: 30px;">
  Pour vous désabonner de nos communications marketing, contactez-nous à
  <a href="mailto:contact@vintiz.fr" style="color: #1A7A6A;">contact@vintiz.fr</a>.
</p>
<p style="font-size: 12px; color: #999;">
  Vintiz — 6 rue Saint-Jacques, 27200 Vernon | SIRET : XXX XXX XXX XXXXX
</p>
</body></html>
"""

@router.post("/campaigns/welcome")
async def send_welcome_campaign(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send welcome email to all clients with email_optin=True.
    Uses SMTP if configured, otherwise simulates sending.
    """
    result = await db.execute(
        select(Client).where(Client.email_optin == True, Client.email.isnot(None))  # noqa: E712
    )
    clients = result.scalars().all()

    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    smtp_user = settings.SMTP_USER
    smtp_password = settings.SMTP_PASSWORD
    smtp_from = settings.SMTP_FROM or smtp_user or "noreply@vintiz.fr"

    sent = 0
    simulated = 0
    errors = 0

    for client in clients:
        try:
            subject = f"Bienvenue chez Vintiz, {client.first_name} !"
            body = WELCOME_EMAIL_TEMPLATE.format(first_name=client.first_name)

            if smtp_host and smtp_user and smtp_password:
                import smtplib
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText

                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = smtp_from
                msg["To"] = client.email

                msg.attach(MIMEText(body, "html", "utf-8"))
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.sendmail(smtp_from, client.email, msg.as_string())
                sent += 1
            else:
                simulated += 1
        except Exception:
            logger.exception(
                "welcome campaign: send failed for client_id=%s",
                getattr(client, "id", "unknown"),
            )
            errors += 1

    return {
        "total_eligible": len(clients),
        "sent": sent,
        "simulated": simulated,
        "errors": errors,
        "smtp_configured": bool(smtp_host and smtp_user and smtp_password),
    }

# ---------------------------------------------------------------------------
# Avoir / store credit (P1-016)
# ---------------------------------------------------------------------------

@router.get("/clients/{client_id}/avoir")
async def get_client_avoir(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the client's avoir balance and transaction history."""
    from app.services.refund import RefundService

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    refund_service = RefundService(db)
    history = await refund_service.list_avoir_history(client_id)
    return {
        "client_id": str(client.id),
        "balance": float(client.avoir_credit or 0),
        "history": history,
    }

# ---------------------------------------------------------------------------
# RGPD endpoints (P1-007) — manager only
# ---------------------------------------------------------------------------

class ConsentRequest(BaseModel):
    purpose: str  # email_marketing | sms_marketing | profiling | data_sharing
    granted: bool
    source: str = "admin"  # site_signup | pos | admin | import
    policy_version: str | None = None

@router.get("/clients/{client_id}/consents")
async def get_client_consents(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return current consent state per purpose + full history."""
    from app.services.rgpd import RgpdService

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    svc = RgpdService(db)
    return {
        "client_id": str(client.id),
        "current": await svc.current_consents(client.id),
        "history": await svc.consent_history(client.id),
    }

@router.post("/clients/{client_id}/consents")
async def record_client_consent(
    client_id: uuid.UUID,
    request: ConsentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a consent grant or revoke for a single purpose."""
    from app.services.rgpd import RgpdService

    try:
        purpose = ConsentPurpose(request.purpose)
    except ValueError:
        valid = ", ".join(p.value for p in ConsentPurpose)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid consent purpose. Valid values: {valid}",
        )

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    svc = RgpdService(db)
    entry = await svc.record_consent(
        client=client,
        purpose=purpose,
        granted=request.granted,
        source=request.source,
        recorded_by_user_id=current_user.id,
        policy_version=request.policy_version,
    )
    await db.commit()
    return {
        "id": str(entry.id),
        "purpose": entry.purpose.value,
        "granted": entry.granted,
        "policy_version": entry.policy_version,
        "recorded_at": entry.created_at.isoformat() if entry.created_at else None,
    }

@router.get("/clients/{client_id}/data-export")
async def export_client_data(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a portable JSON snapshot of everything we hold about the client
    (Article 20 RGPD — data portability)."""
    from app.services.rgpd import RgpdService

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    return await RgpdService(db).export_client_data(client)

@router.post("/clients/{client_id}/deletion-request")
async def request_client_deletion(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete: stamps the 30-day grace window. The daily cron purges
    clients whose request is older than DELETION_WINDOW."""
    from app.services.rgpd import RgpdService

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    requested_at = await RgpdService(db).request_deletion(client)
    await db.commit()
    return {
        "client_id": str(client.id),
        "deletion_requested_at": requested_at.isoformat(),
        "purge_after": (requested_at + timedelta(days=30)).isoformat(),
    }

# ---------------------------------------------------------------------------
# Public account self-service (P1-007 — accessed from apps/site /account/data)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Personal Shopper v2 (P2-003) — embeddings + Claude rewrite
# ---------------------------------------------------------------------------

class RecommendationClickRequest(BaseModel):
    recommendation_set_id: uuid.UUID
    product_id: uuid.UUID
    customer_email: str | None = None
    position_in_list: int | None = None

@router.get("/clients/{client_id}/personal-shopper-v2")
async def personal_shopper_v2(
    client_id: uuid.UUID,
    top_n: int = 4,
    weather: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Build a Personal Shopper v2 recommendation set for a client.

    PR2 gating: 403 if the client is not loyalty-active or hasn't
    granted profiling consent. Manager / staff only — the public
    flavour goes through ``/api/crm/personal-shopper-v2``.
    """
    from app.services.personal_shopper import (
        PersonalShopperGatedError,
        PersonalShopperService,
    )

    try:
        result = await PersonalShopperService(db).recommend(
            client_id, top_n=max(1, min(top_n, 10)), weather_summary=weather,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonalShopperGatedError as exc:
        raise HTTPException(status_code=403, detail=exc.reason)
    await db.commit()
    return result

@router.get("/personal-shopper-v2")
async def public_personal_shopper_v2(
    email: str = Query(..., min_length=5, max_length=255),
    top_n: int = 4,
    weather: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Public flavour of Personal Shopper v2 — email-based lookup.

    PR2 gating: 403 if the customer isn't a member or hasn't opted-in
    to profiling. Same pipeline as the authenticated endpoint.
    """
    from app.services.personal_shopper import (
        PersonalShopperGatedError,
        PersonalShopperService,
    )

    cleaned = _normalize_email(email)
    result_row = await db.execute(select(Client).where(Client.email == cleaned))
    client = result_row.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")
    try:
        result = await PersonalShopperService(db).recommend(
            client.id, top_n=max(1, min(top_n, 10)), weather_summary=weather,
        )
    except PersonalShopperGatedError as exc:
        raise HTTPException(status_code=403, detail=exc.reason)
    await db.commit()
    return result

# ---------------------------------------------------------------------------
# Personal Shopper public toggles + free-text search (PR2)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Espace client — coupons / transactions / consents (PR3)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Cold-start onboarding (P2-004)
# ---------------------------------------------------------------------------

@router.get("/onboarding/options")
async def onboarding_options():
    """Public catalogue of style profiles, occasions and price buckets the
    picker UI displays. Static data — no DB hit."""
    from app.services.onboarding import (
        list_available_occasions,
        list_available_price_buckets,
        list_available_style_profiles,
    )

    return {
        "styles": list_available_style_profiles(),
        "occasions": list_available_occasions(),
        "price_buckets": list_available_price_buckets(),
    }

@router.post("/clients/{client_id}/onboarding")
async def submit_onboarding(
    client_id: uuid.UUID,
    request: OnboardingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manager-side: build (or refresh) a cold-start taste profile for a
    client whose history is too thin for the daily cron."""
    from app.services.onboarding import cold_start_taste_profile

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    profile = await cold_start_taste_profile(
        db, client,
        liked_style_keys=request.liked_style_keys,
        preferred_occasions=request.preferred_occasions,
        preferred_price_buckets=request.preferred_price_buckets,
        preferred_categories=request.preferred_categories,
    )
    await db.commit()
    return {
        "client_id": str(client.id),
        "profile_id": str(profile.id),
        "algo_version": profile.algo_version,
        "computed_at": profile.computed_at.isoformat() if profile.computed_at else None,
    }

@router.post("/personal-shopper-v2/click")
async def personal_shopper_click(
    request: RecommendationClickRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public click-through endpoint. Logs ``customer.recommendation_clicked``."""
    from app.services.personal_shopper import PersonalShopperService

    customer_id: uuid.UUID | None = None
    if request.customer_email:
        cleaned = _normalize_email(request.customer_email)
        result_row = await db.execute(
            select(Client).where(Client.email == cleaned)
        )
        client = result_row.scalar_one_or_none()
        if client is not None:
            customer_id = client.id

    await PersonalShopperService(db).record_click(
        recommendation_set_id=request.recommendation_set_id,
        product_id=request.product_id,
        customer_id=customer_id,
        position_in_list=request.position_in_list,
    )
    await db.commit()
    return {"recorded": True}

@router.post("/clients/{client_id}/deletion-cancel")
async def cancel_client_deletion(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a pending deletion request (only valid before the cron runs)."""
    from app.services.rgpd import RgpdService

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    await RgpdService(db).cancel_deletion(client)
    await db.commit()
    return {"client_id": str(client.id), "deletion_cancelled": True}

# ---------------------------------------------------------------------------
# RFM segmentation read endpoints (P4-007)
# ---------------------------------------------------------------------------

@router.get("/segments")
async def list_rfm_segments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate counts of clients per RFM segment, plus a sample list."""
    from app.services.rfm import segment_summary

    counts = await segment_summary(db)
    total = sum(counts.values())
    return {
        "total_segmented": total,
        "segments": [
            {"segment": seg, "count": cnt}
            for seg, cnt in sorted(counts.items(), key=lambda kv: -kv[1])
        ],
    }

@router.get("/segments/{segment}")
async def list_clients_in_segment(
    segment: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sample of clients in a given RFM segment (champion, loyal, …)."""
    result = await db.execute(
        select(Client)
        .where(Client.rfm_segment == segment)
        .order_by(Client.updated_at.desc())
        .limit(limit)
    )
    clients = result.scalars().all()
    return {
        "segment": segment,
        "count": len(clients),
        "clients": [
            {
                "id": str(c.id),
                "email": c.email,
                "first_name": c.first_name,
                "last_name": c.last_name,
                "rfm_segment": c.rfm_segment,
            }
            for c in clients
        ],
    }

# ---------------------------------------------------------------------------
# Wallet pass (P4-004) — public lookup by email + manager-side by id
# ---------------------------------------------------------------------------

@router.get("/clients/{client_id}/wallet")
async def client_wallet_pass(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manager-side wallet payload (preview a client's pass)."""
    from app.services.wallet import (
        apple_wallet_available,
        build_pass_for_client,
        google_wallet_available,
        payload_to_dict,
    )

    pass_payload = await build_pass_for_client(db, client_id)
    if pass_payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    out = payload_to_dict(pass_payload)
    out["apple_signed_available"] = apple_wallet_available()
    out["google_save_available"] = google_wallet_available()
    return out

# ---------------------------------------------------------------------------
# Wallet downloads — Apple .pkpass / Google save URL / QR fallback
# ---------------------------------------------------------------------------

@router.get("/curation/current")
async def public_curation_current(db: AsyncSession = Depends(get_db)):
    """Return the active manager-curated selection (resolved to live products).

    Used by /account/selection. Drops any product that is no longer in stock
    so we never advertise a sold piece.
    """
    from app.services.app_config import get_section
    from app.models.product import Product, ProductStatus
    import uuid as _uuid

    section = get_section("curation_picks") or {}
    raw_items: list[dict] = section.get("items") or []
    if not raw_items:
        return {"items": [], "curator_note": section.get("curator_note", ""), "updated_at": section.get("updated_at", "")}

    # Resolve UUIDs (defensive)
    ids: list = []
    reasons: dict[str, str] = {}
    for it in raw_items:
        pid = it.get("product_id")
        if not pid:
            continue
        try:
            uid = _uuid.UUID(pid)
            ids.append(uid)
            reasons[str(uid)] = it.get("reason") or ""
        except (ValueError, TypeError):
            continue
    if not ids:
        return {"items": [], "curator_note": section.get("curator_note", ""), "updated_at": section.get("updated_at", "")}

    rows = (
        await db.execute(
            select(Product)
            .where(Product.id.in_(ids))
            .where(Product.status.in_([ProductStatus.stock, ProductStatus.display]))
        )
    ).scalars().all()

    by_id = {str(p.id): p for p in rows}
    out: list[dict] = []
    for it in raw_items:
        p = by_id.get(it.get("product_id", ""))
        if not p:
            continue
        out.append(
            {
                "id": str(p.id),
                "name": p.name,
                "barcode": p.barcode,
                "brand": p.brand,
                "size": p.size,
                "color": p.color,
                "sale_price": float(p.sale_price or 0),
                "photo_url": p.photo_url,
                "reason": reasons.get(str(p.id), ""),
            }
        )
    return {
        "items": out,
        "curator_note": section.get("curator_note", ""),
        "updated_at": section.get("updated_at", ""),
    }

