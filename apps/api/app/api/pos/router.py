from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.pos import PosService
from app.services.fiscal import FiscalService
from pydantic import BaseModel
from decimal import Decimal
import uuid
import os

router = APIRouter(prefix="/pos", tags=["pos"])


class CartItem(BaseModel):
    product_id: uuid.UUID | None = None
    name: str | None = None
    quantity: int = 1
    unit_price: float | None = None
    discount_percent: float = 0


class PaymentInput(BaseModel):
    method: str  # cash, card, cheque
    amount: Decimal


class CreateTransactionRequest(BaseModel):
    items: list[CartItem]
    payments: list[PaymentInput]
    client_id: uuid.UUID | None = None


class OpenDrawerRequest(BaseModel):
    opening_amount: Decimal


class CloseDrawerRequest(BaseModel):
    closing_amount: Decimal


@router.post("/transactions")
async def create_transaction(
    request: CreateTransactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new sale transaction with payments."""
    pos_service = PosService(db)
    fiscal_service = FiscalService(db)

    transaction = await pos_service.create_transaction(
        user_id=current_user.id,
        items=request.items,
        payments=request.payments,
        client_id=request.client_id,
    )

    # Generate fiscal hash chain
    await fiscal_service.sign_transaction(transaction)
    await db.commit()

    return {
        "id": str(transaction.id),
        "transaction_id": str(transaction.id),
        "transaction_number": transaction.transaction_number,
        "total_ttc": float(transaction.total_ttc),
    }


@router.get("/transactions")
async def list_transactions(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recent transactions."""
    pos_service = PosService(db)
    transactions = await pos_service.list_transactions(skip=skip, limit=limit)
    return transactions


@router.get("/transactions/{transaction_id}")
async def get_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get transaction details."""
    pos_service = PosService(db)
    transaction = await pos_service.get_transaction(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.post("/drawer/open")
async def open_drawer(
    request: OpenDrawerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Open cash drawer for the day."""
    pos_service = PosService(db)
    drawer = await pos_service.open_drawer(current_user.id, request.opening_amount)
    await db.commit()
    return {
        "drawer_id": str(drawer.id),
        "opening_amount": float(drawer.opening_amount),
    }


@router.post("/drawer/close")
async def close_drawer(
    request: CloseDrawerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Close cash drawer and generate Z report."""
    pos_service = PosService(db)
    fiscal_service = FiscalService(db)

    drawer = await pos_service.close_drawer(current_user.id, request.closing_amount)
    z_report = await fiscal_service.generate_z_report(drawer, current_user.id)
    await db.commit()

    return {
        "drawer_id": str(drawer.id),
        "z_report_number": z_report.report_number,
        "total_sales": float(z_report.total_sales),
        "total_refunds": float(z_report.total_refunds),
        "total_net": float(z_report.total_net),
        "transaction_count": z_report.transaction_count,
        "difference": float(drawer.closing_amount - drawer.expected_amount)
        if drawer.expected_amount
        else 0,
    }


@router.get("/drawer/current")
async def get_current_drawer(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the currently open drawer."""
    pos_service = PosService(db)
    drawer = await pos_service.get_open_drawer()
    if not drawer:
        return {"open": False}
    return {
        "open": True,
        "drawer_id": str(drawer.id),
        "opening_amount": float(drawer.opening_amount),
    }


@router.get("/z-reports")
async def list_z_reports(
    skip: int = 0,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List Z reports."""
    fiscal_service = FiscalService(db)
    reports = await fiscal_service.list_z_reports(skip=skip, limit=limit)
    return reports


class CBInitiateRequest(BaseModel):
    amount: float
    description: str = "Vente Vintiz"


class ResendRequest(BaseModel):
    channel: str  # 'email' or 'sms'


# ---------------------------------------------------------------------------
# CB / SumUp endpoints
# ---------------------------------------------------------------------------

@router.post("/payments/cb/initiate")
async def initiate_cb_payment(
    request: CBInitiateRequest,
    current_user: User = Depends(get_current_user),
):
    """Initiate a SumUp card checkout. Returns checkout_id for polling."""
    from app.services.sumup_service import SumUpService
    svc = SumUpService()
    result = await svc.create_checkout(
        amount=request.amount,
        description=request.description,
    )
    return result


@router.get("/payments/cb/{checkout_id}/status")
async def get_cb_payment_status(
    checkout_id: str,
    current_user: User = Depends(get_current_user),
):
    """Poll the status of a SumUp checkout."""
    from app.services.sumup_service import SumUpService
    svc = SumUpService()
    result = await svc.get_checkout_status(checkout_id)
    return result


@router.delete("/payments/cb/{checkout_id}")
async def cancel_cb_payment(
    checkout_id: str,
    current_user: User = Depends(get_current_user),
):
    """Cancel a pending SumUp checkout."""
    from app.services.sumup_service import SumUpService
    svc = SumUpService()
    ok = await svc.cancel_checkout(checkout_id)
    return {"cancelled": ok}


@router.post("/transactions/{transaction_id}/resend")
async def resend_transaction(
    transaction_id: uuid.UUID,
    request: ResendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resend a transaction receipt by email or SMS."""
    pos_service = PosService(db)
    transaction = await pos_service.get_transaction(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction introuvable")

    client = transaction.get("client")
    if not client:
        raise HTTPException(status_code=400, detail="Aucun client associe a cette transaction")

    ticket_num = transaction["transaction_number"]
    total = transaction["total_ttc"]
    items_text = "\n".join(
        f"  - {item['name']} x{item['quantity']} : {item['unit_price']:.2f} EUR"
        for item in transaction.get("items", [])
    )

    if request.channel == "email":
        if not client.get("email"):
            raise HTTPException(status_code=400, detail="Ce client n'a pas d'adresse email")
        smtp_host = os.getenv("SMTP_HOST", "")
        if smtp_host:
            try:
                import smtplib
                from email.mime.text import MIMEText
                msg = MIMEText(
                    f"Bonjour {client['first_name']},\n\n"
                    f"Voici le recu de votre achat chez Vintiz.\n\n"
                    f"Ticket #{ticket_num}\n"
                    f"Articles :\n{items_text}\n\n"
                    f"Total TTC : {total:.2f} EUR\n\n"
                    f"Merci de votre visite !\nVintiz — Boutique de seconde main premium",
                    "plain",
                    "utf-8",
                )
                msg["Subject"] = f"Votre recu Vintiz #{ticket_num}"
                msg["From"] = os.getenv("SMTP_USER", "noreply@vintiz.fr")
                msg["To"] = client["email"]
                with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587"))) as server:
                    server.starttls()
                    server.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASSWORD", ""))
                    server.send_message(msg)
                return {"success": True, "message": f"Email envoye a {client['email']}"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erreur envoi email : {e}")
        else:
            # Simulate
            return {"success": True, "message": f"[SIMULE] Email envoye a {client['email']}"}

    elif request.channel == "sms":
        if not client.get("phone"):
            raise HTTPException(status_code=400, detail="Ce client n'a pas de numero de telephone")
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        if twilio_sid:
            try:
                from twilio.rest import Client as TwilioClient
                tw = TwilioClient(twilio_sid, os.getenv("TWILIO_AUTH_TOKEN", ""))
                tw.messages.create(
                    body=f"Vintiz - Ticket #{ticket_num} - Total {total:.2f}EUR. Merci !",
                    from_=os.getenv("TWILIO_FROM", ""),
                    to=client["phone"],
                )
                return {"success": True, "message": f"SMS envoye au {client['phone']}"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erreur envoi SMS : {e}")
        else:
            return {"success": True, "message": f"[SIMULE] SMS envoye au {client['phone']}"}
    else:
        raise HTTPException(status_code=400, detail="Canal invalide (email ou sms)")


@router.get("/transactions/{transaction_id}/receipt")
async def get_transaction_receipt(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and return receipt text for a transaction."""
    from sqlalchemy import select
    from app.models.pos import Transaction
    from app.services.receipt import ReceiptService

    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    receipt_service = ReceiptService()
    receipt_text = receipt_service.generate_receipt_text(transaction)

    return {
        "receipt_text": receipt_text,
        "transaction_id": str(transaction_id),
    }
