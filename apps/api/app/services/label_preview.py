"""Labelary preview wrapper — render a ZPL job to PNG for the admin UI.

Labelary (https://labelary.com) is a free, hosted ZPL renderer. We POST
the ZPL job as the request body and get back a PNG of the rendered
label, byte-for-byte identical to what the Zebra would emit.

The Labelary endpoint encodes the printer DPI and label dimensions in
the path. For Vintiz we use :

    POST https://api.labelary.com/v1/printers/8dpmm/labels/3.15x4.72/0/

    8dpmm     = 203 dpi (ZD421d)
    3.15x4.72 = inches → 80 × 120 mm
    0         = first label of the job

Verified against the official doc (labelary.com/service.html) :
- HTTPS endpoint is supported
- Multi-label : POST a ZPL with N ``^XA…^XZ`` blocks + ``Accept:
  application/pdf`` returns a multi-page PDF (one page per label),
  used by the A4 fallback path.
- Rate limit : 429 with ``Retry-After`` ; we retry with backoff.

If the service is unreachable (offline POS, network glitch) we surface
a 502 to the caller — the front-end shows a "Aperçu indisponible" state.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.services.zebra_zpl import LABELARY_DPMM, LABELARY_SIZE

_log = logging.getLogger("vintiz.labelary")

# HTTPS — the previous version used http:// which would have leaked
# label content (product names, prices, barcodes) on the wire.
LABELARY_BASE = "https://api.labelary.com/v1/printers"
TIMEOUT_S = 8.0
MAX_ATTEMPTS = 3


class PreviewUnavailable(RuntimeError):
    """Raised when Labelary doesn't return a PNG (timeout, 5xx, etc.)."""


async def _post_with_retry(
    url: str, *, zpl: str, accept: str,
) -> bytes:
    """POST a ZPL job to Labelary with retry on 429/5xx.

    Honours the ``Retry-After`` header when Labelary returns one. Falls
    back to exponential backoff (0.5s, 1s, 2s) otherwise. Raises
    :class:`PreviewUnavailable` after ``MAX_ATTEMPTS`` failures.
    """
    headers = {"Accept": accept, "Content-Type": "application/x-www-form-urlencoded"}
    last_error: str = ""
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await client.post(
                    url, content=zpl.encode("utf-8"), headers=headers,
                )
            except httpx.HTTPError as exc:
                last_error = f"network: {exc}"
                if attempt == MAX_ATTEMPTS - 1:
                    raise PreviewUnavailable(f"Labelary injoignable : {exc}") from exc
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            if response.status_code == 200 and response.content:
                return response.content
            # 429 or 5xx → retry
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < MAX_ATTEMPTS - 1:
                    retry_after = response.headers.get("Retry-After")
                    sleep_for = float(retry_after) if retry_after else 0.5 * (2 ** attempt)
                    _log.info(
                        "Labelary %s — retry %d/%d in %.1fs",
                        response.status_code, attempt + 1, MAX_ATTEMPTS, sleep_for,
                    )
                    await asyncio.sleep(sleep_for)
                    continue
            last_error = f"status={response.status_code} body={response.text[:200]}"
            break
    raise PreviewUnavailable(f"Labelary {last_error}")


async def render_zpl_to_png(zpl: str) -> bytes:
    """Render a ZPL job to PNG bytes via Labelary."""
    url = f"{LABELARY_BASE}/{LABELARY_DPMM}/labels/{LABELARY_SIZE}/0/"
    return await _post_with_retry(url, zpl=zpl, accept="image/png")


async def render_zpl_to_pdf(zpl: str) -> bytes:
    """Render a multi-label ZPL job to a multi-page PDF.

    Used by the A4 fallback : we concatenate one ``^XA…^XZ`` block per
    product and ask Labelary for a PDF where each page is one label.
    Replaces the previous "N parallel PNG calls" approach :
    - 1 HTTP roundtrip instead of N
    - 1 print job for the operator instead of multiple
    - Better print quality (PDF preserves vector text + barcode crisp)
    """
    url = f"{LABELARY_BASE}/{LABELARY_DPMM}/labels/{LABELARY_SIZE}/"
    return await _post_with_retry(url, zpl=zpl, accept="application/pdf")
