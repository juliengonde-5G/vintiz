"""Label printing endpoints — Zebra ZD421d over ZPL.

Replaces the previous SATO/SBPL stack. Single source of truth for both
the unitary print (admin clicks the printer icon on a row) and the batch
print (admin selects N products + clicks "Imprimer les étiquettes").

All endpoints are manager-only.
"""

from __future__ import annotations

import asyncio
import html
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import RoleChecker
from app.models.product import Product
from app.services import zebra_printer
from app.services.hardware_config import load_config
from app.services.label_preview import PreviewUnavailable, render_zpl_to_png
from app.services.zebra_zpl import (
    MARKDOWN_DAYS,
    LabelData,
    build_label_zpl,
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


def _resolve_printer() -> tuple[str, int]:
    """Read host/port from the persisted hardware config.

    Returns the tuple ready to pass to ``zebra_printer.send_zpl``.
    Raises 400 if the printer is disabled or its IP isn't set — the UI
    should be showing the offline pill in that state anyway.
    """
    cfg = load_config()["label_printer"]
    if not cfg.get("enabled"):
        raise HTTPException(
            status_code=400,
            detail="Imprimante étiquettes désactivée dans les paramètres",
        )
    host = (cfg.get("host") or "").strip()
    port = int(cfg.get("port") or zebra_printer.DEFAULT_PORT)
    if not host:
        raise HTTPException(
            status_code=400,
            detail="Adresse IP imprimante non configurée (ZEBRA_PRINTER_IP)",
        )
    return host, port


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
    host, port = _resolve_printer()
    zpl = build_label_zpl(product_to_label_data(product), copies=max(copies, 1))
    try:
        zebra_printer.send_zpl(zpl, host=host, port=port)
    except zebra_printer.PrinterUnreachable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "status": "printed",
        "product_id": str(product.id),
        "printer_ip": host,
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

    host, port = _resolve_printer()

    printed: list[str] = []
    errors: list[dict[str, str]] = []
    for idx, product_id in enumerate(payload.product_ids):
        try:
            product = await _fetch_product(db, product_id)
            zpl = build_label_zpl(
                product_to_label_data(product), copies=payload.copies
            )
            zebra_printer.send_zpl(zpl, host=host, port=port)
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
    zpl = build_label_zpl(product_to_label_data(product))
    try:
        png = await render_zpl_to_png(zpl)
    except PreviewUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


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
    host = (cfg.get("host") or "").strip()
    port = int(cfg.get("port") or zebra_printer.DEFAULT_PORT)
    enabled = bool(cfg.get("enabled"))
    snapshot = zebra_printer.ping(host=host, port=port)
    return {
        "online": snapshot.online,
        "ip": snapshot.ip,
        "port": snapshot.port,
        "latency_ms": snapshot.latency_ms,
        "enabled": enabled,
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

    Renders the same product data as the ZPL template but as an HTML page
    sized to A4 with a CSS grid. Each cell is the size of a Vintiz label
    (default 2×4 = 8 labels per page). The operator opens the page in a
    new tab and uses Ctrl+P (or the device's print menu) to send it to
    a standard A4 printer; an embedded ``onload=window.print()`` triggers
    the dialog automatically. The user then cuts the labels manually or
    uses pre-cut Avery-style sheets.
    """
    raw_ids = [p.strip() for p in ids.split(",") if p.strip()]
    if not raw_ids:
        raise HTTPException(status_code=400, detail="Aucun produit fourni")
    try:
        uuids = [uuid.UUID(p) for p in raw_ids]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"ID invalide : {exc}") from exc
    if len(uuids) > 96:  # 12 A4 pages of 8 labels — generous safety stop
        raise HTTPException(status_code=400, detail="Maximum 96 étiquettes par planche")

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

    html_doc = _render_a4_sheet(ordered, cols=cols, rows=rows)
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
    host, port = _resolve_printer()
    try:
        zebra_printer.send_test_label(host=host, port=port)
    except zebra_printer.PrinterUnreachable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "printed", "printer_ip": host}


# ---------------------------------------------------------------------------
# A4 fallback sheet renderer
# ---------------------------------------------------------------------------


def _fmt_price(amount: float) -> str:
    return f"{amount:.2f} €".replace(".", ",")


def _fmt_date(dt) -> str:
    return dt.strftime("%d/%m/%Y") if dt else "—"


def _render_label_cell(data: LabelData) -> str:
    """Render a single label as inline HTML.

    Mirrors the ZPL template layout (name, category·size, condition,
    price XXL, barcode placeholder, dates) so a printed A4 cell looks
    visually similar to a Zebra label. The barcode is rendered as a
    Code 128 SVG via the in-page ``JsBarcode`` script.
    """
    name = html.escape(data.product_name or "Article")[:60]
    category = html.escape(data.category or "Article")
    size = html.escape(data.size or "")
    condition = html.escape(data.condition or "Bon état")
    price = html.escape(_fmt_price(float(data.sale_price)))
    ref = html.escape(data.barcode or "VTZ-NOREF")
    shelf = _fmt_date(data.shelf_date)
    markdown = _fmt_date(
        (data.shelf_date + timedelta(days=MARKDOWN_DAYS)) if data.shelf_date else None
    )
    category_line = f"{category} • T.{size}" if size else category
    return (
        '<div class="cell">'
        '  <div class="brand">VINTIZ</div>'
        '  <div class="sep"></div>'
        f'  <div class="name">{name}</div>'
        f'  <div class="cat">{category_line}</div>'
        f'  <div class="cond">{condition}</div>'
        f'  <div class="price">{price}</div>'
        '  <div class="sep"></div>'
        f'  <svg class="barcode" jsbarcode-format="CODE128"'
        f'       jsbarcode-value="{ref}" jsbarcode-displayvalue="true"'
        '        jsbarcode-fontsize="11" jsbarcode-height="40"></svg>'
        f'  <div class="ref">Réf : {ref}</div>'
        f'  <div class="date">Rayon depuis : {shelf}</div>'
        f'  <div class="date">Démarque le : {markdown}</div>'
        '</div>'
    )


def _render_a4_sheet(products: list, *, cols: int, rows: int) -> str:
    """Wrap N label cells in an A4-sized HTML page ready to ``window.print()``.

    Uses ``@page A4`` + a CSS grid to lay out the cells. ``JsBarcode`` is
    loaded from a CDN to render Code 128 barcodes from data attributes —
    no server-side image generation needed.
    """
    cells = "\n".join(_render_label_cell(product_to_label_data(p)) for p in products)
    per_page = cols * rows
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
    padding: 4mm;
    display: flex; flex-direction: column;
    text-align: center;
    page-break-inside: avoid;
    break-inside: avoid;
    aspect-ratio: 1 / 1.15;
  }}
  .brand {{
    font-family: Georgia, "Fraunces", serif;
    font-weight: 700; font-size: 22pt; letter-spacing: 0.04em;
    color: #0B7A6A;
  }}
  .sep {{
    height: 1px; background: #0E0E0C; margin: 4px 12px;
  }}
  .name {{
    font-weight: 600; font-size: 12pt; line-height: 1.15;
    margin-top: 4px; min-height: 30px;
  }}
  .cat {{ font-size: 10pt; color: #4A4A47; margin-top: 2px; }}
  .cond {{ font-size: 9pt; color: #8B8B86; margin-top: 1px; }}
  .price {{
    font-weight: 700; font-size: 32pt; color: #0E0E0C;
    margin: 6px 0; line-height: 1;
  }}
  .barcode {{ display: block; margin: 0 auto; max-width: 80%; height: 50px; }}
  .ref {{ font-family: ui-monospace, monospace; font-size: 9pt; margin-top: 2px; }}
  .date {{ font-size: 8pt; color: #4A4A47; margin-top: 1px; }}
  @media print {{
    .toolbar {{ display: none !important; }}
    .sheet {{ padding: 0; gap: 2mm; }}
  }}
</style>
</head>
<body>
  <div class="toolbar">
    <strong>Planche A4 — {len(products)} étiquette{"s" if len(products) > 1 else ""}</strong>
    <span style="opacity: 0.8;">({cols}×{rows} = {per_page} par page)</span>
    <span style="flex: 1"></span>
    <button onclick="window.print()" type="button">Imprimer</button>
    <button onclick="window.close()" type="button" style="background:#fff;color:#4A4A47;">Fermer</button>
  </div>
  <div class="sheet">
{cells}
  </div>
  <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.6/dist/JsBarcode.all.min.js"></script>
  <script>
    document.addEventListener('DOMContentLoaded', function () {{
      try {{ JsBarcode('.barcode').init(); }} catch (e) {{}}
      // Auto-trigger print dialog after barcodes render
      setTimeout(function () {{ window.print(); }}, 250);
    }});
  </script>
</body>
</html>"""
