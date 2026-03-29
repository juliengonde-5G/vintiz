import uuid

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
