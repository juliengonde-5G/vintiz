"""SumUp card payment service.

Wraps the SumUp REST API to initiate checkouts and poll for completion.

Three environments are supported via the ``SUMUP_ENVIRONMENT`` variable:

* ``production`` — talks to the real SumUp API at ``api.sumup.com``.
  Requires ``SUMUP_API_KEY`` and ``SUMUP_MERCHANT_CODE``.
* ``sandbox``    — simulated terminal that mimics the real flow (PENDING →
  PAID/FAILED) with a configurable delay, exposes a live event log and allows
  manual approve/decline for step-by-step testing. This is the default when no
  API key is set.
* ``production`` with no key falls back to ``sandbox`` automatically so the
  app remains usable out of the box.

The sandbox store lives in-process (module level singleton). It is intended
for single-worker dev/test setups and is reset on process restart.
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

import httpx

SUMUP_API_BASE = "https://api.sumup.com/v0.1"

SandboxStatus = Literal["PENDING", "PAID", "FAILED", "CANCELLED"]


# ---------------------------------------------------------------------------
# Sandbox in-memory store
# ---------------------------------------------------------------------------

@dataclass
class SandboxCheckout:
    checkout_id: str
    reference: str
    amount: float
    currency: str
    description: str
    status: SandboxStatus = "PENDING"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    auto_approve_at: float | None = None  # timestamp after which status becomes PAID
    manual_override: bool = False  # set True when operator approved/declined

    def to_dict(self) -> dict:
        remaining = None
        if self.auto_approve_at and self.status == "PENDING" and not self.manual_override:
            remaining = max(0.0, round(self.auto_approve_at - time.time(), 1))
        return {
            "checkout_id": self.checkout_id,
            "checkout_reference": self.reference,
            "amount": self.amount,
            "currency": self.currency,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "auto_approve_in": remaining,
            "manual_override": self.manual_override,
        }


@dataclass
class SandboxEvent:
    timestamp: float
    kind: str  # create | poll | approve | decline | cancel | auto_paid
    checkout_id: str
    status: str
    payload: dict

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "iso_time": time.strftime("%H:%M:%S", time.localtime(self.timestamp)),
            "kind": self.kind,
            "checkout_id": self.checkout_id,
            "status": self.status,
            "payload": self.payload,
        }


class SandboxStore:
    """Module-level singleton holding sandbox checkouts and an event log."""

    MAX_EVENTS = 200

    def __init__(self) -> None:
        self._checkouts: dict[str, SandboxCheckout] = {}
        self._events: list[SandboxEvent] = []

    # -- checkouts ---------------------------------------------------------
    def add(self, checkout: SandboxCheckout) -> None:
        self._checkouts[checkout.checkout_id] = checkout

    def get(self, checkout_id: str) -> SandboxCheckout | None:
        return self._checkouts.get(checkout_id)

    def list(self) -> list[SandboxCheckout]:
        return sorted(self._checkouts.values(), key=lambda c: c.created_at, reverse=True)

    # -- events ------------------------------------------------------------
    def log(self, kind: str, checkout_id: str, status: str, payload: dict | None = None) -> None:
        self._events.append(
            SandboxEvent(
                timestamp=time.time(),
                kind=kind,
                checkout_id=checkout_id,
                status=status,
                payload=payload or {},
            )
        )
        if len(self._events) > self.MAX_EVENTS:
            self._events = self._events[-self.MAX_EVENTS :]

    def events(self, limit: int = 50) -> list[SandboxEvent]:
        return list(reversed(self._events[-limit:]))

    def clear_events(self) -> None:
        self._events.clear()

    def reset(self) -> None:
        self._checkouts.clear()
        self._events.clear()


# Module-level singleton — shared across requests within a worker
_sandbox_store = SandboxStore()


def get_sandbox_store() -> SandboxStore:
    return _sandbox_store


# ---------------------------------------------------------------------------
# SumUp service
# ---------------------------------------------------------------------------


class SumUpService:
    """Thin wrapper around the SumUp Checkout API with a sandbox fallback."""

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
        env = _pick("environment", "SUMUP_ENVIRONMENT").lower()
        # Auto-detect: sandbox whenever no API key is set
        if env not in ("sandbox", "production"):
            env = "sandbox" if not self.api_key else "production"
        # If production requested but no key, fall back to sandbox
        if env == "production" and not self.api_key:
            env = "sandbox"
        self.environment = env
        delay_persisted = persisted.get("sandbox_auto_delay_sec")
        try:
            if delay_persisted not in (None, ""):
                self.sandbox_auto_delay = float(delay_persisted)
            else:
                self.sandbox_auto_delay = float(os.getenv("SUMUP_SANDBOX_AUTO_DELAY_SEC", "5"))
        except (ValueError, TypeError):
            self.sandbox_auto_delay = 5.0
        # Optional return URL after reader payment (production only)
        self.return_url = _pick("return_url", "SUMUP_RETURN_URL")
        self.store = get_sandbox_store()

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
            "api_key_set": bool(self.api_key),
            "merchant_code_set": bool(self.merchant_code),
            "merchant_code_masked": masked,
            "reader_id_set": bool(self.reader_id),
            "reader_id_masked": reader_masked,
            "return_url_set": bool(self.return_url),
            "return_url": self.return_url,
            "sandbox_auto_delay_sec": self.sandbox_auto_delay,
            "api_base": SUMUP_API_BASE if self.environment == "production" else "sandbox (in-memory)",
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
        """Create a checkout.

        - **Sandbox** — in-memory simulated flow with auto-approve delay.
        - **Production + `SUMUP_READER_ID`** — push directly to the SumUp Solo
          terminal via the Readers API. The TPE rings on the cashier's side;
          the customer taps their card; no manual amount entry on the TPE.
        - **Production without reader id** — classic Checkouts API; the
          customer pays via a payment link or the Solo app on the same merchant
          account (cashier types the amount on the TPE).

        In production, API errors are surfaced to the caller (status
        ``FAILED`` + ``error_detail``) so the cashier can retry or fall back to
        a manual confirmation rather than seeing a silent fake success.
        """
        ref = reference or str(uuid.uuid4())[:8].upper()

        if self.environment == "sandbox":
            return self._sandbox_create(amount, currency, description, ref)

        # Production: prefer the Readers API if a reader is configured.
        if self.reader_id and self.merchant_code:
            pushed = await self._push_to_reader(amount, currency, description, ref)
            if pushed is not None:
                return pushed
            # _push_to_reader returned None → fall through to classic checkout

        # Production: classic Checkouts API (customer pays via link/app).
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
                    "simulated": False,
                    "mode": "checkout",
                }
            return {
                "checkout_id": f"ERR-{ref}",
                "checkout_reference": ref,
                "amount": amount,
                "currency": currency,
                "status": "FAILED",
                "environment": "production",
                "simulated": False,
                "http_status": resp.status_code,
                "error_detail": resp.text[:300],
            }
        except Exception as e:
            return {
                "checkout_id": f"ERR-{ref}",
                "checkout_reference": ref,
                "amount": amount,
                "currency": currency,
                "status": "FAILED",
                "environment": "production",
                "simulated": False,
                "error_detail": f"network error: {e}",
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
                    "simulated": False,
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
                "simulated": False,
                "mode": "reader",
                "http_status": resp.status_code,
                "error_detail": resp.text[:300],
            }
        except Exception:
            return None

    def _sandbox_create(
        self,
        amount: float,
        currency: str,
        description: str,
        ref: str,
        note: str | None = None,
    ) -> dict:
        checkout_id = f"SBX-{ref}"
        auto_at = time.time() + self.sandbox_auto_delay if self.sandbox_auto_delay > 0 else None
        co = SandboxCheckout(
            checkout_id=checkout_id,
            reference=ref,
            amount=round(amount, 2),
            currency=currency,
            description=description,
            auto_approve_at=auto_at,
        )
        self.store.add(co)
        self.store.log(
            "create",
            checkout_id,
            "PENDING",
            {
                "amount": co.amount,
                "currency": currency,
                "description": description,
                "reference": ref,
                "auto_delay_sec": self.sandbox_auto_delay,
                "note": note,
            },
        )
        result = co.to_dict()
        result["environment"] = "sandbox"
        result["simulated"] = True
        if note:
            result["note"] = note
        return result

    # ------------------------------------------------------------------
    # Poll status
    # ------------------------------------------------------------------
    async def get_checkout_status(self, checkout_id: str) -> dict:
        # Sandbox path: SBX-* and also legacy SIM-* identifiers
        if checkout_id.startswith("SBX-"):
            return self._sandbox_status(checkout_id)
        if checkout_id.startswith("SIM-"):
            # Legacy one-shot simulation — still return PAID for backward compat
            return {"checkout_id": checkout_id, "status": "PAID", "environment": "sandbox", "simulated": True}

        if self.environment == "sandbox" or not self.api_key:
            return {"checkout_id": checkout_id, "status": "PAID", "environment": "sandbox", "simulated": True}

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
                    "simulated": False,
                }
            return {
                "checkout_id": checkout_id,
                "status": "FAILED",
                "environment": "production",
                "simulated": False,
                "http_status": resp.status_code,
            }
        except Exception as e:
            return {"checkout_id": checkout_id, "status": "FAILED", "error": str(e)}

    def _sandbox_status(self, checkout_id: str) -> dict:
        co = self.store.get(checkout_id)
        if not co:
            return {
                "checkout_id": checkout_id,
                "status": "FAILED",
                "environment": "sandbox",
                "simulated": True,
                "error": "unknown checkout_id",
            }
        # Auto-transition PENDING → PAID once the delay elapsed
        if (
            co.status == "PENDING"
            and not co.manual_override
            and co.auto_approve_at is not None
            and time.time() >= co.auto_approve_at
        ):
            co.status = "PAID"
            co.updated_at = time.time()
            self.store.log("auto_paid", checkout_id, "PAID", {"reason": "auto-delay elapsed"})

        self.store.log("poll", checkout_id, co.status, {})
        result = co.to_dict()
        result["environment"] = "sandbox"
        result["simulated"] = True
        return result

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------
    async def cancel_checkout(self, checkout_id: str) -> bool:
        if checkout_id.startswith("SBX-"):
            co = self.store.get(checkout_id)
            if co and co.status == "PENDING":
                co.status = "CANCELLED"
                co.manual_override = True
                co.updated_at = time.time()
            self.store.log("cancel", checkout_id, "CANCELLED", {})
            return True
        if checkout_id.startswith("SIM-") or self.environment == "sandbox" or not self.api_key:
            return True
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.delete(
                    f"{SUMUP_API_BASE}/checkouts/{checkout_id}",
                    headers=self._headers,
                )
                return resp.status_code in (200, 204)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Sandbox admin helpers
    # ------------------------------------------------------------------
    def sandbox_approve(self, checkout_id: str) -> dict:
        co = self.store.get(checkout_id)
        if not co:
            return {"ok": False, "error": "unknown checkout_id"}
        co.status = "PAID"
        co.manual_override = True
        co.updated_at = time.time()
        self.store.log("approve", checkout_id, "PAID", {"source": "manual"})
        return {"ok": True, "checkout": co.to_dict()}

    def sandbox_decline(self, checkout_id: str) -> dict:
        co = self.store.get(checkout_id)
        if not co:
            return {"ok": False, "error": "unknown checkout_id"}
        co.status = "FAILED"
        co.manual_override = True
        co.updated_at = time.time()
        self.store.log("decline", checkout_id, "FAILED", {"source": "manual"})
        return {"ok": True, "checkout": co.to_dict()}

    def sandbox_snapshot(self, limit: int = 50) -> dict:
        return {
            "config": self.describe(),
            "checkouts": [c.to_dict() for c in self.store.list()],
            "events": [e.to_dict() for e in self.store.events(limit)],
        }

    def sandbox_clear(self) -> None:
        self.store.reset()
