import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.client import Client, LoyaltyAccount, LoyaltyTransaction, LoyaltyTxType
from app.models.pos import Transaction, TransactionItem
from app.models.product import Product, ProductStatus
from app.models.user import User

router = APIRouter(prefix="/crm", tags=["crm"])


# ---------------------------------------------------------------------------
# Public endpoint for client extranet
# ---------------------------------------------------------------------------

@router.get("/clients/lookup")
async def lookup_client(
    email: str = Query(..., description="Client email address"),
    db: AsyncSession = Depends(get_db),
):
    """Public lookup for client extranet. Returns client info, loyalty, and recent transactions."""
    result = await db.execute(
        select(Client).where(Client.email == email.strip().lower())
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

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
            "first_name": client.first_name,
            "last_name": client.last_name,
            "email": client.email,
            "phone": client.phone,
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
    """List clients with optional search."""
    query = select(Client)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Client.first_name.ilike(pattern),
                Client.last_name.ilike(pattern),
                Client.phone.ilike(pattern),
                Client.email.ilike(pattern),
            )
        )
    query = query.order_by(Client.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    clients = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "first_name": c.first_name,
            "last_name": c.last_name,
            "phone": c.phone,
            "email": c.email,
            "has_loyalty": c.loyalty_account is not None,
        }
        for c in clients
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
    """Send an email to a client. Uses SMTP if configured, otherwise simulates."""
    result = await db.execute(select(Client).where(Client.id == request.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.email:
        raise HTTPException(status_code=400, detail="Client has no email address")

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@vintiz.fr")

    if smtp_host and smtp_user and smtp_password:
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart("alternative")
            msg["Subject"] = request.subject
            msg["From"] = smtp_from
            msg["To"] = client.email

            html_part = MIMEText(request.body, "html", "utf-8")
            msg.attach(html_part)

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, client.email, msg.as_string())

            return {
                "status": "sent",
                "message": f"Email envoye a {client.email}",
                "client_id": str(request.client_id),
                "type": request.type,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur envoi email: {str(e)}")
    else:
        # Simulated send
        return {
            "status": "simulated",
            "message": f"[SIMULATION] Email '{request.subject}' envoye a {client.email} ({client.first_name} {client.last_name})",
            "client_id": str(request.client_id),
            "type": request.type,
            "sent_at": datetime.now(timezone.utc).isoformat(),
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
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur envoi SMS: {str(e)}")
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
    email: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Return AI-powered product recommendations for a client based on purchase history.

    Public endpoint (no auth) — uses email as identifier.
    """
    result = await db.execute(
        select(Client).where(Client.email == email.strip().lower())
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

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
