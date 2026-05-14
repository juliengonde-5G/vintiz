"""Label printing endpoints — Zebra ZD421d over ZPL.

Replaces the previous SATO/SBPL stack. Single source of truth for both
the unitary print (admin clicks the printer icon on a row) and the batch
print (admin selects N products + clicks "Imprimer les étiquettes").

All endpoints are manager-only.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker
from app.models.product import Product
from app.services import zebra_printer
from app.services.hardware_config import load_config
from app.services.label_preview import PreviewUnavailable, render_zpl_to_png
from app.services.zebra_zpl import build_label_zpl, product_to_label_data

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
