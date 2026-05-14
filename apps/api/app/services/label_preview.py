"""Labelary preview wrapper — render a ZPL job to PNG for the admin UI.

Labelary (http://labelary.com) is a free, hosted ZPL renderer. We POST
the ZPL job as the request body and get back a PNG of the rendered
label, byte-for-byte identical to what the Zebra would emit.

The Labelary endpoint encodes the printer DPI and label dimensions in
the path. For Vintiz we use:

    POST http://api.labelary.com/v1/printers/8dpmm/labels/3.15x4.72/0/

    8dpmm     = 203 dpi (ZD421d)
    3.15x4.72 = inches → 80 × 120 mm
    0         = first label of the job

If the service is unreachable (offline POS, network glitch) we surface
a 502 to the caller — the front-end shows a "Aperçu indisponible" state.
"""

from __future__ import annotations

import httpx

from app.services.zebra_zpl import LABELARY_DPMM, LABELARY_SIZE

LABELARY_BASE = "http://api.labelary.com/v1/printers"
TIMEOUT_S = 8.0


class PreviewUnavailable(RuntimeError):
    """Raised when Labelary doesn't return a PNG (timeout, 5xx, etc.)."""


async def render_zpl_to_png(zpl: str) -> bytes:
    """Render a ZPL job to PNG bytes via Labelary."""
    url = f"{LABELARY_BASE}/{LABELARY_DPMM}/labels/{LABELARY_SIZE}/0/"
    headers = {"Accept": "image/png", "Content-Type": "application/x-www-form-urlencoded"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            response = await client.post(url, content=zpl.encode("utf-8"), headers=headers)
    except httpx.HTTPError as exc:
        raise PreviewUnavailable(f"Labelary injoignable : {exc}") from exc

    if response.status_code != 200 or not response.content:
        raise PreviewUnavailable(
            f"Labelary status={response.status_code}, body={response.text[:200]}"
        )
    return response.content
