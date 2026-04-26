import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    email_clean = email.strip().lower()
    if "@" not in email_clean or "." not in email_clean.split("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Adresse email invalide")

    result = await db.execute(
        select(Client).where(Client.email == email_clean)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")

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
            "tier": la.tier,
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
    client = Client(
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
        email=request.email,
        notes=request.city,
        email_optin=request.email_optin,
        sms_optin=request.sms_optin,
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
                       la.points, la.tier
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
            "loyalty_tier": r["tier"] or "bronze",
        }
        for r in rows
    ]


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
            "tier": client.loyalty_account.tier,
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
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.loyalty_account:
        raise HTTPException(status_code=400, detail="Loyalty already active")

    account = LoyaltyAccount(
        client_id=client.id,
        points=0,
        tier="bronze",
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    await db.commit()
    return {
        "account_id": str(account.id),
        "client_id": str(client.id),
        "points": account.points,
        "tier": account.tier,
    }


@router.get("/clients/{client_id}/loyalty")
async def get_loyalty(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get loyalty balance for a client."""
    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.client_id == client_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="No loyalty account found")

    return {
        "account_id": str(account.id),
        "client_id": str(client_id),
        "points": account.points,
        "tier": account.tier,
        "transactions": [
            {
                "id": str(lt.id),
                "type": lt.tx_type.value,
                "points": lt.points,
                "description": lt.description,
                "created_at": lt.created_at.isoformat() if lt.created_at else None,
            }
            for lt in (account.transactions or [])
        ],
    }


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
    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.client_id == client_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="No loyalty account found")

    account.points += request.points

    tx = LoyaltyTransaction(
        account_id=account.id,
        tx_type=LoyaltyTxType.earn,
        points=request.points,
        description=request.description,
    )
    db.add(tx)
    await db.flush()
    await db.refresh(account)
    await db.commit()

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
    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.client_id == client_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="No loyalty account found")

    if account.points < request.points:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient points. Available: {account.points}, requested: {request.points}",
        )

    account.points -= request.points

    tx = LoyaltyTransaction(
        account_id=account.id,
        tx_type=LoyaltyTxType.redeem,
        points=request.points,
        description=request.description,
    )
    db.add(tx)
    await db.flush()
    await db.refresh(account)
    await db.commit()

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

    twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from_number = os.getenv("TWILIO_FROM_NUMBER", "")

    if twilio_account_sid and twilio_auth_token and twilio_from_number:
        try:
            from twilio.rest import Client as TwilioClient

            twilio_client = TwilioClient(twilio_account_sid, twilio_auth_token)
            message = twilio_client.messages.create(
                body=request.message,
                from_=twilio_from_number,
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

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@vintiz.fr")

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
# Personal Shopper (public — accessible from client extranet)
# ---------------------------------------------------------------------------

@router.get("/clients/personal-shopper")
async def get_personal_shopper(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Return AI-powered product recommendations for a client based on purchase history.

    Public endpoint (no auth) — uses email as identifier. As with /clients/lookup,
    this should be moved to a magic-link flow for proper protection.
    """
    email_clean = email.strip().lower()
    if "@" not in email_clean or "." not in email_clean.split("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Adresse email invalide")

    result = await db.execute(
        select(Client).where(Client.email == email_clean)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")

    # Collect all products purchased by this client
    tx_result = await db.execute(
        select(Transaction)
        .where(Transaction.client_id == client.id)
        .order_by(Transaction.created_at.desc())
        .limit(50)
    )
    transactions = tx_result.scalars().all()

    # Collect purchased product details
    purchased_brands: dict[str, int] = {}
    purchased_sizes: list[str] = []
    purchased_categories: dict[str, int] = {}

    for tx in transactions:
        for item in (tx.items or []):
            if item.product_id:
                prod_res = await db.execute(
                    select(Product).where(Product.id == item.product_id)
                )
                prod = prod_res.scalar_one_or_none()
                if prod:
                    if prod.brand:
                        purchased_brands[prod.brand] = purchased_brands.get(prod.brand, 0) + 1
                    if prod.size:
                        purchased_sizes.append(prod.size)
                    if prod.category:
                        cat_name = prod.category.name
                        purchased_categories[cat_name] = purchased_categories.get(cat_name, 0) + 1

    # Determine preferred brands (top 3) and most common size
    top_brands = sorted(purchased_brands.items(), key=lambda x: -x[1])[:3]
    top_brand_names = [b for b, _ in top_brands]
    preferred_size = max(set(purchased_sizes), key=purchased_sizes.count) if purchased_sizes else None
    top_categories = sorted(purchased_categories.items(), key=lambda x: -x[1])[:3]
    top_category_names = [c for c, _ in top_categories]

    # Find matching products in stock
    stock_query = select(Product).where(
        Product.status.in_([ProductStatus.stock, ProductStatus.display])
    )
    stock_result = await db.execute(stock_query.limit(500))
    all_stock = stock_result.scalars().all()

    # Score products by match
    def match_score(p: Product) -> int:
        score = 0
        if p.brand and p.brand in top_brand_names:
            idx = top_brand_names.index(p.brand)
            score += (3 - idx) * 10  # Higher for better-ranked brands
        if preferred_size and p.size == preferred_size:
            score += 8
        if p.category and p.category.name in top_category_names:
            idx = top_category_names.index(p.category.name)
            score += (3 - idx) * 5
        if p.trend_score:
            score += int(p.trend_score * 0.1)
        return score

    scored = [(match_score(p), p) for p in all_stock]
    scored.sort(key=lambda x: -x[0])
    top_matches = [p for _, p in scored if _ > 0][:8]

    # If not enough matches, pad with top-scored products
    if len(top_matches) < 4:
        extras = [p for _, p in scored if p not in top_matches][:4 - len(top_matches)]
        top_matches.extend(extras)

    recommendations = [
        {
            "id": str(p.id),
            "name": p.name,
            "brand": p.brand,
            "size": p.size,
            "color": p.color,
            "sale_price": float(p.sale_price),
            "category": p.category.name if p.category else None,
            "trend_score": p.trend_score,
            "zone_name": None,  # Can be enriched later
            "condition": getattr(p, "condition", None),
        }
        for p in top_matches
    ]

    # Claude-powered narrative
    narrative = None
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key and top_matches:
        try:
            import anthropic
            client_ai = anthropic.AsyncAnthropic(api_key=anthropic_key)
            items_str = ", ".join(p.name for p in top_matches[:4])
            brands_str = ", ".join(top_brand_names) if top_brand_names else "variées"
            prompt = f"""Tu es une styliste personnelle pour la boutique Vintiz (Vernon, Normandie — seconde main premium).
Ta cliente s'appelle {client.first_name}. Elle aime les marques : {brands_str}.
Taille habituelle : {preferred_size or 'non renseignée'}.
Pièces sélectionnées pour elle : {items_str}.
Écris un message chaleureux et élégant de 2-3 phrases pour lui présenter ces sélections. Sois enthousiaste, personnelle et fashion. Tutoie-la."""
            msg = await client_ai.messages.create(
                model="claude-haiku-4-5",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            narrative = msg.content[0].text if msg.content else None
        except Exception:
            pass

    if not narrative:
        narrative = f"Bonjour {client.first_name} ! Voici une sélection de pièces choisies spécialement pour toi, en accord avec tes goûts et ton style. Ces articles sont disponibles dès maintenant en boutique."

    return {
        "client": {"first_name": client.first_name, "last_name": client.last_name},
        "profile": {
            "preferred_brands": top_brand_names,
            "preferred_size": preferred_size,
            "preferred_categories": top_category_names,
        },
        "narrative": narrative,
        "recommendations": recommendations,
        "generated_at": datetime.now(timezone.utc).isoformat(),
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


class AccountActionRequest(BaseModel):
    email: str


def _normalize_email(value: str) -> str:
    cleaned = value.strip().lower()
    if "@" not in cleaned or "." not in cleaned.split("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    return cleaned


@router.get("/account/data-export")
async def public_account_data_export(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Public RGPD data export (Article 20 portability) by email lookup.

    Returns the JSON portable snapshot directly. The audit logger records the
    request via the SQLAlchemy listener; a future iteration will replace this
    with a magic-link confirmation flow to prevent email enumeration leakage.
    """
    from app.services.rgpd import RgpdService

    cleaned = _normalize_email(email)
    result = await db.execute(select(Client).where(Client.email == cleaned))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")
    return await RgpdService(db).export_client_data(client)


@router.post("/account/deletion-request")
async def public_account_deletion_request(
    request: AccountActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public RGPD deletion request (Article 17 erasure) by email lookup.

    Stamps the soft-delete timestamp; the daily cron purges past 30 days.
    The customer can cancel by re-submitting via the same flow within the
    window (a future iteration will surface a "cancel" button on the site).
    """
    from app.services.rgpd import RgpdService

    cleaned = _normalize_email(request.email)
    result = await db.execute(select(Client).where(Client.email == cleaned))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")

    if client.deletion_requested_at is not None:
        return {
            "client_email": cleaned,
            "deletion_requested_at": client.deletion_requested_at.isoformat(),
            "purge_after": (
                client.deletion_requested_at + timedelta(days=30)
            ).isoformat(),
            "already_pending": True,
        }
    requested_at = await RgpdService(db).request_deletion(client)
    await db.commit()
    return {
        "client_email": cleaned,
        "deletion_requested_at": requested_at.isoformat(),
        "purge_after": (requested_at + timedelta(days=30)).isoformat(),
        "already_pending": False,
    }


@router.post("/account/deletion-cancel")
async def public_account_deletion_cancel(
    request: AccountActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public cancellation of a pending deletion request (within the 30-day window)."""
    from app.services.rgpd import RgpdService

    cleaned = _normalize_email(request.email)
    result = await db.execute(select(Client).where(Client.email == cleaned))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")
    if client.deletion_requested_at is None:
        return {"client_email": cleaned, "deletion_cancelled": True, "was_pending": False}
    await RgpdService(db).cancel_deletion(client)
    await db.commit()
    return {"client_email": cleaned, "deletion_cancelled": True, "was_pending": True}


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

    Pipeline: embedding similarity → diversify by category → size filter →
    Claude Haiku rewrite (fallback to deterministic template if the API
    isn't reachable). Manager / staff only — the public flavour goes
    through ``/api/crm/personal-shopper-v2``.
    """
    from app.services.personal_shopper import PersonalShopperService

    try:
        result = await PersonalShopperService(db).recommend(
            client_id, top_n=max(1, min(top_n, 10)), weather_summary=weather,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
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

    Same pipeline as the authenticated endpoint; the email is the only
    identification, which mirrors the existing public lookup pattern.
    Future iteration: magic-link verification before serving (consistent
    with the RGPD endpoints).
    """
    from app.services.personal_shopper import PersonalShopperService

    cleaned = _normalize_email(email)
    result_row = await db.execute(select(Client).where(Client.email == cleaned))
    client = result_row.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")
    result = await PersonalShopperService(db).recommend(
        client.id, top_n=max(1, min(top_n, 10)), weather_summary=weather,
    )
    await db.commit()
    return result


# ---------------------------------------------------------------------------
# Cold-start onboarding (P2-004)
# ---------------------------------------------------------------------------


class OnboardingRequest(BaseModel):
    liked_style_keys: list[str] = []
    preferred_occasions: list[str] = []
    preferred_price_buckets: list[str] = []
    preferred_categories: list[str] = []


class PublicOnboardingRequest(OnboardingRequest):
    email: str


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


@router.post("/account/onboarding")
async def public_submit_onboarding(
    request: PublicOnboardingRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public: same as the authenticated endpoint, identified by email."""
    from app.services.onboarding import cold_start_taste_profile

    cleaned = _normalize_email(request.email)
    result = await db.execute(select(Client).where(Client.email == cleaned))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")

    profile = await cold_start_taste_profile(
        db, client,
        liked_style_keys=request.liked_style_keys,
        preferred_occasions=request.preferred_occasions,
        preferred_price_buckets=request.preferred_price_buckets,
        preferred_categories=request.preferred_categories,
    )
    await db.commit()
    return {
        "client_email": cleaned,
        "profile_id": str(profile.id),
        "algo_version": profile.algo_version,
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


@router.get("/account/wallet")
async def public_wallet_pass(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Return the loyalty Wallet pass payload by client email.

    Generic 404 on unknown email — same shape as ``/clients/lookup`` so
    we don't expose enumeration. The payload contains the Apple
    ``pass.json`` and the Google ``LoyaltyObject`` plus the metadata the
    front needs to render a preview card.
    """
    from app.services.wallet import build_pass_by_email, payload_to_dict

    email_clean = email.strip().lower()
    if "@" not in email_clean or "." not in email_clean.split("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    pass_payload = await build_pass_by_email(db, email_clean)
    if pass_payload is None:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    return payload_to_dict(pass_payload)


@router.get("/clients/{client_id}/wallet")
async def client_wallet_pass(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manager-side wallet payload (preview a client's pass)."""
    from app.services.wallet import build_pass_for_client, payload_to_dict

    pass_payload = await build_pass_for_client(db, client_id)
    if pass_payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return payload_to_dict(pass_payload)
