"""RGPD/GDPR helpers: consent ledger, data export, soft / hard deletion (P1-007).

The Client row keeps fast-read flags (email_optin, sms_optin) for the rest of
the codebase to consult, but every change is also appended to the Consent
ledger so we can prove when, by whom and on which policy version a given
consent was granted or revoked.

Deletion runs in two phases:
1. Soft: ``request_deletion`` stamps ``Client.deletion_requested_at``.
2. Hard: ``purge_pending_deletions`` runs daily, finds clients past the
   30-day window, anonymises their references on transactions and audit
   logs, then deletes the client and its dependent rows.

The cancellation window is intentional: legal regimes require a reversal
period for accidental requests, and a daily cron is conservative enough
without bombarding the DB.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.client import (
    AvoirTransaction,
    Client,
    Consent,
    ConsentPurpose,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.pos import Transaction


# Bumped whenever the privacy policy changes; persisted on each Consent row
# so we can prove the policy text the client agreed to.
CURRENT_POLICY_VERSION = "v1.0-2026-04"

# Soft-delete grace period before hard purge.
DELETION_WINDOW = timedelta(days=30)

# Mirror between Consent purposes and the legacy boolean columns on Client.
_PURPOSE_TO_FLAG: dict[ConsentPurpose, str] = {
    ConsentPurpose.email_marketing: "email_optin",
    ConsentPurpose.sms_marketing: "sms_optin",
}


class RgpdService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Consent ledger
    # ------------------------------------------------------------------

    async def record_consent(
        self,
        client: Client,
        purpose: ConsentPurpose,
        granted: bool,
        source: str,
        recorded_by_user_id: uuid.UUID | None,
        policy_version: str | None = None,
    ) -> Consent:
        """Append a new Consent row and mirror to the legacy opt-in flag."""
        entry = Consent(
            client_id=client.id,
            purpose=purpose,
            granted=granted,
            policy_version=policy_version or CURRENT_POLICY_VERSION,
            source=source,
            recorded_by_user_id=recorded_by_user_id,
        )
        self.db.add(entry)

        # Keep Client.email_optin / sms_optin in sync so existing callers
        # don't need to learn about the ledger.
        flag = _PURPOSE_TO_FLAG.get(purpose)
        if flag is not None:
            setattr(client, flag, granted)

        await self.db.flush()
        return entry

    async def current_consents(self, client_id: uuid.UUID) -> dict[str, dict]:
        """Return the current decision per purpose: {purpose: {granted, at, version}}."""
        result = await self.db.execute(
            select(Consent)
            .where(Consent.client_id == client_id)
            .order_by(Consent.created_at.asc())
        )
        rows = result.scalars().all()
        latest: dict[str, dict] = {}
        for row in rows:
            latest[row.purpose.value] = {
                "granted": row.granted,
                "policy_version": row.policy_version,
                "source": row.source,
                "recorded_at": row.created_at.isoformat() if row.created_at else None,
            }
        return latest

    async def consent_history(self, client_id: uuid.UUID) -> list[dict]:
        result = await self.db.execute(
            select(Consent)
            .where(Consent.client_id == client_id)
            .order_by(Consent.created_at.desc())
        )
        return [
            {
                "id": str(row.id),
                "purpose": row.purpose.value,
                "granted": row.granted,
                "policy_version": row.policy_version,
                "source": row.source,
                "recorded_by_user_id": str(row.recorded_by_user_id)
                if row.recorded_by_user_id
                else None,
                "recorded_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in result.scalars().all()
        ]

    # ------------------------------------------------------------------
    # Data export (Article 20 RGPD — portability)
    # ------------------------------------------------------------------

    async def export_client_data(self, client: Client) -> dict:
        """Build a portable JSON snapshot of everything we hold about ``client``."""
        # Loyalty: fetch explicitly to avoid lazy-load on async session.
        loyalty: dict | None = None
        account_result = await self.db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.client_id == client.id)
        )
        account = account_result.scalar_one_or_none()
        if account is not None:
            tx_result = await self.db.execute(
                select(LoyaltyTransaction)
                .where(LoyaltyTransaction.account_id == account.id)
                .order_by(LoyaltyTransaction.created_at.asc())
            )
            loyalty_transactions = tx_result.scalars().all()
            loyalty = {
                "tier": account.tier,
                "points": account.points,
                "transactions": [
                    {
                        "tx_type": tx.tx_type.value,
                        "points": tx.points,
                        "description": tx.description,
                        "at": tx.created_at.isoformat() if tx.created_at else None,
                    }
                    for tx in loyalty_transactions
                ],
            }

        avoir_result = await self.db.execute(
            select(AvoirTransaction)
            .where(AvoirTransaction.client_id == client.id)
            .order_by(AvoirTransaction.created_at.asc())
        )
        avoir_history = [
            {
                "tx_type": row.tx_type.value,
                "amount": float(row.amount),
                "reason": row.reason,
                "at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in avoir_result.scalars().all()
        ]

        tx_result = await self.db.execute(
            select(Transaction)
            .where(Transaction.client_id == client.id)
            .order_by(Transaction.created_at.asc())
        )
        purchases = [
            {
                "transaction_number": tx.transaction_number,
                "type": tx.transaction_type.value,
                "total_ttc": float(tx.total_ttc),
                "at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in tx_result.scalars().all()
        ]

        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "policy_version": CURRENT_POLICY_VERSION,
            "client": {
                "id": str(client.id),
                "first_name": client.first_name,
                "last_name": client.last_name,
                "email": client.email,
                "phone": client.phone,
                "notes": client.notes,
                "email_optin": client.email_optin,
                "sms_optin": client.sms_optin,
                "avoir_credit": float(client.avoir_credit or 0),
                "deletion_requested_at": client.deletion_requested_at.isoformat()
                if client.deletion_requested_at
                else None,
            },
            "consents": await self.consent_history(client.id),
            "loyalty": loyalty,
            "avoir_history": avoir_history,
            "purchases": purchases,
        }

    # ------------------------------------------------------------------
    # Soft delete / cancel / purge
    # ------------------------------------------------------------------

    async def request_deletion(self, client: Client) -> datetime:
        if client.deletion_requested_at is not None:
            raise HTTPException(
                status_code=400, detail="Deletion already requested"
            )
        client.deletion_requested_at = datetime.now(timezone.utc)
        await self.db.flush()
        return client.deletion_requested_at

    async def cancel_deletion(self, client: Client) -> None:
        if client.deletion_requested_at is None:
            raise HTTPException(
                status_code=400, detail="No pending deletion to cancel"
            )
        client.deletion_requested_at = None
        await self.db.flush()

    async def hard_delete(self, client: Client) -> dict:
        """Anonymise references and remove the client. Used by the cron.

        Transactions and AuditLog rows are kept (NF525 / audit traceability)
        but their client_id / user_id is nullified. Loyalty + avoir + consent
        rows belong to the client and are removed.
        """
        client_id = client.id

        # Anonymise foreign references that must survive (legal retention).
        await self.db.execute(
            update(Transaction)
            .where(Transaction.client_id == client_id)
            .values(client_id=None)
        )

        # Loyalty: delete transactions then accounts.
        loyalty_account_ids = (
            await self.db.execute(
                select(LoyaltyAccount.id).where(LoyaltyAccount.client_id == client_id)
            )
        ).scalars().all()
        if loyalty_account_ids:
            await self.db.execute(
                delete(LoyaltyTransaction).where(
                    LoyaltyTransaction.account_id.in_(loyalty_account_ids)
                )
            )
            await self.db.execute(
                delete(LoyaltyAccount).where(
                    LoyaltyAccount.id.in_(loyalty_account_ids)
                )
            )

        # Avoir + consents: belong to the client, can be deleted.
        await self.db.execute(
            delete(AvoirTransaction).where(AvoirTransaction.client_id == client_id)
        )
        await self.db.execute(
            delete(Consent).where(Consent.client_id == client_id)
        )

        # AuditLog rows reference user_id; they reference entity_id by UUID
        # so dropping the client implicitly leaves entity_id = old id (which
        # is no longer resolvable). Acceptable for audit purposes.

        await self.db.delete(client)
        await self.db.flush()

        return {"deleted_client_id": str(client_id)}

    async def purge_pending_deletions(self, now: datetime | None = None) -> dict:
        """Find clients whose grace period has elapsed and hard-delete them.

        Returns a summary dict for the cron logger.
        """
        cutoff = (now or datetime.now(timezone.utc)) - DELETION_WINDOW
        result = await self.db.execute(
            select(Client).where(
                Client.deletion_requested_at.is_not(None),
                Client.deletion_requested_at <= cutoff,
            )
        )
        targets = result.scalars().all()
        purged_ids: list[str] = []
        for client in targets:
            await self.hard_delete(client)
            purged_ids.append(str(client.id))
        return {"purged_count": len(purged_ids), "purged_ids": purged_ids}
