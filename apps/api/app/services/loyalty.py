"""Loyalty programme business logic.

Handles account activation, point earning/redemption, subscription, and
summary queries. Raises domain exceptions — never HTTPException.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientBalance, InvalidOperation, ResourceNotFound
from app.models.client import (
    Client,
    Consent,
    ConsentPurpose,
    LoyaltyAccount,
    LoyaltyTransaction,
    LoyaltyTxType,
)
from app.services.membership_id import generate_membership_number


# 24 months — points expire after this many days of inactivity (PR1 / Q6).
LOYALTY_EXPIRY_DAYS = 730

# Consent policy version stamped onto Consent rows created at POS subscription.
CONSENT_POLICY_VERSION = "v2-2026-04"


class LoyaltyDuplicateError(RuntimeError):
    """Raised by subscribe() when an email already has a loyalty account.

    Carries enough info for the POS UI to propose a "fusionner ?" dialog.
    """

    def __init__(self, *, client_id: uuid.UUID, membership_number: str) -> None:
        super().__init__("duplicate_email")
        self.client_id = client_id
        self.membership_number = membership_number


def _now() -> datetime:
    return datetime.now(timezone.utc)


def loyalty_active(client: Client | None) -> bool:
    """True iff the client holds an active loyalty account.

    Active ⇔ ``loyalty_account`` exists AND ``loyalty_expires_at`` is in
    the future (or absent — backwards compat for accounts created before
    PR1 backfill). Used as the gate for Personal Shopper in PR2.

    SQLite drops tzinfo on DateTime columns; we treat naive datetimes
    as UTC so tests using sqlite+aiosqlite work the same as PostgreSQL.
    """
    if client is None or client.loyalty_account is None:
        return False
    expires = getattr(client, "loyalty_expires_at", None)
    if expires is None:
        return True
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires > _now()


class LoyaltyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def activate(self, client_id: uuid.UUID) -> LoyaltyAccount:
        """Create a new loyalty account for the client.

        Use ``subscribe`` for the full POS enrolment flow (with anti-duplicate
        + consent ledger). ``activate`` is the lower-level building block.
        """
        client_row = await self.db.execute(
            select(Client).where(Client.id == client_id)
        )
        client = client_row.scalar_one_or_none()
        if client is None:
            raise ResourceNotFound("Client", client_id)
        if client.loyalty_account:
            raise InvalidOperation("Loyalty account already active for this client")

        membership = await generate_membership_number(self.db)
        account = LoyaltyAccount(
            client_id=client.id, points=0, membership_number=membership
        )
        self.db.add(account)
        # Mark subscription window so loyalty_active() returns True.
        client.loyalty_subscribed_at = _now()
        client.loyalty_expires_at = _now() + timedelta(days=LOYALTY_EXPIRY_DAYS)
        if not client.loyalty_subscription_mode:
            client.loyalty_subscription_mode = "free"
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def get_account(self, client_id: uuid.UUID) -> LoyaltyAccount:
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
            "membership_number": account.membership_number,
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


async def subscribe(
    db: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    email: str,
    postal_code: str | None,
    mode: str,
    optin_newsletter: bool = False,
    optin_profiling: bool = False,
    source: str = "pos_subscription",
    user_id: uuid.UUID | None = None,
) -> tuple[Client, LoyaltyAccount]:
    """Enrol a client in the loyalty programme.

    Anti-duplicate: if a client with that email already has a loyalty
    account, raise ``LoyaltyDuplicateError`` with the existing
    membership number — the POS UI surfaces a "fusionner ?" modal.

    Side-effects:
    - create or attach the LoyaltyAccount (with new V###### number),
    - set ``loyalty_subscribed_at`` / ``loyalty_expires_at`` (24mo
      rolling),
    - record RGPD Consent rows for newsletter + profiling per the
      checked boxes (text version stamped),
    - optionally update the client's name/postal_code (notes) if absent.
    """
    norm_email = (email or "").strip().lower()
    if not norm_email or "@" not in norm_email:
        raise InvalidOperation("Email obligatoire pour la souscription")
    if mode not in ("free", "paid", "first_purchase"):
        raise InvalidOperation(f"Mode souscription invalide: {mode}")

    existing_row = await db.execute(select(Client).where(Client.email == norm_email))
    existing: Client | None = existing_row.scalar_one_or_none()
    if existing is not None and existing.loyalty_account is not None:
        raise LoyaltyDuplicateError(
            client_id=existing.id,
            membership_number=existing.loyalty_account.membership_number,
        )

    if existing is None:
        client = Client(
            first_name=first_name.strip() or "Client",
            last_name=last_name.strip() or "",
            email=norm_email,
            email_optin=optin_newsletter,
        )
        if postal_code:
            client.notes = f"CP: {postal_code.strip()}"
        db.add(client)
        await db.flush()
    else:
        client = existing
        # Update name fields if blank, but never overwrite existing data.
        if not client.first_name and first_name:
            client.first_name = first_name.strip()
        if not client.last_name and last_name:
            client.last_name = last_name.strip()
        if optin_newsletter:
            client.email_optin = True
        if postal_code and (not client.notes or "CP:" not in client.notes):
            client.notes = ((client.notes or "") + f"\nCP: {postal_code.strip()}").strip()

    membership = await generate_membership_number(db)
    account = LoyaltyAccount(client_id=client.id, points=0, membership_number=membership)
    db.add(account)

    now = _now()
    client.loyalty_subscribed_at = now
    client.loyalty_expires_at = now + timedelta(days=LOYALTY_EXPIRY_DAYS)
    client.loyalty_subscription_mode = mode

    # RGPD consent ledger — append-only.
    consents: Iterable[tuple[ConsentPurpose, bool]] = (
        (ConsentPurpose.email_marketing, optin_newsletter),
        (ConsentPurpose.profiling, optin_profiling),
    )
    for purpose, granted in consents:
        db.add(
            Consent(
                client_id=client.id,
                purpose=purpose,
                granted=granted,
                policy_version=CONSENT_POLICY_VERSION,
                source=source,
                recorded_by_user_id=user_id,
            )
        )

    await db.flush()
    await db.refresh(client)
    await db.refresh(account)
    return client, account
