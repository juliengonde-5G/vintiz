"""POS cashier identification via 4-digit PIN.

A PIN is bcrypt-hashed in `users.pin_hash`. Verifying a PIN at the till
requires iterating active users with a stored PIN — bcrypt's random salt
prevents direct lookup. This is acceptable for a single-shop team (<50
users) and avoids weakening the hash by using a deterministic scheme.
"""

import re

import bcrypt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

PIN_LENGTH = 4
_PIN_PATTERN = re.compile(r"^\d{4}$")


def _validate_pin_format(pin: str) -> None:
    if not _PIN_PATTERN.match(pin or ""):
        raise HTTPException(
            status_code=400,
            detail=f"PIN must be exactly {PIN_LENGTH} digits",
        )


class CashierService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def set_pin(self, user: User, pin: str) -> None:
        """Hash and store a PIN for a user."""
        _validate_pin_format(pin)
        user.pin_hash = bcrypt.hashpw(
            pin.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        await self.db.flush()

    async def clear_pin(self, user: User) -> None:
        user.pin_hash = None
        await self.db.flush()

    async def authenticate_pin(self, pin: str) -> User:
        """Find the active user matching the supplied PIN.

        Iterates users with a stored PIN. Raises 401 on no match,
        400 on bad input format. Does not reveal whether a candidate
        existed (constant-time-ish: every active user with a PIN is checked).
        """
        _validate_pin_format(pin)
        result = await self.db.execute(
            select(User).where(
                User.is_active.is_(True),
                User.pin_hash.is_not(None),
            )
        )
        candidates = result.scalars().all()

        match: User | None = None
        for candidate in candidates:
            if candidate.pin_hash and bcrypt.checkpw(
                pin.encode("utf-8"), candidate.pin_hash.encode("utf-8")
            ):
                # Don't break — keep checking to maintain timing.
                match = match or candidate

        if match is None:
            raise HTTPException(status_code=401, detail="Invalid PIN")
        return match

    async def list_with_pin_status(self) -> list[dict]:
        result = await self.db.execute(
            select(User).order_by(User.username.asc())
        )
        users = result.scalars().all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role.value,
                "is_active": u.is_active,
                "has_pin": u.pin_hash is not None,
            }
            for u in users
        ]
