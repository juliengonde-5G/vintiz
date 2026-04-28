"""Magic-link OTP for the public client space (PR1).

Replaces ``?email=`` lookups across ``/api/crm/account/*``. Flow:

1. ``issue(email, ip)`` — store a 6-digit code (bcrypt-hashed) with 10
   min TTL, send it via ``email_gateway.send_email``. Rate-limited per
   email (3/h) and per IP (30/h) to stop enumeration + Brevo abuse.
2. ``verify(email, code, ip)`` — load the latest unused row, check
   expiry + attempts, compare hash, return a 1h client JWT (role=client,
   sub=<client_id>).

Constant-time responses: ``issue`` returns success even on rate-limit so
attackers can't infer "this email exists". ``verify`` only returns
"invalid_or_expired" — never "no client".
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.auth import MagicLinkToken
from app.models.client import Client, LoyaltyAccount
from app.services.email_gateway import EmailDeliveryError, EmailMessage, send_email


logger = logging.getLogger("vintiz.magic_link")


CODE_TTL_MINUTES = 10
MAX_ATTEMPTS = 5
RATE_LIMIT_EMAIL_PER_HOUR = 3
RATE_LIMIT_IP_PER_HOUR = 30
JWT_TTL_MINUTES = 60


class MagicLinkError(RuntimeError):
    """Domain error for verify(); routers map to 401/429."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass
class VerifyResult:
    access_token: str
    expires_in: int
    client_id: str
    membership_number: str | None


def _hash_code(code: str, salt: bytes | None = None) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), salt or bcrypt.gensalt()).decode("utf-8")


def _check_code(code: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(code.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _opaque_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


async def _count_recent(
    db: AsyncSession, *, email: str | None = None, ip: str | None = None
) -> int:
    cutoff = _now() - timedelta(hours=1)
    stmt = select(func.count(MagicLinkToken.id)).where(
        MagicLinkToken.created_at >= cutoff
    )
    if email is not None:
        stmt = stmt.where(MagicLinkToken.email == email)
    if ip is not None:
        stmt = stmt.where(MagicLinkToken.ip == ip)
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def issue(
    db: AsyncSession,
    email: str,
    ip: str | None = None,
) -> None:
    """Mint a 6-digit code, store + send it. Always succeeds (no enumeration)."""
    norm_email = _normalize_email(email)
    if not norm_email or "@" not in norm_email:
        # Silent no-op: never tell the caller why we didn't send.
        logger.info("magic_link: rejecting malformed email")
        return

    by_email = await _count_recent(db, email=norm_email)
    by_ip = await _count_recent(db, ip=ip) if ip else 0
    if by_email >= RATE_LIMIT_EMAIL_PER_HOUR or by_ip >= RATE_LIMIT_IP_PER_HOUR:
        logger.warning(
            "magic_link: rate-limited email=%s ip=%s by_email=%d by_ip=%d",
            norm_email, ip, by_email, by_ip,
        )
        return

    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = _hash_code(code)
    token = _opaque_token()
    token_hash = _hash_token(token)
    expires_at = _now() + timedelta(minutes=CODE_TTL_MINUTES)

    db.add(
        MagicLinkToken(
            email=norm_email,
            token_hash=token_hash,
            code_hash=code_hash,
            expires_at=expires_at,
            ip=ip,
        )
    )
    await db.flush()

    subject = f"Code de connexion Vintiz : {code}"
    html = (
        "<p>Bonjour,</p>"
        f"<p>Votre code de connexion à votre espace Vintiz est&nbsp;: <strong style='font-size:24px'>{code}</strong></p>"
        f"<p>Ce code est valable {CODE_TTL_MINUTES} minutes. Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.</p>"
        "<p>À très vite en boutique,<br/>L'équipe Vintiz Vernon</p>"
    )
    text = (
        f"Code de connexion Vintiz : {code}\n"
        f"Valable {CODE_TTL_MINUTES} minutes.\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n"
    )
    try:
        send_email(
            EmailMessage(
                to=norm_email,
                subject=subject,
                html=html,
                text=text,
            )
        )
        # Sim mode also logs the code at INFO level via _simulate; that's
        # how tests pull it back. Re-log here for clarity.
        logger.info("magic_link: code issued for email=%s (sim=safe to log)", norm_email)
    except EmailDeliveryError as exc:
        # Email backend up but call failed; we still keep the row so a
        # retry from the user can succeed if backend recovers.
        logger.warning("magic_link: email delivery failed: %s", exc)


async def verify(
    db: AsyncSession,
    email: str,
    code: str,
    ip: str | None = None,
) -> VerifyResult:
    """Consume a code, return a short-lived JWT + client info.

    Raises ``MagicLinkError`` (.code in {invalid_or_expired, too_many_attempts}).
    """
    norm_email = _normalize_email(email)
    code = (code or "").strip()
    if not norm_email or not code:
        raise MagicLinkError("invalid_or_expired")

    row = await db.execute(
        select(MagicLinkToken)
        .where(
            MagicLinkToken.email == norm_email,
            MagicLinkToken.used_at.is_(None),
            MagicLinkToken.expires_at > _now(),
        )
        .order_by(MagicLinkToken.created_at.desc())
        .limit(1)
    )
    token: Optional[MagicLinkToken] = row.scalar_one_or_none()
    if token is None:
        raise MagicLinkError("invalid_or_expired")

    if token.attempts >= MAX_ATTEMPTS:
        raise MagicLinkError("too_many_attempts")

    if not _check_code(code, token.code_hash):
        token.attempts += 1
        await db.flush()
        # Surface a generic error: don't leak "wrong code" vs "expired".
        if token.attempts >= MAX_ATTEMPTS:
            raise MagicLinkError("too_many_attempts")
        raise MagicLinkError("invalid_or_expired")

    token.used_at = _now()
    await db.flush()

    # Resolve client by email (may be None for clients who haven't been
    # created yet — most flows want to issue a JWT only when a Client row
    # exists, so we 401 in that case).
    client_row = await db.execute(
        select(Client).where(Client.email == norm_email)
    )
    client: Client | None = client_row.scalar_one_or_none()
    if client is None:
        # Don't leak: keep error generic, but log so ops can see why no JWT.
        logger.info("magic_link: verified code but no Client for email=%s", norm_email)
        raise MagicLinkError("invalid_or_expired")

    membership = None
    loyalty_row = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.client_id == client.id)
    )
    loyalty = loyalty_row.scalar_one_or_none()
    if loyalty is not None:
        membership = loyalty.membership_number

    jwt = create_access_token(
        data={"sub": str(client.id), "role": "client", "email": norm_email},
        expires_delta=timedelta(minutes=JWT_TTL_MINUTES),
    )
    return VerifyResult(
        access_token=jwt,
        expires_in=JWT_TTL_MINUTES * 60,
        client_id=str(client.id),
        membership_number=membership,
    )
