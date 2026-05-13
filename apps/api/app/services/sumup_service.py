"""SumUp card payment service — production only.

Wraps the SumUp Checkout API at ``api.sumup.com``. Requires
``SUMUP_API_KEY`` and ``SUMUP_MERCHANT_CODE`` (or the persisted equivalent
in ``data/app_config.json``).

Le mode sandbox/simulation a été retiré : Vintiz boutique tourne sur des
clés SumUp de production. Si la clé API n'est pas configurée, tout
checkout retourne un FAILED clair plutôt que de laisser passer un
faux paiement.
"""
from __future__ import annotations

import logging
import os
import re
import uuid

import httpx

_log = logging.getLogger("vintiz")

SUMUP_API_BASE = "https://api.sumup.com/v0.1"


# ---------------------------------------------------------------------------
# PII redaction for persisted SumUp error payloads
# ---------------------------------------------------------------------------

# PAN (Primary Account Number) : 13 à 19 chiffres consécutifs.
# Visa 16, Mastercard 16, Amex 15, Maestro 12-19, Discover 16-19.
# On garde les non-digits autour pour éviter de matcher des timestamps,
# mais on traite les espaces/dashes typiques de PAN affichés (4-4-4-4).
_PAN_RE = re.compile(
    r"(?<!\d)(?:\d[\s\-]?){13,19}(?!\d)"
)
# CVV / CVC / CVV2 / CSC : 3 ou 4 chiffres précédés d'un libellé connu.
_CVV_RE = re.compile(
    r"(?i)\b(cvv2?|cvc2?|csc|card_security_code|security_code)\b\s*[:=]?\s*\d{3,4}"
)
# Authorization headers et Bearer tokens.
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}")
_AUTH_HEADER_RE = re.compile(
    r"(?i)\bauthorization\b\s*[:=]\s*[A-Za-z0-9._\-+/=\s]{8,}"
)
# API keys SumUp / Stripe / Anthropic / etc. (préfixes connus suivis de
# 24+ caractères de payload).
_API_KEY_RE = re.compile(
    r"\b(sup_sk_|sk_live_|pk_live_|sk_test_|pk_test_|sk-ant-)[A-Za-z0-9_\-]{20,}"
)
# JWT (3 segments base64 séparés par des points).
_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"
)


def redact_sumup_error(text: str | None, max_len: int = 300) -> str:
    """Nettoie un payload d'erreur SumUp avant persistance ou logging.

    Si SumUp ou la stack HTTP renvoie une erreur contenant un PAN partiel,
    un CVV, un Bearer token ou une clé API, on les remplace par un
    marqueur ``<…_REDACTED>`` avant de tronquer à ``max_len`` caractères.

    Conforme à PCI-DSS req. 3 (interdiction de stocker du PAN/CVV en clair)
    et au principe RGPD de minimisation.
    """
    if not text:
        return ""
    safe = str(text)
    safe = _PAN_RE.sub("<PAN_REDACTED>", safe)
    safe = _CVV_RE.sub(
        lambda m: f"{m.group(1)} <CVV_REDACTED>", safe
    )
    safe = _BEARER_RE.sub("Bearer <TOKEN_REDACTED>", safe)
    safe = _AUTH_HEADER_RE.sub("Authorization: <REDACTED>", safe)
    safe = _API_KEY_RE.sub(
        lambda m: f"{m.group(1)}<API_KEY_REDACTED>", safe
    )
    safe = _JWT_RE.sub("<JWT_REDACTED>", safe)
    if len(safe) > max_len:
        safe = safe[:max_len].rstrip() + "…"
    return safe


# ---------------------------------------------------------------------------
# SumUp service — production API only
# ---------------------------------------------------------------------------


class SumUpService:
    """Thin wrapper around the SumUp Checkout API (production only).

    Loads its credentials from the persisted config (``data/app_config.json``)
    or environment variables. Si aucune clé n'est posée, ``is_configured``
    retourne False et tous les appels CB échouent proprement (``FAILED`` +
    ``error_detail``) plutôt que de laisser passer un faux paiement.
    """

    def __init__(self) -> None:
        # Persisted config (data/app_config.json) takes precedence over env vars
        # so the manager can configure SumUp credentials from the UI without
        # touching the deployment.
        try:
            from app.services.app_config import get_section
            persisted = get_section("sumup")
        except Exception:
            persisted = {}

        def _pick(key: str, env_var: str, default: str = "") -> str:
            value = (persisted.get(key) or "").strip() if isinstance(persisted.get(key), str) else ""
            if not value:
                value = os.getenv(env_var, default).strip()
            return value

        self.api_key = _pick("api_key", "SUMUP_API_KEY")
        self.merchant_code = _pick("merchant_code", "SUMUP_MERCHANT_CODE")
        # Optional: target a specific SumUp Solo terminal via the Readers API.
        # When set, card checkouts are pushed to this reader so the TPE Solo
        # rings automatically without the cashier re-entering the amount.
        self.reader_id = _pick("reader_id", "SUMUP_READER_ID")
        # Optional return URL after reader payment.
        self.return_url = _pick("return_url", "SUMUP_RETURN_URL")

    @property
    def is_configured(self) -> bool:
        """True when the API key is set — required for any real checkout."""
        return bool(self.api_key)

    # -- public config snapshot for UI ------------------------------------
    def describe(self) -> dict:
        masked = ""
        if self.merchant_code:
            masked = self.merchant_code[:2] + "***" + self.merchant_code[-2:]
        reader_masked = ""
        if self.reader_id:
            reader_masked = self.reader_id[:4] + "***" + self.reader_id[-2:] if len(self.reader_id) > 6 else "***"
        return {
            "environment": "production",
            "api_key_set": bool(self.api_key),
            "merchant_code_set": bool(self.merchant_code),
            "merchant_code_masked": masked,
            "reader_id_set": bool(self.reader_id),
            "reader_id_masked": reader_masked,
            "return_url_set": bool(self.return_url),
            "return_url": self.return_url,
            "api_base": SUMUP_API_BASE,
        }

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Create checkout
    # ------------------------------------------------------------------
    async def create_checkout(
        self,
        amount: float,
        currency: str = "EUR",
        description: str = "Vente Vintiz",
        reference: str | None = None,
    ) -> dict:
        """Create a checkout against the SumUp production API.

        - **Avec `SUMUP_READER_ID`** — push directly to the SumUp Solo
          terminal via the Readers API. The TPE rings on the cashier's side;
          the customer taps their card; no manual amount entry on the TPE.
        - **Sans reader id** — classic Checkouts API; the customer pays
          via a payment link or the Solo app on the same merchant account
          (cashier types the amount on the TPE).

        Si la clé API n'est pas configurée, retourne ``FAILED`` avec un
        ``error_detail`` explicite — la caissière voit l'erreur et ne peut
        pas valider une vente CB par accident.
        """
        ref = reference or str(uuid.uuid4())[:8].upper()

        if not self.is_configured:
            _log.error(
                "SumUp create_checkout called but SUMUP_API_KEY is not configured. "
                "Configure SUMUP_API_KEY + SUMUP_MERCHANT_CODE dans .env ou via "
                "/admin/sumup-config avant d'encaisser en CB.",
            )
            return {
                "checkout_id": f"NOKEY-{ref}",
                "checkout_reference": ref,
                "amount": amount,
                "currency": currency,
                "status": "FAILED",
                "environment": "production",
                "error_detail": "SumUp non configuré (SUMUP_API_KEY manquant) — paiement CB indisponible.",
            }

        # Prefer the Readers API if a reader is configured.
        if self.reader_id and self.merchant_code:
            pushed = await self._push_to_reader(amount, currency, description, ref)
            if pushed is not None:
                return pushed
            # _push_to_reader returned None → fall through to classic checkout

        # Classic Checkouts API (customer pays via link/app).
        payload = {
            "checkout_reference": ref,
            "amount": round(amount, 2),
            "currency": currency,
            "pay_to_email": self.merchant_code or "",
            "description": description,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{SUMUP_API_BASE}/checkouts",
                    json=payload,
                    headers=self._headers,
                )
            if resp.status_code in (200, 201):
                data = resp.json()
                return {
                    "checkout_id": data.get("id", ref),
                    "checkout_reference": ref,
                    "amount": amount,
                    "currency": currency,
                    "status": data.get("status", "PENDING"),
                    "environment": "production",
                    "mode": "checkout",
                }
            return {
                "checkout_id": f"ERR-{ref}",
                "checkout_reference": ref,
                "amount": amount,
                "currency": currency,
                "status": "FAILED",
                "environment": "production",
                "http_status": resp.status_code,
                "error_detail": redact_sumup_error(resp.text),
            }
        except Exception as e:
            return {
                "checkout_id": f"ERR-{ref}",
                "checkout_reference": ref,
                "amount": amount,
                "currency": currency,
                "status": "FAILED",
                "environment": "production",
                "error_detail": redact_sumup_error(f"network error: {e}"),
            }

    async def _push_to_reader(
        self,
        amount: float,
        currency: str,
        description: str,
        ref: str,
    ) -> dict | None:
        """Push a payment to a SumUp Solo terminal via the Readers API.

        SumUp expects the amount as integer **minor units** (cents) in the
        reader payload, unlike the top-level Checkouts API which takes a float.
        Returns ``None`` on unexpected error to let the caller fall back.
        """
        url = (
            f"{SUMUP_API_BASE}/merchants/{self.merchant_code}"
            f"/readers/{self.reader_id}/checkout"
        )
        payload = {
            "total_amount": {
                "value": int(round(amount * 100)),
                "currency": currency,
                "minor_unit": 2,
            },
            "description": description,
            "return_url": self.return_url or None,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=self._headers)
            if resp.status_code in (200, 201, 202):
                data = resp.json() if resp.content else {}
                return {
                    "checkout_id": data.get("data", {}).get("client_transaction_id") or ref,
                    "checkout_reference": ref,
                    "amount": amount,
                    "currency": currency,
                    "status": "PENDING",
                    "environment": "production",
                    "mode": "reader",
                    "reader_id": self.reader_id,
                }
            # Non-2xx from the Readers API — surface but signal failure.
            return {
                "checkout_id": f"ERR-{ref}",
                "checkout_reference": ref,
                "amount": amount,
                "currency": currency,
                "status": "FAILED",
                "environment": "production",
                "mode": "reader",
                "http_status": resp.status_code,
                "error_detail": redact_sumup_error(resp.text),
            }
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Poll status
    # ------------------------------------------------------------------
    async def get_checkout_status(self, checkout_id: str) -> dict:
        # Un checkout_id qui commence par NOKEY-* ou ERR-* est une trace
        # d'erreur côté Vintiz, pas un vrai checkout SumUp. On renvoie
        # FAILED sans appeler l'API.
        if checkout_id.startswith(("NOKEY-", "ERR-")):
            return {
                "checkout_id": checkout_id,
                "status": "FAILED",
                "environment": "production",
                "error": "local error sentinel",
            }

        if not self.is_configured:
            return {
                "checkout_id": checkout_id,
                "status": "FAILED",
                "environment": "production",
                "error": "SumUp non configuré (SUMUP_API_KEY manquant)",
            }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{SUMUP_API_BASE}/checkouts/{checkout_id}",
                    headers=self._headers,
                )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "checkout_id": checkout_id,
                    "status": data.get("status", "PENDING"),
                    "environment": "production",
                }
            return {
                "checkout_id": checkout_id,
                "status": "FAILED",
                "environment": "production",
                "http_status": resp.status_code,
            }
        except Exception as e:
            return {
                "checkout_id": checkout_id,
                "status": "FAILED",
                "error": redact_sumup_error(str(e)),
            }

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------
    async def cancel_checkout(self, checkout_id: str) -> bool:
        """Cancel a checkout — refuses to cancel a PAID one.

        Cancelling a checkout that already moved to PAID would create a
        comptable mismatch: the customer's card is debited at SumUp but
        the cashier UI marks the sale as cancelled and never creates the
        Vintiz transaction. We hard-fail in that case so the caller has
        to confirm the payment manually instead of losing the money.
        """
        if checkout_id.startswith(("NOKEY-", "ERR-")):
            return True  # local sentinel, nothing to cancel side SumUp.

        if not self.is_configured:
            return False

        # Peek at the current status before issuing DELETE. If the checkout
        # is already PAID at SumUp, refuse the cancel and let the cashier
        # finalise the sale manually.
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                peek = await client.get(
                    f"{SUMUP_API_BASE}/checkouts/{checkout_id}",
                    headers=self._headers,
                )
                if peek.status_code == 200:
                    current = (peek.json() or {}).get("status", "")
                    if current == "PAID":
                        _log.warning(
                            "cancel_checkout refused (production): %s already PAID at SumUp",
                            checkout_id,
                        )
                        return False
                resp = await client.delete(
                    f"{SUMUP_API_BASE}/checkouts/{checkout_id}",
                    headers=self._headers,
                )
                return resp.status_code in (200, 204)
        except Exception as exc:  # noqa: BLE001
            _log.warning("cancel_checkout network error for %s: %s", checkout_id, exc)
            return False
