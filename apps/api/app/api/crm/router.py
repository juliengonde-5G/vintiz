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
from app.models.pos import Transaction
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


class UpdateClientRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None


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

    await db.flush()
    await db.refresh(client)
    await db.commit()
    return {
        "id": str(client.id),
        "first_name": client.first_name,
        "last_name": client.last_name,
        "phone": client.phone,
        "email": client.email,
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
