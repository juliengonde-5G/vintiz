"""Membership number helpers (PR1).

Format: ``V`` + 6 digits (e.g. ``V482931``). Stored verbatim on
``LoyaltyAccount.membership_number`` (unique). The format is human-dictable
over the phone and short enough for the bottom of a receipt or a Wallet
card. ~1180 cards before birthday-paradox collision in 1M space — the
loop retries on collision and the unique constraint is the final safety
net.
"""

from __future__ import annotations

import re
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import LoyaltyAccount, Client


_PATTERN = re.compile(r"^V\d{6}$")


def is_membership_number(value: str | None) -> bool:
    if not value:
        return False
    return bool(_PATTERN.match(value.strip()))


async def generate_membership_number(db: AsyncSession, max_attempts: int = 8) -> str:
    """Pick a fresh ``V######`` not yet used in ``loyalty_accounts``.

    Retries on collision; raises ``RuntimeError`` after ``max_attempts``
    so callers fail loudly rather than silently re-using a number.
    """
    for _ in range(max_attempts):
        candidate = "V" + f"{secrets.randbelow(1_000_000):06d}"
        row = await db.execute(
            select(LoyaltyAccount.id).where(
                LoyaltyAccount.membership_number == candidate
            )
        )
        if row.scalar_one_or_none() is None:
            return candidate
    raise RuntimeError("Could not generate a unique membership number after retries")


async def lookup_by_membership_number(
    db: AsyncSession, membership_number: str
) -> Client | None:
    """Return the Client owning a given membership number, or None."""
    if not is_membership_number(membership_number):
        return None
    row = await db.execute(
        select(Client)
        .join(LoyaltyAccount, LoyaltyAccount.client_id == Client.id)
        .where(LoyaltyAccount.membership_number == membership_number.strip())
    )
    return row.scalar_one_or_none()
