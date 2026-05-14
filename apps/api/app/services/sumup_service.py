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
        # Optional affiliate identification — when set, every checkout
        # carries an ``affiliate.foreign_transaction_id`` so we can look
        # up the resulting SumUp transaction (transaction_code, auth_code,
        # card brand) once it moves to PAID. Required for the
        # reconciliation + refund flow. Create them in the SumUp
        # developer console : https://developer.sumup.com/affiliate-keys
        self.affiliate_app_id = _pick("affiliate_app_id", "SUMUP_AFFILIATE_APP_ID")
        self.affiliate_key = _pick("affiliate_key", "SUMUP_AFFILIATE_KEY")

    @property
    def is_configured(self) -> bool:
        """True when the API key is set — required for any real checkout."""
        return bool(self.api_key)

    @property
    def is_sandbox(self) -> bool:
        """True when the configured API key is a SumUp test key.

        SumUp doesn't expose a separate sandbox URL — they use the same
        ``api.sumup.com`` host but accept test keys prefixed with
        ``sup_sk_test_``. Detecting this lets the UI flag the cashier
        with an orange banner "Mode test SumUp" so a real customer
        doesn't accidentally pay through a test merchant account.
        """
        return bool(self.api_key) and self.api_key.startswith("sup_sk_test_")

    @property
    def environment(self) -> str:
        return "sandbox" if self.is_sandbox else "production"

    # -- public config snapshot for UI ------------------------------------
    def describe(self) -> dict:
        masked = ""
        if self.merchant_code:
            masked = self.merchant_code[:2] + "***" + self.merchant_code[-2:]
        reader_masked = ""
        if self.reader_id:
            reader_masked = self.reader_id[:4] + "***" + self.reader_id[-2:] if len(self.reader_id) > 6 else "***"
        return {
            "environment": self.environment,
            "is_sandbox": self.is_sandbox,
            "api_key_set": bool(self.api_key),
            "merchant_code_set": bool(self.merchant_code),
            "merchant_code_masked": masked,
            "reader_id_set": bool(self.reader_id),
            "reader_id_masked": reader_masked,
            "return_url_set": bool(self.return_url),
            "return_url": self.return_url,
            "api_base": SUMUP_API_BASE,
        }

    async def ping_reader(self) -> dict:
        """Probe the configured SumUp reader and return a structured status.

        Spec-compliant (https://developer.sumup.com/api/readers): SumUp
        splits the reader state into two orthogonal axes :

        - **Pairing state** (``Reader.status``) — ``unknown | processing
          | paired | expired``. Returned by ``GET /readers/{id}``. Tells
          us whether the pairing record is usable at all.
        - **Live device status** (``StatusResponse.data.status``) —
          ``ONLINE | OFFLINE``. Returned by ``GET /readers/{id}/status``.
          Tells us whether the physical Solo is currently reachable via
          its Wi-Fi / 4G link (Solo firmware ≥ 3.3.39.0).

        We check both so the POS banner can distinguish "TPE jamais
        appairé" from "TPE appairé mais Wi-Fi coupé".

        Returns a flat dict suitable for the front-end :

            { configured, paired, online, ready, status, message,
              state, battery_level, connection_type }
        """
        import httpx

        common = {"is_sandbox": self.is_sandbox, "environment": self.environment}
        if not self.is_configured:
            return {
                **common,
                "configured": False, "paired": False, "online": False, "ready": False,
                "status": "unconfigured",
                "message": "SUMUP_API_KEY / SUMUP_MERCHANT_CODE non configurés",
            }
        if not self.reader_id:
            return {
                **common,
                "configured": True, "paired": False, "online": False, "ready": False,
                "status": "no_reader",
                "message": "Aucun TPE rattaché (SUMUP_READER_ID vide) — paiements CB possibles via lien checkout mais pas en push direct",
            }

        # SUMUP_API_BASE already includes /v0.1 — don't prefix it twice.
        reader_url = (
            f"{SUMUP_API_BASE}/merchants/{self.merchant_code}"
            f"/readers/{self.reader_id}"
        )
        status_url = f"{reader_url}/status"

        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1) Pairing state — `Reader.status`
            try:
                resp = await client.get(reader_url, headers=self._headers)
            except httpx.HTTPError as exc:
                return {
                    **common,
                    "configured": True, "paired": False, "online": False, "ready": False,
                    "status": "network_error",
                    "message": f"SumUp Cloud injoignable : {exc}",
                }
            if resp.status_code == 404:
                return {
                    **common,
                    "configured": True, "paired": False, "online": False, "ready": False,
                    "status": "reader_not_found",
                    "message": "Le SUMUP_READER_ID configuré n'existe plus côté SumUp — rappairez le TPE depuis l'app SumUp",
                }
            if resp.status_code != 200:
                return {
                    **common,
                    "configured": True, "paired": False, "online": False, "ready": False,
                    "status": f"http_{resp.status_code}",
                    "message": f"SumUp Cloud {resp.status_code}: {resp.text[:120]}",
                }
            reader = resp.json()
            pairing = (reader.get("status") or "").lower()
            if pairing != "paired":
                return {
                    **common,
                    "configured": True, "paired": False, "online": False, "ready": False,
                    "status": f"pairing_{pairing or 'unknown'}",
                    "message": {
                        "processing": "TPE en cours d'appairage avec SumUp — patientez quelques minutes ou rappairez",
                        "expired": "Appairage SumUp expiré — supprimez ce TPE dans /settings et recréez-le",
                        "unknown": "Statut d'appairage SumUp inconnu — réessayez plus tard",
                    }.get(pairing, f"TPE non appairé ({pairing})"),
                    "name": reader.get("name"),
                }

            try:
                live_resp = await client.get(status_url, headers=self._headers)
            except httpx.HTTPError as exc:
                return {
                    **common,
                    "configured": True, "paired": True, "online": False, "ready": True,
                    "status": "live_unreachable",
                    "message": f"TPE appairé mais l'état live n'est pas joignable ({exc}) — tentez quand même la vente",
                    "name": reader.get("name"),
                }

            if live_resp.status_code == 404:
                return {
                    **common,
                    "configured": True, "paired": True, "online": True, "ready": True,
                    "status": "paired",
                    "message": "TPE appairé (live status indisponible — firmware Solo < 3.3.39 ?)",
                    "name": reader.get("name"),
                }
            if live_resp.status_code != 200:
                return {
                    **common,
                    "configured": True, "paired": True, "online": False, "ready": True,
                    "status": f"live_http_{live_resp.status_code}",
                    "message": f"État live SumUp {live_resp.status_code} — TPE appairé, tentez quand même",
                    "name": reader.get("name"),
                }
            live = (live_resp.json() or {}).get("data", {}) or {}
            device_status = (live.get("status") or "").upper()
            online = device_status == "ONLINE"
            return {
                **common,
                "configured": True, "paired": True,
                "online": online,
                "ready": online,
                "status": device_status.lower() or "unknown",
                "state": live.get("state"),
                "battery_level": live.get("battery_level"),
                "connection_type": live.get("connection_type"),
                "name": reader.get("name"),
                "message": (
                    f"TPE en ligne ({live.get('state', 'IDLE')})"
                    if online
                    else "TPE hors ligne — vérifiez le Wi-Fi/4G du Solo (le TPE doit afficher l'écran d'accueil)"
                ),
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
        foreign_transaction_id: str | None = None,
    ) -> dict:
        """Create a checkout against the SumUp production API.

        - **Avec `SUMUP_READER_ID`** — push directly to the SumUp Solo
          terminal via the Readers API. The TPE rings on the cashier's side;
          the customer taps their card; no manual amount entry on the TPE.
        - **Sans reader id** — classic Checkouts API; the customer pays
          via a payment link or the Solo app on the same merchant account
          (cashier types the amount on the TPE).

        ``foreign_transaction_id`` is the Vintiz-side identifier (typically
        ``Transaction.client_uuid``). When set, it lets us **dedupe** a
        retry : if the network blip caused us to call SumUp twice with
        the same id, SumUp returns the same checkout instead of charging
        the customer twice. It also lets us look up the resulting SumUp
        transaction via ``get_transaction(foreign_transaction_id=…)``
        once the payment moves to PAID — needed for traceability and
        refunds.

        Si la clé API n'est pas configurée, retourne ``FAILED`` avec un
        ``error_detail`` explicite — la caissière voit l'erreur et ne peut
        pas valider une vente CB par accident.
        """
        ref = reference or str(uuid.uuid4())[:8].upper()
        # Foreign id : when not provided, derive a stable one from the
        # reference so retries on the same call still dedupe.
        if not foreign_transaction_id:
            foreign_transaction_id = f"vintiz-{ref}"

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
        foreign_transaction_id: str | None = None,
    ) -> dict | None:
        """Push a payment to a SumUp Solo terminal via the Readers API.

        SumUp expects the amount as integer **minor units** (cents) in the
        reader payload, unlike the top-level Checkouts API which takes a float.
        Returns ``None`` on unexpected error to let the caller fall back.

        ``foreign_transaction_id`` flows into ``affiliate.foreign_transaction_id``
        — used to look up the resulting SumUp transaction via
        ``GET /v2.1/.../transactions?foreign_transaction_id=…`` once the
        customer taps their card, so we can persist transaction_code +
        auth_code on our Payment row for reconciliation and refund.
        """
        url = (
            f"{SUMUP_API_BASE}/merchants/{self.merchant_code}"
            f"/readers/{self.reader_id}/checkout"
        )
        payload: dict = {
            "total_amount": {
                "value": int(round(amount * 100)),
                "currency": currency,
                "minor_unit": 2,
            },
            "description": description,
        }
        if self.return_url:
            payload["return_url"] = self.return_url
        # Affiliate object — only included when an Affiliate Key has been
        # configured (SumUp requires app_id + key + foreign_transaction_id
        # together, all three are mandatory per the OpenAPI spec). Without
        # the key, we omit the whole block ; the checkout still works,
        # we just don't get retrieval-by-foreign-id later.
        affiliate_key = self.affiliate_key
        affiliate_app_id = self.affiliate_app_id
        if affiliate_key and affiliate_app_id and foreign_transaction_id:
            payload["affiliate"] = {
                "app_id": affiliate_app_id,
                "key": affiliate_key,
                "foreign_transaction_id": foreign_transaction_id,
            }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=self._headers)
            if resp.status_code in (200, 201, 202):
                data = resp.json() if resp.content else {}
                inner = data.get("data") or {}
                return {
                    "checkout_id": inner.get("client_transaction_id") or ref,
                    "checkout_reference": ref,
                    "amount": amount,
                    "currency": currency,
                    "status": "PENDING",
                    "environment": self.environment,
                    "mode": "reader",
                    "reader_id": self.reader_id,
                    "foreign_transaction_id": foreign_transaction_id,
                }
            # Non-2xx from the Readers API — surface but signal failure.
            # 422 ReaderBusy / ReaderOffline both come here ; the caller
            # maps them to user-friendly French via friendly_error().
            return {
                "checkout_id": f"ERR-{ref}",
                "checkout_reference": ref,
                "amount": amount,
                "currency": currency,
                "status": "FAILED",
                "environment": self.environment,
                "mode": "reader",
                "http_status": resp.status_code,
                "error_detail": redact_sumup_error(resp.text),
                "error_friendly": _friendly_error(resp.status_code, resp.text),
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
                status = data.get("status", "PENDING")
                result = {
                    "checkout_id": checkout_id,
                    "status": status,
                    "environment": self.environment,
                }
                # Enrich with the SumUp transaction details when PAID.
                # The Checkouts API embeds the resulting transaction in
                # the ``transactions`` array once the payment completes.
                # We extract the first one (a checkout maps to ≤ 1 txn).
                if status in ("PAID", "SUCCESSFUL") and data.get("transactions"):
                    txn = (data["transactions"] or [{}])[0]
                    card = txn.get("card") or {}
                    result.update({
                        "sumup_transaction_id": txn.get("id"),
                        "sumup_transaction_code": txn.get("transaction_code"),
                        "sumup_auth_code": txn.get("auth_code"),
                        "sumup_card_brand": card.get("type") or card.get("scheme"),
                        "sumup_card_last4": card.get("last_4_digits"),
                    })
                return result
            return {
                "checkout_id": checkout_id,
                "status": "FAILED",
                "environment": self.environment,
                "http_status": resp.status_code,
                "error_friendly": _friendly_error(resp.status_code, resp.text),
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


    # ==================================================================
    # NEW: terminate, refund, get_transaction
    # Added to close the audit gaps for ZERO defect / full compatibility.
    # ==================================================================

    async def terminate_reader_checkout(self) -> dict:
        """Cancel an in-flight checkout currently displayed on the Solo.

        Spec: ``POST /v0.1/merchants/{m}/readers/{r}/terminate``.

        The device must be online AND waiting for the cardholder
        (WAITING_FOR_CARD / WAITING_FOR_PIN / WAITING_FOR_SIGNATURE).
        If the customer already tapped the card, the transaction will
        complete and terminate has no effect — that's documented
        SumUp behaviour, not a bug.

        Returns a dict { ok, status, message } for the caller's UX.
        """
        if not self.is_configured:
            return {"ok": False, "status": "unconfigured", "message": "SumUp non configuré"}
        if not self.reader_id:
            return {"ok": False, "status": "no_reader", "message": "Aucun TPE configuré"}

        url = (
            f"{SUMUP_API_BASE}/merchants/{self.merchant_code}"
            f"/readers/{self.reader_id}/terminate"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, headers=self._headers)
        except httpx.HTTPError as exc:
            return {
                "ok": False, "status": "network_error",
                "message": f"SumUp injoignable : {redact_sumup_error(str(exc))}",
            }
        if resp.status_code == 202:
            return {"ok": True, "status": "terminated", "message": "Annulation envoyée au TPE"}
        if resp.status_code == 422:
            return {
                "ok": False, "status": "not_waiting",
                "message": "Le TPE n'attend pas le client (déjà payé ou inactif) — annulation refusée",
            }
        if resp.status_code == 404:
            return {"ok": False, "status": "not_found", "message": "TPE introuvable côté SumUp"}
        return {
            "ok": False, "status": f"http_{resp.status_code}",
            "message": _friendly_error(resp.status_code, resp.text),
        }

    async def refund_transaction(
        self,
        transaction_id: str,
        *,
        amount: float | None = None,
    ) -> dict:
        """Refund a SumUp transaction in full or partially.

        Spec: ``POST /v1.0/merchants/{m}/payments/{id}/refunds``.

        Used by the Vintiz refund flow when the operator refunds a
        customer who originally paid by card — without this call, the
        customer would receive cash from the till but SumUp would still
        hold the money, creating an accounting mismatch.

        ``amount`` is in EUR (decimal). Omit for a full refund. SumUp
        rejects amounts > original amount or that would exceed the
        merchant's available balance.

        Returns { ok, status, http_status, message, error_code }.
        """
        if not self.is_configured:
            return {"ok": False, "status": "unconfigured",
                    "message": "SumUp non configuré — remboursement manuel requis"}
        if not transaction_id or transaction_id.startswith(("NOKEY-", "ERR-")):
            return {"ok": False, "status": "invalid_id",
                    "message": "ID transaction SumUp invalide — vérifiez la traçabilité"}

        url = (
            f"https://api.sumup.com/v1.0/merchants/{self.merchant_code}"
            f"/payments/{transaction_id}/refunds"
        )
        body: dict = {}
        if amount is not None:
            body["amount"] = round(float(amount), 2)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=body, headers=self._headers)
        except httpx.HTTPError as exc:
            return {
                "ok": False, "status": "network_error",
                "message": f"SumUp injoignable : {redact_sumup_error(str(exc))}",
            }
        if resp.status_code == 204:
            return {
                "ok": True, "status": "refunded", "http_status": 204,
                "message": f"Remboursement SumUp effectué ({amount or 'total'} EUR)",
            }
        # Parse the error body to surface the SumUp error_code verbatim
        body_text = resp.text
        try:
            data = resp.json()
            error_code = data.get("error_code")
            error_msg = data.get("message")
        except Exception:  # noqa: BLE001
            error_code, error_msg = None, body_text[:200]
        return {
            "ok": False,
            "status": f"http_{resp.status_code}",
            "http_status": resp.status_code,
            "error_code": error_code,
            "message": (
                _friendly_refund_error(error_code, error_msg)
                or _friendly_error(resp.status_code, body_text)
            ),
        }

    async def get_transaction(
        self,
        *,
        transaction_id: str | None = None,
        transaction_code: str | None = None,
        foreign_transaction_id: str | None = None,
    ) -> dict | None:
        """Look up a SumUp transaction's full details.

        Spec: ``GET /v2.1/merchants/{m}/transactions``.

        At least one of ``transaction_id``, ``transaction_code`` or
        ``foreign_transaction_id`` must be provided. We use this right
        after a checkout moves to PAID to fetch the transaction_code +
        auth_code + card_brand + card_last4 that we persist on the
        Payment row for reconciliation and refund.

        Returns the SumUp transaction dict, or None on error / not found.
        """
        if not self.is_configured or not self.merchant_code:
            return None
        params = {}
        if transaction_id:
            params["id"] = transaction_id
        elif transaction_code:
            params["transaction_code"] = transaction_code
        elif foreign_transaction_id:
            params["foreign_transaction_id"] = foreign_transaction_id
        else:
            return None
        url = (
            f"https://api.sumup.com/v2.1/merchants/{self.merchant_code}/transactions"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params, headers=self._headers)
            if resp.status_code == 200:
                return resp.json()
        except httpx.HTTPError as exc:
            _log.warning("get_transaction network error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# User-facing error mapping — French messages for the cashier
# ---------------------------------------------------------------------------

# Top documented SumUp error codes mapped to actionable French copy. The
# generic ``_friendly_error`` fallback covers anything not in this table.
_ERROR_CODES_FR: dict[str, str] = {
    "READER_BUSY": "Le TPE traite déjà un paiement — patientez quelques secondes ou redémarrez le terminal",
    "READER_OFFLINE": "TPE hors ligne — vérifiez le Wi-Fi/4G du Solo (le TPE doit afficher l'écran d'accueil)",
    "READER_NOT_FOUND": "TPE inconnu — vérifiez SUMUP_READER_ID dans /settings > Paiement",
    "CONFLICT": "Cette transaction n'est pas dans un état remboursable (déjà remboursée, expirée, ou non finalisée)",
    "NOT_ENOUGH_BALANCE": "Solde SumUp insuffisant pour le remboursement — voir l'app SumUp",
    "NOT_FOUND": "Transaction introuvable côté SumUp",
    "MISSING_FIELD": "Données invalides envoyées à SumUp — voir détail",
}


def _friendly_error(http_status: int, body_text: str) -> str:
    """Generic mapping of (HTTP status, error body) → French message."""
    if http_status == 401:
        return "Clé API SumUp invalide ou expirée — re-créer la clé dans /settings"
    if http_status == 403:
        return "Permissions insuffisantes sur la clé SumUp — vérifier les scopes (payments, readers.read, readers.write)"
    if http_status == 404:
        return "Ressource SumUp introuvable"
    if http_status == 409:
        return "Conflit côté SumUp (paiement déjà traité ou en cours)"
    if http_status == 422:
        return "Données refusées par SumUp — voir détail"
    if http_status == 429:
        return "Trop d'appels SumUp — patientez quelques secondes"
    if 500 <= http_status < 600:
        return "Erreur serveur SumUp — réessayer plus tard"
    return f"SumUp HTTP {http_status} — {redact_sumup_error(body_text)[:200]}"


def _friendly_refund_error(error_code: str | None, message: str | None) -> str | None:
    """Map a refund error_code to a French message ; None if unknown."""
    if not error_code:
        return None
    if error_code in _ERROR_CODES_FR:
        return _ERROR_CODES_FR[error_code]
    return None
