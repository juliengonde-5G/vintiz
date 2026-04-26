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

import json
import logging
import os
import smtplib
from dataclasses import dataclass
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
    value = os.getenv(key)
    return value if value is not None else default


def _send_via_brevo(message: EmailMessage) -> EmailResult:
    """Hit Brevo's transactional endpoint. Network call wrapped in
    urllib so we keep zero runtime dependencies (no httpx/aiohttp)."""

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

    body = json.dumps(payload).encode("utf-8")
    req = Request(
        "https://api.brevo.com/v3/smtp/email",
        data=body,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": api_key,
        },
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
        logger.warning("Brevo API rejected message: %s %s", exc.code, detail)
        raise EmailDeliveryError(f"Brevo {exc.code}: {detail[:200]}") from exc
    except (URLError, TimeoutError) as exc:
        logger.warning("Brevo network error: %s", exc)
        raise EmailDeliveryError(f"Brevo network: {exc}") from exc


def _send_via_smtp(message: EmailMessage) -> EmailResult:
    host = _from_env("SMTP_HOST")
    user = _from_env("SMTP_USER")
    password = _from_env("SMTP_PASSWORD")
    if not (host and user and password):
        raise EmailDeliveryError("SMTP not configured")
    port = int(_from_env("SMTP_PORT", "587"))
    sender = _from_env("SMTP_FROM", _from_env("EMAIL_FROM_ADDRESS", user))

    msg = MIMEMultipart("alternative")
    msg["Subject"] = message.subject
    msg["From"] = sender
    msg["To"] = message.to
    if message.reply_to:
        msg["Reply-To"] = message.reply_to
    msg.attach(MIMEText(message.text or _strip_html(message.html), "plain", "utf-8"))
    msg.attach(MIMEText(message.html, "html", "utf-8"))

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
