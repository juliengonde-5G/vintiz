"""Unified email gateway (P4-003).

Three back-ends in priority order:

1. **Brevo** (formerly Sendinblue) — when ``BREVO_API_KEY`` is set.
   Transactional API; we hit ``POST /v3/smtp/email`` with the message
   body. This is the production path.
2. **SMTP** — when ``SMTP_HOST`` + credentials are set. Same flow as the
   pre-P4 inline code; kept so existing prod stays working until Brevo
   is provisioned.
3. **Simulation** — no creds → log + return ``status="simulated"``. Lets
   tests, dev and the seed scripts run end-to-end without external
   dependencies.

The gateway is intentionally thin: it doesn't queue, doesn't retry on a
schedule, doesn't templatise on the server side. Templates are
generated in caller services (anniversary, new arrivals, …) and the
HTML is passed in.

Failures are logged and re-raised as :class:`EmailDeliveryError` so the
caller (cron, endpoint) can decide whether to fail loud (HTTP endpoint)
or swallow (cron job). Returning a status object instead of raising
would mix concerns: tests can assert on either.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import smtplib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


logger = logging.getLogger("vintiz.email")


class EmailDeliveryError(RuntimeError):
    """Raised when delivery is configured but fails."""


@dataclass
class EmailMessage:
    to: str
    subject: str
    html: str
    to_name: str | None = None
    text: str | None = None  # plain text fallback; computed from HTML if missing
    reply_to: str | None = None
    # Optional binary attachments. Each entry is
    # ``{"filename": str, "content": bytes, "mime": str}``.
    # Used by the Z-report mailer (PDF). Ignored by the simulation backend.
    attachments: list[dict] | None = None
    # Brevo analytics — tagging lets the manager filter delivery
    # reports in the Brevo dashboard ("ticket-resend", "anniversary",
    # "new-arrivals", "zreport", "magic-link"…). Up to 5 tags.
    tags: list[str] = field(default_factory=list)
    # Idempotency key — when set, Brevo dedupes retries with the same
    # key so a network blip doesn't double-send. We derive a stable
    # key from the message content if the caller doesn't supply one.
    idempotency_key: str | None = None


@dataclass
class EmailResult:
    status: str   # "sent" | "simulated" | "failed"
    backend: str  # "brevo" | "smtp" | "simulation"
    message_id: str | None = None
    detail: str | None = None
    sent_at: str = ""


def _strip_html(html: str) -> str:
    """Cheap HTML→text fallback. We only ship plaintext when the caller
    didn't provide one — good enough for inboxes that prefer text/plain."""
    import re

    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _from_env(key: str, default: str = "") -> str:
    """Read a config value: persisted ``app_config.json`` first, env var second.

    The persisted store mirrors the SumUp pattern — operators can edit Brevo /
    SMTP credentials from /settings > Communication without touching the
    deployment. Env vars stay as a safety net.
    """
    persisted = ""
    try:
        from app.services.app_config import get_section
        section = get_section("email")
        # Map env var → persisted key
        mapping = {
            "BREVO_API_KEY": "brevo_api_key",
            "SMTP_HOST": "smtp_host",
            "SMTP_PORT": "smtp_port",
            "SMTP_USER": "smtp_user",
            "SMTP_PASSWORD": "smtp_password",
            "SMTP_FROM": "smtp_from",
            "EMAIL_FROM_ADDRESS": "from_address",
            "EMAIL_FROM_NAME": "from_name",
        }
        pkey = mapping.get(key)
        if pkey:
            value = section.get(pkey)
            if value not in (None, ""):
                persisted = str(value)
    except Exception:
        persisted = ""
    if persisted:
        return persisted
    value = os.getenv(key)
    return value if value is not None else default


def describe_active_provider() -> dict:
    """Snapshot of which backend would be used right now (no actual send)."""
    if _from_env("BREVO_API_KEY"):
        return {"provider": "brevo", "configured": True}
    if _from_env("SMTP_HOST") and _from_env("SMTP_USER") and _from_env("SMTP_PASSWORD"):
        return {
            "provider": "smtp",
            "configured": True,
            "host": _from_env("SMTP_HOST"),
            "port": _from_env("SMTP_PORT", "587"),
        }
    return {"provider": "simulation", "configured": False}


def _stable_idempotency_key(message: EmailMessage) -> str:
    """Deterministic idempotency key derived from the message content.

    A retry of the exact same (to, subject, html) within ~24 h is treated
    by Brevo as the same message and not re-sent. Caller can override by
    setting ``message.idempotency_key`` explicitly (e.g. transaction
    UUID for ticket resends).
    """
    if message.idempotency_key:
        return message.idempotency_key
    digest = hashlib.sha256(
        f"{message.to}|{message.subject}|{message.html}".encode("utf-8")
    ).hexdigest()
    return f"vintiz-{digest[:32]}"


def _send_via_brevo(message: EmailMessage) -> EmailResult:
    """Hit Brevo's transactional endpoint. Network call wrapped in
    urllib so we keep zero runtime dependencies (no httpx/aiohttp).

    Conformity audit (developers.brevo.com 2026-05-14) :
    - ``POST https://api.brevo.com/v3/smtp/email`` ✓
    - ``api-key`` header (not Bearer) ✓
    - ``Idempotency-Key`` header — dedupes retries within Brevo's window
    - Exponential backoff on 429 (rate limit) + 5xx (transient)
    - ``tags`` field for analytics grouping in the Brevo dashboard
    """

    api_key = _from_env("BREVO_API_KEY")
    if not api_key:
        raise EmailDeliveryError("BREVO_API_KEY not set")

    sender_email = _from_env("EMAIL_FROM_ADDRESS", "noreply@vintiz.fr")
    sender_name = _from_env("EMAIL_FROM_NAME", "Vintiz Vernon")

    payload = {
        "sender": {"email": sender_email, "name": sender_name},
        "to": [
            {"email": message.to, "name": message.to_name or message.to}
        ],
        "subject": message.subject,
        "htmlContent": message.html,
        "textContent": message.text or _strip_html(message.html),
    }
    if message.reply_to:
        payload["replyTo"] = {"email": message.reply_to}
    if message.attachments:
        import base64

        payload["attachment"] = [
            {
                "name": a.get("filename", "attachment.bin"),
                "content": base64.b64encode(a.get("content") or b"").decode(
                    "ascii"
                ),
            }
            for a in message.attachments
        ]
    if message.tags:
        # Brevo caps tags at 5 per message — silently truncate, no need
        # to error on a non-critical analytics field.
        payload["tags"] = list(message.tags)[:5]

    body = json.dumps(payload).encode("utf-8")
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key,
        "Idempotency-Key": _stable_idempotency_key(message),
    }
    # Retry on 429 (Retry-After) and 5xx with exponential backoff.
    # Max 3 attempts so we don't block the request handler too long.
    max_attempts = 3
    last_exc: EmailDeliveryError | None = None
    for attempt in range(max_attempts):
        req = Request(
            "https://api.brevo.com/v3/smtp/email",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(req, timeout=15) as resp:  # noqa: S310 — domain pinned
                text = resp.read().decode("utf-8")
                data = json.loads(text) if text else {}
                return EmailResult(
                    status="sent",
                    backend="brevo",
                    message_id=data.get("messageId"),
                    sent_at=datetime.now(timezone.utc).isoformat(),
                )
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
            should_retry = exc.code == 429 or 500 <= exc.code < 600
            last_exc = EmailDeliveryError(f"Brevo {exc.code}: {detail[:200]}")
            if not should_retry or attempt == max_attempts - 1:
                logger.warning("Brevo API rejected message: %s %s", exc.code, detail)
                raise last_exc from exc
            # Honour the Retry-After header when present (seconds or HTTP date)
            sleep_for = 0.0
            try:
                retry_after = exc.headers.get("Retry-After") if hasattr(exc, "headers") else None
                if retry_after:
                    sleep_for = float(retry_after)
            except (TypeError, ValueError):
                sleep_for = 0.0
            if sleep_for <= 0:
                sleep_for = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s
            logger.info(
                "Brevo %s — retry %d/%d in %.1fs", exc.code, attempt + 1, max_attempts, sleep_for,
            )
            time.sleep(sleep_for)
        except (URLError, TimeoutError) as exc:
            last_exc = EmailDeliveryError(f"Brevo network: {exc}")
            if attempt == max_attempts - 1:
                logger.warning("Brevo network error after %d attempts: %s", max_attempts, exc)
                raise last_exc from exc
            time.sleep(0.5 * (2 ** attempt))
    # Defensive — loop always returns or raises.
    if last_exc:
        raise last_exc
    raise EmailDeliveryError("Brevo: unknown error")


def _send_via_smtp(message: EmailMessage) -> EmailResult:
    host = _from_env("SMTP_HOST")
    user = _from_env("SMTP_USER")
    password = _from_env("SMTP_PASSWORD")
    if not (host and user and password):
        raise EmailDeliveryError("SMTP not configured")
    port = int(_from_env("SMTP_PORT", "587"))
    sender = _from_env("SMTP_FROM", _from_env("EMAIL_FROM_ADDRESS", user))

    # When the caller ships attachments, wrap the alternative bodies inside
    # a ``multipart/mixed`` envelope — most clients (Gmail, Outlook, Mail.app)
    # require the binary parts at the same level as the body.
    if message.attachments:
        msg = MIMEMultipart("mixed")
        body = MIMEMultipart("alternative")
        body.attach(
            MIMEText(message.text or _strip_html(message.html), "plain", "utf-8")
        )
        body.attach(MIMEText(message.html, "html", "utf-8"))
        msg.attach(body)
        from email.mime.application import MIMEApplication

        for att in message.attachments:
            part = MIMEApplication(
                att.get("content") or b"",
                _subtype=(att.get("mime") or "application/octet-stream").split(
                    "/"
                )[-1],
            )
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=att.get("filename", "attachment.bin"),
            )
            msg.attach(part)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(
            MIMEText(message.text or _strip_html(message.html), "plain", "utf-8")
        )
        msg.attach(MIMEText(message.html, "html", "utf-8"))
    msg["Subject"] = message.subject
    msg["From"] = sender
    msg["To"] = message.to
    if message.reply_to:
        msg["Reply-To"] = message.reply_to

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(sender, message.to, msg.as_string())
    except Exception as exc:  # smtplib raises a zoo of subclasses
        logger.warning("SMTP send failed: %s", exc)
        raise EmailDeliveryError(f"SMTP: {exc}") from exc

    return EmailResult(
        status="sent",
        backend="smtp",
        sent_at=datetime.now(timezone.utc).isoformat(),
    )


def _simulate(message: EmailMessage) -> EmailResult:
    logger.info(
        "[email simulated] to=%s subject=%s body_len=%d",
        message.to, message.subject, len(message.html),
    )
    return EmailResult(
        status="simulated",
        backend="simulation",
        sent_at=datetime.now(timezone.utc).isoformat(),
    )


def send_email(message: EmailMessage) -> EmailResult:
    """Pick the first available backend and deliver. Falls back to
    simulation when nothing is configured. Raises only when a backend
    is present but the call itself failed — callers in crons should
    swallow."""
    if _from_env("BREVO_API_KEY"):
        return _send_via_brevo(message)
    if _from_env("SMTP_HOST") and _from_env("SMTP_USER") and _from_env("SMTP_PASSWORD"):
        return _send_via_smtp(message)
    return _simulate(message)


def send_bulk(messages: Iterable[EmailMessage]) -> list[EmailResult]:
    """Sequential — Brevo's free tier only allows a handful per second
    and our boutique footprint is small (~50 clients). One per call
    keeps it simple and lets us log per-recipient outcomes."""
    results: list[EmailResult] = []
    for msg in messages:
        try:
            results.append(send_email(msg))
        except EmailDeliveryError as exc:
            logger.warning("Email to %s failed: %s", msg.to, exc)
            results.append(EmailResult(
                status="failed",
                backend="error",
                detail=str(exc),
                sent_at=datetime.now(timezone.utc).isoformat(),
            ))
    return results
