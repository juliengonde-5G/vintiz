"""Unified SMS gateway — Twilio fallback for OTP magic-link.

Mirrors the email_gateway.py shape: Twilio when ``TWILIO_*`` is configured
(persisted via app_config first, env vars second), simulation otherwise.

The gateway uses Twilio's REST API directly (urllib) so we avoid a Twilio
SDK dependency. Only the Messages endpoint is used.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


logger = logging.getLogger("vintiz.sms")


class SMSDeliveryError(RuntimeError):
    pass


@dataclass
class SMSMessage:
    to: str
    body: str


@dataclass
class SMSResult:
    status: str   # "sent" | "simulated" | "failed"
    backend: str  # "twilio" | "simulation"
    message_id: str | None = None
    detail: str | None = None
    sent_at: str = ""


def _from_config(env_var: str, persisted_key: str, default: str = "") -> str:
    """Read from app_config['sms'] first, env var second."""
    try:
        from app.services.app_config import get_section
        section = get_section("sms")
        value = section.get(persisted_key)
        if value not in (None, ""):
            return str(value)
    except Exception:
        pass
    return os.getenv(env_var, default)


def describe_active_provider() -> dict:
    sid = _from_config("TWILIO_ACCOUNT_SID", "twilio_account_sid")
    token = _from_config("TWILIO_AUTH_TOKEN", "twilio_auth_token")
    from_ = _from_config("TWILIO_FROM", "twilio_from")
    if sid and token and from_:
        return {"provider": "twilio", "configured": True, "from": from_}
    return {"provider": "simulation", "configured": False}


def _send_via_twilio(message: SMSMessage) -> SMSResult:
    sid = _from_config("TWILIO_ACCOUNT_SID", "twilio_account_sid")
    token = _from_config("TWILIO_AUTH_TOKEN", "twilio_auth_token")
    from_ = _from_config("TWILIO_FROM", "twilio_from")
    if not (sid and token and from_):
        raise SMSDeliveryError("Twilio not configured")

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urlencode({"To": message.to, "From": from_, "Body": message.body}).encode("utf-8")
    auth = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
    req = Request(
        url,
        data=data,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:  # noqa: S310 — domain pinned
            text = resp.read().decode("utf-8")
            payload = json.loads(text) if text else {}
            return SMSResult(
                status="sent",
                backend="twilio",
                message_id=payload.get("sid"),
                sent_at=datetime.now(timezone.utc).isoformat(),
            )
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        logger.warning("Twilio API rejected message: %s %s", exc.code, detail)
        raise SMSDeliveryError(f"Twilio {exc.code}: {detail[:200]}") from exc
    except (URLError, TimeoutError) as exc:
        logger.warning("Twilio network error: %s", exc)
        raise SMSDeliveryError(f"Twilio network: {exc}") from exc


def _simulate(message: SMSMessage) -> SMSResult:
    logger.info(
        "[sms simulated] to=%s body=%s",
        message.to, message.body[:80],
    )
    return SMSResult(
        status="simulated",
        backend="simulation",
        sent_at=datetime.now(timezone.utc).isoformat(),
    )


def send_sms(message: SMSMessage) -> SMSResult:
    """Pick the first available backend and deliver. Falls back to simulation."""
    sid = _from_config("TWILIO_ACCOUNT_SID", "twilio_account_sid")
    token = _from_config("TWILIO_AUTH_TOKEN", "twilio_auth_token")
    from_ = _from_config("TWILIO_FROM", "twilio_from")
    if sid and token and from_:
        return _send_via_twilio(message)
    return _simulate(message)
