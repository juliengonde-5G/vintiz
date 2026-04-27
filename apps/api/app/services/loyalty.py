"""Loyalty programme business logic.

Handles account activation, point earning/redemption, and summary queries.
Raises domain exceptions — never HTTPException.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientBalance, InvalidOperation, ResourceNotFound
from app.models.client import Client, LoyaltyAccount, LoyaltyTransaction, LoyaltyTxType


class LoyaltyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def activate(self, client_id: uuid.UUID) -> LoyaltyAccount:
        """Create a new loyalty account for the client."""
        client_row = await self.db.execute(
            select(Client).where(Client.id == client_id)
        )
        client = client_row.scalar_one_or_none()
        if client is None:
            raise ResourceNotFound("Client", client_id)
        if client.loyalty_account:
            raise InvalidOperation("Loyalty account already active for this client")

        account = LoyaltyAccount(client_id=client.id, points=0, tier="bronze")
        self.db.add(account)
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def get_account(self, client_id: uuid.UUID) -> LoyaltyAccount:
        """Return the loyalty account for a client, or raise ResourceNotFound."""
        row = await self.db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.client_id == client_id)
        )
        account = row.scalar_one_or_none()
        if account is None:
            raise ResourceNotFound("LoyaltyAccount", client_id)
        return account

    async def earn(
        self, client_id: uuid.UUID, points: int, description: str
    ) -> LoyaltyAccount:
        """Add points to a client's account. Creates a ledger row."""
        account = await self.get_account(client_id)
        account.points += points
        self.db.add(LoyaltyTransaction(
            account_id=account.id,
            tx_type=LoyaltyTxType.earn,
            points=points,
            description=description,
        ))
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def redeem(
        self, client_id: uuid.UUID, points: int, description: str
    ) -> LoyaltyAccount:
        """Deduct points from a client's account. Raises if balance is insufficient."""
        account = await self.get_account(client_id)
        if account.points < points:
            raise InsufficientBalance(
                f"Loyalty: available {account.points}, requested {points}"
            )
        account.points -= points
        self.db.add(LoyaltyTransaction(
            account_id=account.id,
            tx_type=LoyaltyTxType.redeem,
            points=points,
            description=description,
        ))
        await self.db.flush()
        await self.db.refresh(account)
        return account

    def serialize(self, account: LoyaltyAccount) -> dict:
        return {
            "account_id": str(account.id),
            "client_id": str(account.client_id),
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
