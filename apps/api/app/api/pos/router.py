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

router = APIRouter(prefix="/pos", tags=["pos"])


class CartItem(BaseModel):
    product_id: uuid.UUID
    quantity: int = 1


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
