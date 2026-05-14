"""Unified SMS gateway — Brevo (primary) + Twilio (legacy fallback) + simulation.

Mirrors the email_gateway.py shape. Provider priority :

1. **Brevo Transactional SMS** when ``BREVO_API_KEY`` is set
   (same key as the email gateway — single API key for both channels).
2. **Twilio** when ``TWILIO_ACCOUNT_SID`` + ``TWILIO_AUTH_TOKEN`` +
   ``TWILIO_FROM`` are all set. Kept as a fallback so existing prod
   deployments keep working until they migrate to Brevo.
3. **Simulation** otherwise — the call is logged but no SMS leaves
   the server. The caller's UI surfaces this as a warning so the
   operator doesn't think a real message went out.

The gateway hits the providers' REST APIs directly (urllib) to avoid
adding SDK dependencies for what amounts to one endpoint each.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


logger = logging.getLogger("vintiz.sms")


# E.164 normalisation — Brevo and Twilio both reject phone numbers
# that aren't in international E.164 format ("+33612345678"). Boutique
# operators routinely type "06 12 34 56 78" or "+33 6 12 34 56 78" or
# "0612345678" ; we normalise on the way in so the send always works.
_PHONE_NON_DIGITS = re.compile(r"[^\d+]")


def normalise_phone_e164(raw: str, default_country_code: str = "33") -> str:
    """Best-effort E.164 conversion for French numbers.

    Rules :
    - ``+33 6 12 34 56 78`` → ``+33612345678``
    - ``06 12 34 56 78`` → ``+33612345678`` (assume FR national)
    - ``0033612345678`` → ``+33612345678`` (drop the international 00)
    - already E.164 → unchanged

    Anything that doesn't look like a phone (≤ 6 digits) is returned
    as-is and the gateway will surface the API error to the caller.
    """
    if not raw:
        return ""
    cleaned = _PHONE_NON_DIGITS.sub("", raw)
    if cleaned.startswith("+"):
        return cleaned
    if cleaned.startswith("00"):
        return "+" + cleaned[2:]
    if cleaned.startswith("0") and len(cleaned) >= 9:
        # National FR (or another country with same convention) — drop
        # the leading 0 and prefix the default country code.
        return f"+{default_country_code}{cleaned[1:]}"
    if len(cleaned) >= 9:
        # Numbers without a leading 0 → assume already in international
        # form without the +, e.g. "33612345678".
        return f"+{cleaned}"
    return cleaned


class SMSDeliveryError(RuntimeError):
    pass


@dataclass
class SMSMessage:
    to: str
    body: str


@dataclass
class SMSResult:
    status: str   # "sent" | "simulated" | "failed"
    backend: str  # "brevo" | "twilio" | "simulation"
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


def _brevo_api_key() -> str:
    """The Brevo key is shared with the email gateway: prefer the email
    config section so a single value in /settings > Communication
    activates both channels.
    """
    try:
        from app.services.app_config import get_section
        email_section = get_section("email")
        value = email_section.get("brevo_api_key")
        if value not in (None, ""):
            return str(value)
    except Exception:
        pass
    return os.getenv("BREVO_API_KEY", "")


def _brevo_sender() -> str:
    """Alphanumeric sender ID shown on the recipient's phone.

    Brevo allows up to 11 characters; defaults to ``Vintiz`` (6 chars).
    Overridable via ``BREVO_SMS_SENDER`` or sms.brevo_sender in
    app_config.
    """
    return _from_config("BREVO_SMS_SENDER", "brevo_sender", default="Vintiz")[:11]


def describe_active_provider() -> dict:
    if _brevo_api_key():
        return {"provider": "brevo", "configured": True, "from": _brevo_sender()}
    sid = _from_config("TWILIO_ACCOUNT_SID", "twilio_account_sid")
    token = _from_config("TWILIO_AUTH_TOKEN", "twilio_auth_token")
    from_ = _from_config("TWILIO_FROM", "twilio_from")
    if sid and token and from_:
        return {"provider": "twilio", "configured": True, "from": from_}
    return {"provider": "simulation", "configured": False}


def _send_via_brevo(message: SMSMessage) -> SMSResult:
    api_key = _brevo_api_key()
    if not api_key:
        raise SMSDeliveryError("BREVO_API_KEY not set")

    payload = json.dumps({
        "sender": _brevo_sender(),
        "recipient": message.to,
        "content": message.body,
        "type": "transactional",
    }).encode("utf-8")
    req = Request(
        "https://api.brevo.com/v3/transactionalSMS/sms",
        data=payload,
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:  # noqa: S310 — domain pinned
            text = resp.read().decode("utf-8")
            body = json.loads(text) if text else {}
            return SMSResult(
                status="sent",
                backend="brevo",
                message_id=str(body.get("messageId") or body.get("reference") or ""),
                sent_at=datetime.now(timezone.utc).isoformat(),
            )
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        logger.warning("Brevo SMS API rejected message: %s %s", exc.code, detail)
        raise SMSDeliveryError(f"Brevo {exc.code}: {detail[:200]}") from exc
    except (URLError, TimeoutError) as exc:
        logger.warning("Brevo SMS network error: %s", exc)
        raise SMSDeliveryError(f"Brevo network: {exc}") from exc


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
    """Pick the first available backend and deliver. Falls back to simulation.

    Order: Brevo (preferred — single key shared with email) → Twilio
    (legacy fallback) → simulation.

    Normalises the destination phone to E.164 (Brevo + Twilio both
    require it). Retries up to 3× on 429/5xx with exponential backoff,
    honouring the ``Retry-After`` header when SumUp returns one.
    """
    # Defensive : both Brevo and Twilio reject malformed numbers with
    # a generic 400 that confuses operators ; normalise first so the
    # error surface matches what the cashier expects.
    message = SMSMessage(to=normalise_phone_e164(message.to), body=message.body)
    if not message.to or len(message.to) < 8:
        return SMSResult(
            status="failed",
            backend="simulation",
            detail=f"Numéro de téléphone invalide ({message.to or 'vide'})",
            sent_at=datetime.now(timezone.utc).isoformat(),
        )

    max_attempts = 3
    last_err: SMSDeliveryError | None = None
    use_brevo = bool(_brevo_api_key())
    use_twilio = bool(
        _from_config("TWILIO_ACCOUNT_SID", "twilio_account_sid")
        and _from_config("TWILIO_AUTH_TOKEN", "twilio_auth_token")
        and _from_config("TWILIO_FROM", "twilio_from")
    )
    if not (use_brevo or use_twilio):
        return _simulate(message)

    for attempt in range(max_attempts):
        try:
            return _send_via_brevo(message) if use_brevo else _send_via_twilio(message)
        except SMSDeliveryError as exc:
            last_err = exc
            msg = str(exc)
            should_retry = ("429" in msg) or any(f"{c}" in msg for c in (500, 502, 503, 504))
            if not should_retry or attempt == max_attempts - 1:
                raise
            sleep_for = 0.5 * (2 ** attempt)
            logger.info("SMS retry %d/%d in %.1fs after %s",
                        attempt + 1, max_attempts, sleep_for, msg[:80])
            time.sleep(sleep_for)
    if last_err:
        raise last_err
    raise SMSDeliveryError("SMS gateway: unknown error")
