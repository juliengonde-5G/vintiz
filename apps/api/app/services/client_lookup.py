"""Client lookup helpers used across multiple routers.

Centralizes email normalization and validation so every call site behaves
consistently.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client


def normalize_email(email: str) -> str:
    """Strip whitespace and lowercase an email address."""
    return email.strip().lower()


def validate_email_format(email: str) -> None:
    """Raise HTTP 400 if the email is obviously malformed."""
    if "@" not in email or "." not in email.split("@", 1)[-1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )


async def get_client_by_email(
    db: AsyncSession,
    email: str,
    *,
    raise_if_missing: bool = False,
) -> Client | None:
    """Normalize, validate, and look up a client by email.

    Args:
        db: Database session.
        email: Raw email address (will be normalized).
        raise_if_missing: When True, raises HTTP 404 if the client is not found.

    Returns:
        The ``Client`` ORM object, or ``None`` if not found (and
        ``raise_if_missing`` is False).
    """
    cleaned = normalize_email(email)
    validate_email_format(cleaned)
    result = await db.execute(select(Client).where(Client.email == cleaned))
    client = result.scalar_one_or_none()
    if client is None and raise_if_missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with email '{cleaned}' not found",
        )
    return client


async def get_client_by_id(
    db: AsyncSession,
    client_id: uuid.UUID,
    *,
    raise_if_missing: bool = True,
) -> Client | None:
    """Fetch a client by UUID. Raises HTTP 404 by default if not found."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None and raise_if_missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found",
        )
    return client
