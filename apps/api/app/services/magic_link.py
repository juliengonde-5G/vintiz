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
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.auth import MagicLinkToken
from app.models.client import Client, LoyaltyAccount
from app.services.email_gateway import EmailDeliveryError, EmailMessage, send_email


logger = logging.getLogger("vintiz.magic_link")


CODE_TTL_MINUTES = 10
MAX_ATTEMPTS = 5
RATE_LIMIT_EMAIL_PER_HOUR = 6
RATE_LIMIT_IP_PER_HOUR = 30
JWT_TTL_MINUTES = 60

# Phone-number heuristic for SMS routing. The frontend can pass either an
# email or a phone in the same `email` field; we detect digits-only with an
# optional leading `+` and at least 8 digits (loose by design — full E.164
# validation belongs to Twilio).
_PHONE_RE = __import__("re").compile(r"^\+?\d[\d\s.-]{7,}$")


def _is_phone(value: str) -> bool:
    cleaned = value.strip()
    if "@" in cleaned:
        return False
    return bool(_PHONE_RE.match(cleaned))


def _normalize_phone(value: str) -> str:
    cleaned = value.strip().replace(" ", "").replace(".", "").replace("-", "")
    return cleaned


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
    email: str | None = None


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
) -> dict:
    """Mint a 6-digit code, store + send it. Always succeeds (no enumeration).

    Accepts either an email OR a phone number in the ``email`` argument: when
    the value matches a phone pattern we route through the SMS gateway
    (Twilio when configured, simulation otherwise). The DB row keeps the
    normalized identifier in the ``email`` column so verify() works the same
    way regardless of channel.

    Returns a small status dict ``{"delivery_mode": "sent"|"simulated"|"failed"|"skipped"}``
    so the admin probe can surface the real backend state without leaking to
    the public endpoint (which still answers 204).
    """
    is_phone = _is_phone(email or "")
    if is_phone:
        norm_email = _normalize_phone(email)
        if not norm_email:
            return {"delivery_mode": "skipped", "reason": "malformed_phone"}
    else:
        norm_email = _normalize_email(email)
        if not norm_email or "@" not in norm_email:
            # Silent no-op: never tell the caller why we didn't send.
            logger.info("magic_link: rejecting malformed email")
            return {"delivery_mode": "skipped", "reason": "malformed_email"}

    by_email = await _count_recent(db, email=norm_email)
    by_ip = await _count_recent(db, ip=ip) if ip else 0
    if by_email >= RATE_LIMIT_EMAIL_PER_HOUR or by_ip >= RATE_LIMIT_IP_PER_HOUR:
        logger.warning(
            "magic_link: rate-limited email=%s ip=%s by_email=%d by_ip=%d",
            norm_email, ip, by_email, by_ip,
        )
        return {"delivery_mode": "skipped", "reason": "rate_limited"}

    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = _hash_code(code)
    token = _opaque_token()
    token_hash = _hash_token(token)
    expires_at = _now() + timedelta(minutes=CODE_TTL_MINUTES)

    # Invalidate any still-valid OTP for this email so only the freshest
    # code is accepted. Without this, two issue() calls within 10 min leave
    # both rows valid; if a user types the older code by mistake the
    # mismatch increments the *newest* token's attempts counter and they
    # hit "too_many_attempts" on a code they never used.
    await db.execute(
        update(MagicLinkToken)
        .where(
            MagicLinkToken.email == norm_email,
            MagicLinkToken.used_at.is_(None),
        )
        .values(used_at=_now())
    )

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

    # Clickable one-time link (passwordless alternative to typing the code).
    site_url = (
        os.getenv("PUBLIC_SITE_URL")
        or os.getenv("NEXT_PUBLIC_SITE_URL")
        or "https://vintiz.fr"
    ).rstrip("/")
    login_link = f"{site_url}/account/login?token={token}"

    subject = f"Code de connexion Vintiz : {code}"
    html = (
        "<p>Bonjour,</p>"
        "<p>Connectez-vous à votre espace Vintiz en un clic&nbsp;:</p>"
        f"<p><a href='{login_link}' "
        "style='display:inline-block;background:#0B7A6A;color:#fff;"
        "padding:12px 24px;border-radius:9999px;text-decoration:none;"
        "font-weight:600'>Me connecter</a></p>"
        "<p>Ou saisissez ce code&nbsp;: "
        f"<strong style='font-size:24px'>{code}</strong></p>"
        f"<p>Ce lien et ce code sont valables {CODE_TTL_MINUTES} minutes. "
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.</p>"
        "<p>À très vite en boutique,<br/>L'équipe Vintiz Vernon</p>"
    )
    text = (
        "Connectez-vous à votre espace Vintiz en un clic :\n"
        f"{login_link}\n\n"
        f"Ou saisissez ce code : {code}\n"
        f"Valable {CODE_TTL_MINUTES} minutes.\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n"
    )
    delivery_mode = "failed"
    backend = "unknown"
    try:
        if is_phone:
            from app.services.sms_gateway import (
                SMSDeliveryError,
                SMSMessage,
                send_sms,
            )

            sms_body = (
                f"Vintiz : votre code de connexion est {code}. "
                f"Valable {CODE_TTL_MINUTES} min."
            )
            try:
                sms_result = send_sms(SMSMessage(to=norm_email, body=sms_body))
                backend = sms_result.backend
                if sms_result.status == "sent":
                    delivery_mode = "sent"
                elif sms_result.status == "simulated":
                    delivery_mode = "simulated"
                    if os.getenv("ENVIRONMENT", "").lower() == "production":
                        logger.warning(
                            "magic_link: PRODUCTION using SMS simulation — Twilio not configured"
                        )
                else:
                    delivery_mode = "failed"
            except SMSDeliveryError as exc:
                logger.warning("magic_link: sms delivery failed: %s", exc)
                delivery_mode = "failed"
        else:
            result = send_email(
                EmailMessage(
                    to=norm_email,
                    subject=subject,
                    html=html,
                    text=text,
                )
            )
            backend = result.backend
            if result.status == "sent":
                delivery_mode = "sent"
            elif result.status == "simulated":
                delivery_mode = "simulated"
                # In production, simulation = misconfigured email gateway.
                if os.getenv("ENVIRONMENT", "").lower() == "production":
                    logger.warning(
                        "magic_link: PRODUCTION using simulation backend — Brevo/SMTP not configured"
                    )
            else:
                delivery_mode = "failed"
        logger.info(
            "magic_link: code issued for id=%s channel=%s backend=%s delivery=%s",
            norm_email, "sms" if is_phone else "email", backend, delivery_mode,
        )
    except EmailDeliveryError as exc:
        logger.warning("magic_link: email delivery failed: %s", exc)
        delivery_mode = "failed"

    return {"delivery_mode": delivery_mode, "backend": backend, "channel": "sms" if is_phone else "email"}


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

    # Lock the row so two concurrent verify() requests cannot both increment
    # the attempts counter from the same starting value (race that lets
    # an attacker brute-force OTP in parallel under MAX_ATTEMPTS). On SQLite
    # (tests) FOR UPDATE is a no-op — single-writer model is enough there.
    dialect = db.bind.dialect.name if db.bind else "postgresql"
    stmt = (
        select(MagicLinkToken)
        .where(
            MagicLinkToken.email == norm_email,
            MagicLinkToken.used_at.is_(None),
            MagicLinkToken.expires_at > _now(),
        )
        .order_by(MagicLinkToken.created_at.desc())
        .limit(1)
    )
    if dialect == "postgresql":
        stmt = stmt.with_for_update()
    row = await db.execute(stmt)
    token: Optional[MagicLinkToken] = row.scalar_one_or_none()
    if token is None:
        raise MagicLinkError("invalid_or_expired")

    if token.attempts >= MAX_ATTEMPTS:
        raise MagicLinkError("too_many_attempts")

    if not _check_code(code, token.code_hash):
        # Atomic conditional increment so a concurrent miss can't slip
        # through the MAX_ATTEMPTS gate by reading a stale value.
        result = await db.execute(
            update(MagicLinkToken)
            .where(
                MagicLinkToken.id == token.id,
                MagicLinkToken.attempts < MAX_ATTEMPTS,
            )
            .values(attempts=MagicLinkToken.attempts + 1)
        )
        await db.flush()
        # Reload to know the new attempt count after the conditional update.
        await db.refresh(token)
        if result.rowcount == 0 or token.attempts >= MAX_ATTEMPTS:
            raise MagicLinkError("too_many_attempts")
        raise MagicLinkError("invalid_or_expired")

    token.used_at = _now()
    await db.flush()
    return await _issue_jwt_for_email(db, norm_email)


async def verify_by_token(
    db: AsyncSession,
    token: str,
    ip: str | None = None,
) -> VerifyResult:
    """Passwordless login via the one-time link token (no code to type).

    The issue() flow already stores an opaque ``token`` (hashed). The login
    email embeds it as ``/account/login?token=…``; clicking it logs the
    customer in directly. Same single-use + TTL guarantees as the OTP path.

    Raises ``MagicLinkError("invalid_or_expired")``.
    """
    token = (token or "").strip()
    if not token:
        raise MagicLinkError("invalid_or_expired")
    token_hash = _hash_token(token)
    row = await db.execute(
        select(MagicLinkToken)
        .where(
            MagicLinkToken.token_hash == token_hash,
            MagicLinkToken.used_at.is_(None),
            MagicLinkToken.expires_at > _now(),
        )
        .order_by(MagicLinkToken.created_at.desc())
        .limit(1)
    )
    mlt: Optional[MagicLinkToken] = row.scalar_one_or_none()
    if mlt is None:
        raise MagicLinkError("invalid_or_expired")
    mlt.used_at = _now()
    await db.flush()
    return await _issue_jwt_for_email(db, mlt.email)


async def _issue_jwt_for_email(db: AsyncSession, norm_email: str) -> VerifyResult:
    """Resolve the client by (already-normalised) email and mint a 1h JWT.

    Shared tail of :func:`verify` and :func:`verify_by_token`. 401-style error
    (generic) when no Client row exists for the verified identifier.
    """
    client_row = await db.execute(
        select(Client).where(Client.email == norm_email)
    )
    client: Client | None = client_row.scalar_one_or_none()
    if client is None:
        logger.info("magic_link: verified but no Client for id=%s", norm_email)
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
        email=client.email,
    )
