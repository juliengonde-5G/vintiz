"""Label printing endpoints — Zebra ZD421d over ZPL.

Replaces the previous SATO/SBPL stack. Single source of truth for both
the unitary print (admin clicks the printer icon on a row) and the batch
print (admin selects N products + clicks "Imprimer les étiquettes").

All endpoints are manager-only.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from typing import Annotated

logger = logging.getLogger("vintiz")

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import RoleChecker
from app.models.product import Product
from app.services import zebra_cloud, zebra_printer
from app.services.hardware_config import load_config
from app.services.label_preview import (
    PreviewUnavailable,
    render_zpl_to_pdf,
    render_zpl_to_png,
)
from app.services.zebra_zpl import (
    build_label_set_zpl,
    build_label_zpl,
    build_price_label_zpl,
    product_to_label_data,
)

router = APIRouter(prefix="/labels", tags=["labels"])

manager_only = RoleChecker(["manager"])


# 200 ms between jobs in a batch — gives the printer time to feed and
# avoids overrunning the network buffer on cheap switches.
BATCH_DELAY_S = 0.2


class BatchPrintRequest(BaseModel):
    product_ids: list[uuid.UUID] = Field(default_factory=list)
    copies: int = Field(default=1, ge=1, le=20)


def _label_config() -> dict:
    """Return the label-printer config, or raise 400 if it's disabled."""
    cfg = load_config()["label_printer"]
    if not cfg.get("enabled"):
        raise HTTPException(
            status_code=400,
            detail="Imprimante étiquettes désactivée dans les paramètres",
        )
    return cfg


def _validate_transport(cfg: dict) -> str:
    """Check the configured transport is usable; return its name.

    Fails fast with a 400 (operator-fixable) so a batch doesn't burn a
    per-item retry on a misconfiguration. Returns ``"cloud"`` or
    ``"network"``.
    """
    connection = (cfg.get("connection") or "network").strip().lower()
    if connection == "cloud":
        try:
            zebra_cloud.resolve_credentials(cfg)
        except zebra_cloud.CloudConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return "cloud"
    if connection == "bluetooth":
        # The server can't reach a BLE printer — the tablet prints client-side
        # via Web Bluetooth (GET /api/labels/{id}/zpl). Reject server-side
        # print attempts with a clear message rather than failing obscurely.
        raise HTTPException(
            status_code=400,
            detail="Mode Bluetooth : l'impression se fait depuis la tablette (Web Bluetooth), pas côté serveur",
        )
    if not (cfg.get("host") or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Adresse IP imprimante non configurée (ZEBRA_PRINTER_IP)",
        )
    return "network"


async def _dispatch_zpl(cfg: dict, zpl: str) -> str:
    """Send a ZPL job via the configured transport. Returns a target label.

    Raises ``zebra_printer.PrinterUnreachable`` (→ 502 at the call site) for
    transport failures; ``CloudPrintError`` is a subclass so the cloud path
    is covered by the same handler. Assumes ``_validate_transport`` already
    ran, so config is complete.
    """
    connection = (cfg.get("connection") or "network").strip().lower()
    if connection == "cloud":
        serial = await zebra_cloud.send_zpl(zpl, cfg)
        return f"cloud:{serial}"
    host = (cfg.get("host") or "").strip()
    port = int(cfg.get("port") or zebra_printer.DEFAULT_PORT)
    # Run the blocking socket send off the event loop.
    await asyncio.to_thread(zebra_printer.send_zpl, zpl, host=host, port=port)
    return host


async def _fetch_product(
    db: AsyncSession, product_id: uuid.UUID
) -> Product:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return product


@router.post(
    "/print/{product_id}",
    dependencies=[Depends(manager_only)],
)
async def print_label(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    copies: int = 1,
):
    """Print one product label on the Zebra.

    The printer is identified by the host stored in
    ``data/hardware.json`` (overridable via the ``ZEBRA_PRINTER_IP`` env
    var). A 3-second TCP timeout maps to a 502 if the printer is
    unreachable, with the underlying error in ``detail``.
    """
    product = await _fetch_product(db, product_id)
    cfg = _label_config()
    _validate_transport(cfg)
    # Édition étiquette = jeu de 2 tags : produit (code-barres/réf) + prix (logo).
    zpl = build_label_set_zpl(product_to_label_data(product), copies=max(copies, 1))
    try:
        target = await _dispatch_zpl(cfg, zpl)
    except zebra_printer.PrinterUnreachable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "status": "printed",
        "product_id": str(product.id),
        "printer_ip": target,
        "copies": max(copies, 1),
    }


@router.post(
    "/print/batch",
    dependencies=[Depends(manager_only)],
)
async def print_batch(
    payload: BatchPrintRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Print labels for several products in sequence.

    Iterates over ``product_ids``, sending one ZPL job per product
    (multiplied by ``copies``) with a 200 ms gap between jobs so the
    printer can feed and cut between labels.

    The response separates ``printed`` (successful product ids) from
    ``errors`` (failed product ids with reason) so the UI can show a
    partial-success toast rather than failing the whole operation.
    """
    if not payload.product_ids:
        raise HTTPException(status_code=400, detail="Aucun produit sélectionné")

    cfg = _label_config()
    _validate_transport(cfg)

    printed: list[str] = []
    errors: list[dict[str, str]] = []
    for idx, product_id in enumerate(payload.product_ids):
        try:
            product = await _fetch_product(db, product_id)
            zpl = build_label_set_zpl(
                product_to_label_data(product), copies=payload.copies
            )
            await _dispatch_zpl(cfg, zpl)
            printed.append(str(product.id))
        except HTTPException as exc:
            errors.append({"product_id": str(product_id), "error": exc.detail})
        except zebra_printer.PrinterUnreachable as exc:
            errors.append({"product_id": str(product_id), "error": str(exc)})
            # Bail out: if the printer is unreachable, the rest of the
            # batch will fail too. Don't waste 200 ms per item retrying.
            break
        except Exception as exc:  # noqa: BLE001 — defensive boundary
            errors.append({"product_id": str(product_id), "error": str(exc)})

        if idx < len(payload.product_ids) - 1:
            await asyncio.sleep(BATCH_DELAY_S)

    return {
        "printed": len(printed),
        "printed_ids": printed,
        "failed": len(errors),
        "errors": errors,
        "copies_per_product": payload.copies,
    }


@router.get(
    "/preview/{product_id}",
    dependencies=[Depends(manager_only)],
)
async def preview_label(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return a PNG preview of the label, rendered server-side by Labelary.

    The PNG matches the physical output bit-for-bit, so the operator can
    visually validate a label before sending it to the printer.
    """
    product = await _fetch_product(db, product_id)
    data = product_to_label_data(product)
    try:
        # Aperçu du JEU : tag produit (code-barres/réf) + tag prix (logo).
        product_png = await render_zpl_to_png(build_label_zpl(data))
        price_png = await render_zpl_to_png(build_price_label_zpl(data))
    except PreviewUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(
        content=_stack_pngs_vertically([product_png, price_png]),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


def _stack_pngs_vertically(
    pngs: list[bytes], *, gap: int = 14, bg: tuple = (246, 245, 241)
) -> bytes:
    """Empile verticalement plusieurs PNG (aperçu du jeu d'étiquettes)."""
    from io import BytesIO

    from PIL import Image

    imgs = [Image.open(BytesIO(p)).convert("RGB") for p in pngs if p]
    if not imgs:
        return b""
    if len(imgs) == 1:
        return pngs[0]
    width = max(im.width for im in imgs)
    height = sum(im.height for im in imgs) + gap * (len(imgs) - 1)
    canvas = Image.new("RGB", (width, height), bg)
    y = 0
    for im in imgs:
        canvas.paste(im, ((width - im.width) // 2, y))
        y += im.height + gap
    out = BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


@router.get(
    "/printer/status",
    dependencies=[Depends(manager_only)],
)
async def printer_status():
    """Cheap online/offline probe used by the UI status pill.

    Doesn't print anything — just opens and closes a TCP connection on
    port 9100 within 3 s. Returns the measured latency so the UI can
    flag a slow network.
    """
    cfg = load_config()["label_printer"]
    enabled = bool(cfg.get("enabled"))
    connection = (cfg.get("connection") or "network").strip().lower()

    if connection == "bluetooth":
        # No server-side probe possible — the BLE link lives on the tablet.
        # Report "ready when enabled"; the pairing happens client-side.
        name = (cfg.get("bt_device_name") or "").strip()
        return {
            "online": enabled,
            "ip": name or "Bluetooth",
            "port": None,
            "latency_ms": None,
            "enabled": enabled,
            "connection": "bluetooth",
            "detail": "Appairage depuis la tablette (Web Bluetooth)",
            "model": cfg.get("model", "Zebra ZD421d"),
        }

    if connection == "cloud":
        # No cheap live probe for the Weblink relay — report whether the
        # cloud credentials are complete. The UI pill reflects "configured",
        # with the detail clarifying it's not a live link check.
        try:
            _, _, serial, _ = zebra_cloud.resolve_credentials(cfg)
            configured, detail = True, None
        except zebra_cloud.CloudConfigError as exc:
            serial, configured, detail = (cfg.get("cloud_serial") or "?"), False, str(exc)
        return {
            "online": enabled and configured,
            "ip": f"cloud:{serial}",
            "port": None,
            "latency_ms": None,
            "enabled": enabled,
            "connection": "cloud",
            "detail": detail or "Mode cloud (Weblink) — état basé sur la config, pas un ping live",
            "model": cfg.get("model", "Zebra ZD421d"),
        }

    host = (cfg.get("host") or "").strip()
    port = int(cfg.get("port") or zebra_printer.DEFAULT_PORT)
    snapshot = zebra_printer.ping(host=host, port=port)
    return {
        "online": snapshot.online,
        "ip": snapshot.ip,
        "port": snapshot.port,
        "latency_ms": snapshot.latency_ms,
        "enabled": enabled,
        "connection": "network",
        "detail": snapshot.detail,
        "model": cfg.get("model", "Zebra ZD421d"),
    }


@router.get(
    "/sheet",
    dependencies=[Depends(manager_only)],
)
async def labels_a4_sheet(
    db: Annotated[AsyncSession, Depends(get_db)],
    ids: str = Query(..., description="Liste d'IDs produit séparés par des virgules"),
    cols: int = Query(2, ge=1, le=4),
    rows: int = Query(4, ge=1, le=8),
):
    """A4 fallback when the Zebra is unavailable.

    Renders each label by passing its ZPL through Labelary's PNG endpoint
    — same renderer as the per-product preview, so the printed A4
    matches the Zebra output **pixel-for-pixel**, including font sizes,
    barcode style, separator placement, and date formatting. The PNGs
    are embedded as base64 in an A4-sized HTML grid that auto-prints.

    Why not re-implement the layout in CSS : the brief specifies the
    label content & geometry once, and the ZPL template is the single
    source of truth. Recoding it in CSS would drift over time — every
    tweak to ``zebra_zpl.py`` would have to be mirrored here.
    """
    raw_ids = [p.strip() for p in ids.split(",") if p.strip()]
    if not raw_ids:
        raise HTTPException(status_code=400, detail="Aucun produit fourni")
    try:
        uuids = [uuid.UUID(p) for p in raw_ids]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"ID invalide : {exc}") from exc
    if len(uuids) > 24:  # 24 labels = up to 3 A4 pages at 8 per page
        raise HTTPException(status_code=400, detail="Maximum 24 étiquettes par planche")

    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id.in_(uuids))
    )
    products = result.scalars().all()
    # Preserve the requested order — DB returns the rows unsorted
    by_id = {p.id: p for p in products}
    ordered = [by_id[uid] for uid in uuids if uid in by_id]
    if not ordered:
        raise HTTPException(status_code=404, detail="Aucun produit trouvé")

    # Render the whole batch as ONE multi-page PDF via Labelary — each
    # page = one Vintiz label. Two wins vs the previous "N PNGs assembled
    # in HTML" approach :
    #
    #   1. 1 HTTP roundtrip to Labelary instead of N (latency, rate limit)
    #   2. The operator can print the PDF directly on their A4 printer,
    #      cutting along the page boundaries instead of approximating
    #      80×120 mm cells in CSS that never quite matched the Zebra.
    #
    # The CSS grid path is kept as a fallback when Labelary is offline
    # (the PDF call raises PreviewUnavailable) — we fall back to a
    # one-PNG-per-cell HTML page so the cashier still gets *something*
    # printable.
    combined_zpl = "\n".join(
        build_label_zpl(product_to_label_data(p)) for p in ordered
    )
    try:
        pdf_bytes = await render_zpl_to_pdf(combined_zpl)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f'inline; filename="etiquettes-{len(ordered)}.pdf"',
            },
        )
    except PreviewUnavailable as exc:
        logger.warning("Labelary PDF batch failed, falling back to PNG grid: %s", exc)

    async def _png_for(p: Product) -> str:
        zpl = build_label_zpl(product_to_label_data(p))
        try:
            png = await render_zpl_to_png(zpl)
            return base64.b64encode(png).decode("ascii")
        except PreviewUnavailable as exc:
            logger.warning("Labelary failed for product %s: %s", p.id, exc)
            return ""

    pngs = await asyncio.gather(*[_png_for(p) for p in ordered])
    html_doc = _render_a4_sheet_from_pngs(pngs, cols=cols, rows=rows)
    return HTMLResponse(content=html_doc, headers={"Cache-Control": "no-store"})


@router.post(
    "/test-print",
    dependencies=[Depends(manager_only)],
    status_code=status.HTTP_200_OK,
)
async def test_print():
    """Print a small test label so the operator can validate the wiring.

    Used by the Hardware settings tab when changing the printer IP.
    """
    cfg = _label_config()
    _validate_transport(cfg)
    try:
        target = await _dispatch_zpl(cfg, zebra_printer.build_test_label_zpl())
    except zebra_printer.PrinterUnreachable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "printed", "printer_ip": target}


@router.get(
    "/{product_id}/zpl",
    dependencies=[Depends(manager_only)],
)
async def product_label_zpl(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    copies: int = 1,
):
    """Return the raw ZPL for a product label (text/plain).

    Used by the **Bluetooth** transport: the server can't reach a BLE
    printer, so the cashier tablet fetches this ZPL and writes it to the
    Zebra's BLE Parser service via Web Bluetooth. Mirrors the receipt
    printer's ``/escpos`` endpoint for the WebUSB path.
    """
    product = await _fetch_product(db, product_id)
    zpl = build_label_set_zpl(product_to_label_data(product), copies=max(copies, 1))
    return Response(
        content=zpl,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------------------
# A4 fallback sheet renderer
# ---------------------------------------------------------------------------


def _render_a4_sheet_from_pngs(
    pngs_b64: list[str], *, cols: int, rows: int,
) -> str:
    """Wrap base64-encoded label PNGs in an A4-sized HTML page.

    The PNGs come from Labelary so each cell is a pixel-perfect copy of
    what the Zebra physically prints — same template, same fonts, same
    barcode style. The A4 grid just lays them out for cutting.
    """
    per_page = cols * rows
    cells = []
    for png_b64 in pngs_b64:
        if png_b64:
            cells.append(
                f'<div class="cell">'
                f'  <img alt="Étiquette" src="data:image/png;base64,{png_b64}" />'
                f'</div>'
            )
        else:
            # Labelary failed for this product — print a clear "missing"
            # cell rather than silently skip; the cashier can re-print
            # just that one once Labelary is back.
            cells.append(
                '<div class="cell cell--error">'
                '<span>Aperçu indisponible — relancez plus tard</span>'
                '</div>'
            )
    cells_html = "\n".join(cells)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Étiquettes Vintiz — planche A4</title>
<style>
  @page {{ size: A4; margin: 8mm; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0; color: #0E0E0C; background: #fff;
  }}
  .toolbar {{
    background: #0B7A6A; color: #fff;
    padding: 12px 16px; display: flex; gap: 12px; align-items: center;
    font-size: 14px;
  }}
  .toolbar button {{
    background: #fff; color: #0B7A6A; border: 0;
    padding: 8px 16px; border-radius: 8px; font-weight: 600;
    cursor: pointer;
  }}
  .sheet {{
    display: grid;
    grid-template-columns: repeat({cols}, 1fr);
    grid-auto-rows: 1fr;
    gap: 3mm;
    padding: 4mm;
  }}
  .cell {{
    border: 1px dashed #d5d3cc;
    padding: 2mm;
    display: flex; align-items: center; justify-content: center;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .cell img {{
    max-width: 100%; max-height: 100%;
    object-fit: contain;
    display: block;
  }}
  .cell--error {{
    color: #b00; font-size: 10pt; text-align: center;
  }}
  @media print {{
    .toolbar {{ display: none !important; }}
    .sheet {{ padding: 0; gap: 2mm; }}
    .cell {{ border: none; }}
  }}
</style>
</head>
<body>
  <div class="toolbar">
    <strong>Planche A4 — {len(pngs_b64)} étiquette{"s" if len(pngs_b64) > 1 else ""}</strong>
    <span style="opacity: 0.8;">({cols}×{rows} = {per_page} par page)</span>
    <span style="flex: 1"></span>
    <button onclick="window.print()" type="button">Imprimer</button>
    <button onclick="window.close()" type="button" style="background:#fff;color:#4A4A47;">Fermer</button>
  </div>
  <div class="sheet">
{cells_html}
  </div>
  <script>
    // Wait for all <img> to decode before triggering the print dialog,
    // otherwise the operator sees a half-rendered preview.
    Promise.all(
      Array.from(document.images).map((img) =>
        img.complete ? Promise.resolve() : new Promise((r) => {{
          img.addEventListener('load', r);
          img.addEventListener('error', r);
        }})
      ),
    ).then(function () {{ setTimeout(function () {{ window.print(); }}, 200); }});
  </script>
</body>
</html>"""
