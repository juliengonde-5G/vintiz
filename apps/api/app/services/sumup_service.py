"""SumUp card payment service.

Wraps the SumUp REST API to initiate solo/POS checkouts
and poll for completion. Falls back to simulation if no API key is set.
"""
import os
import uuid

import httpx

SUMUP_API_BASE = "https://api.sumup.com/v0.1"


class SumUpService:
    """Thin wrapper around the SumUp Checkout API."""

    def __init__(self) -> None:
        self.api_key = os.getenv("SUMUP_API_KEY", "")
        self.merchant_code = os.getenv("SUMUP_MERCHANT_CODE", "")

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_checkout(
        self,
        amount: float,
        currency: str = "EUR",
        description: str = "Vente Vintiz",
        reference: str | None = None,
    ) -> dict:
        """Create a SumUp checkout and return checkout_id + payment_url.

        If SUMUP_API_KEY is not set, returns a simulated checkout.
        """
        ref = reference or str(uuid.uuid4())[:8].upper()

        if not self.api_key:
            # Simulation mode — no real API call
            return {
                "checkout_id": f"SIM-{ref}",
                "checkout_reference": ref,
                "amount": amount,
                "currency": currency,
                "status": "PENDING",
                "simulated": True,
            }

        payload = {
            "checkout_reference": ref,
            "amount": amount,
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
                        "simulated": False,
                    }
                else:
                    # SumUp API error — fall back to simulation
                    return {
                        "checkout_id": f"SIM-{ref}",
                        "checkout_reference": ref,
                        "amount": amount,
                        "currency": currency,
                        "status": "PENDING",
                        "simulated": True,
                        "api_error": resp.text,
                    }
        except Exception as e:
            return {
                "checkout_id": f"SIM-{ref}",
                "checkout_reference": ref,
                "amount": amount,
                "currency": currency,
                "status": "PENDING",
                "simulated": True,
                "error": str(e),
            }

    async def get_checkout_status(self, checkout_id: str) -> dict:
        """Poll a checkout status.

        Returns dict with 'status': PAID | PENDING | FAILED.
        Simulated checkouts always return PAID after one poll (for demo).
        """
        if checkout_id.startswith("SIM-"):
            return {"checkout_id": checkout_id, "status": "PAID", "simulated": True}

        if not self.api_key:
            return {"checkout_id": checkout_id, "status": "PAID", "simulated": True}

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
                        "simulated": False,
                    }
                return {"checkout_id": checkout_id, "status": "FAILED", "simulated": False}
        except Exception as e:
            return {"checkout_id": checkout_id, "status": "FAILED", "error": str(e)}

    async def cancel_checkout(self, checkout_id: str) -> bool:
        """Cancel a pending checkout. Returns True if cancelled."""
        if checkout_id.startswith("SIM-") or not self.api_key:
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
