"""Label printing endpoints — server-rendered raster + Raspberry Pi queue.

The Vintiz API runs off-site (cloud) and can't reach a printer on the boutique
LAN, so it no longer talks to a printer directly. Manager actions enqueue a
:class:`LabelPrintJob`; the in-store Raspberry Pi agent polls the ``/agent/*``
endpoints (outbound only), prints the server-rendered PDF on its CUPS printer,
and acks the result.

Two audiences:
  * manager-only endpoints (JWT) — preview, enqueue (single/batch/test), status,
    and an A4 fallback sheet for when the Pi is down;
  * agent endpoints (``X-Agent-Token`` header) — claim jobs + ack.
"""

from __future__ import annotations

import base64
import logging
import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import RoleChecker
from app.models.product import Product
from app.services import label_queue
from app.services.hardware_config import load_config
from app.services.label_render import (
    label_snapshot,
    product_to_label_data,
    render_label_pdf,
    render_label_png,
)

logger = logging.getLogger("vintiz")

router = APIRouter(prefix="/labels", tags=["labels"])

manager_only = RoleChecker(["manager"])


class BatchPrintRequest(BaseModel):
    product_ids: list[uuid.UUID] = Field(default_factory=list)
    copies: int = Field(default=1, ge=1, le=20)


class AckRequest(BaseModel):
    success: bool = True
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _label_enabled() -> None:
    """Raise 400 when the label printer is switched off in the settings."""
    cfg = load_config()["label_printer"]
    if not cfg.get("enabled"):
        raise HTTPException(
            status_code=400,
            detail="Imprimante étiquettes désactivée dans les paramètres",
        )


async def _fetch_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = (
        await db.execute(select(Product).where(Product.id == product_id))
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return product


async def require_agent_token(
    x_agent_token: Annotated[str | None, Header()] = None,
) -> None:
    """Authenticate the Raspberry Pi agent via the shared ``X-Agent-Token``.

    503 when the server has no token configured (agent disabled), 401 on a
    missing/mismatched token. The comparison is constant-time.
    """
    expected = settings.RPI_AGENT_TOKEN
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Agent d'impression désactivé (RPI_AGENT_TOKEN non configuré)",
        )
    if not x_agent_token or not secrets.compare_digest(x_agent_token, expected):
        raise HTTPException(status_code=401, detail="Jeton agent invalide")


# ---------------------------------------------------------------------------
# Manager endpoints
# ---------------------------------------------------------------------------


@router.post("/print/{product_id}", status_code=status.HTTP_202_ACCEPTED)
async def print_label(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    manager: Annotated[object, Depends(manager_only)],
    copies: int = 1,
):
    """Queue one product label for the Raspberry Pi agent to print."""
    _label_enabled()
    product = await _fetch_product(db, product_id)
    job = await label_queue.enqueue_product(
        db, product, copies=max(1, copies), user_id=getattr(manager, "id", None)
    )
    return {
        "status": "queued",
        "job_id": str(job.id),
        "product_id": str(product.id),
        "copies": job.copies,
    }


@router.post("/print/batch", status_code=status.HTTP_202_ACCEPTED)
async def print_batch(
    payload: BatchPrintRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    manager: Annotated[object, Depends(manager_only)],
):
    """Queue labels for several products. Unknown ids are reported, not fatal."""
    if not payload.product_ids:
        raise HTTPException(status_code=400, detail="Aucun produit sélectionné")
    _label_enabled()

    queued: list[str] = []
    errors: list[dict[str, str]] = []
    for product_id in payload.product_ids:
        product = (
            await db.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
        if product is None:
            errors.append({"product_id": str(product_id), "error": "Produit introuvable"})
            continue
        job = await label_queue.enqueue_product(
            db, product, copies=payload.copies, user_id=getattr(manager, "id", None)
        )
        queued.append(str(job.id))

    return {
        "queued": len(queued),
        "job_ids": queued,
        "failed": len(errors),
        "errors": errors,
        "copies_per_product": payload.copies,
    }


@router.post("/test-print", status_code=status.HTTP_202_ACCEPTED)
async def test_print(
    db: Annotated[AsyncSession, Depends(get_db)],
    manager: Annotated[object, Depends(manager_only)],
):
    """Queue a small test label so the operator can validate the wiring."""
    _label_enabled()
    job = await label_queue.enqueue_test(db, user_id=getattr(manager, "id", None))
    return {"status": "queued", "job_id": str(job.id)}


@router.get("/preview/{product_id}", dependencies=[Depends(manager_only)])
async def preview_label(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return a PNG preview rendered with the same layout the Pi will print."""
    product = await _fetch_product(db, product_id)
    png = render_label_png(label_snapshot(product_to_label_data(product)))
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/printer/status", dependencies=[Depends(manager_only)])
async def printer_status(db: Annotated[AsyncSession, Depends(get_db)]):
    """Agent health for the UI status pill: online + queue depth.

    "online" means the Pi has polled within ``RPI_AGENT_STALE_SECONDS``. No
    socket is opened — the agent dials out to us, never the reverse.
    """
    cfg = load_config()["label_printer"]
    q = await label_queue.queue_status(db, stale_seconds=settings.RPI_AGENT_STALE_SECONDS)
    return {
        "enabled": bool(cfg.get("enabled")),
        "agent_configured": bool(settings.RPI_AGENT_TOKEN),
        "online": q["online"],
        "last_seen": q["last_seen"],
        "pending": q["pending"],
        "printing": q["printing"],
        "errors": q["error"],
        "model": cfg.get("model", "Raspberry Pi · CUPS"),
        "cups_printer_name": cfg.get("cups_printer_name", ""),
    }


@router.get("/sheet", dependencies=[Depends(manager_only)])
async def labels_a4_sheet(
    db: Annotated[AsyncSession, Depends(get_db)],
    ids: str = Query(..., description="Liste d'IDs produit séparés par des virgules"),
    cols: int = Query(2, ge=1, le=4),
    rows: int = Query(4, ge=1, le=8),
):
    """Offline fallback when the Pi is down: an A4 HTML sheet of label PNGs.

    Each cell is the exact same render the Pi prints (one renderer, one source
    of truth), laid out for cutting and auto-printed via ``window.print()``.
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

    result = await db.execute(select(Product).where(Product.id.in_(uuids)))
    by_id = {p.id: p for p in result.scalars().all()}
    ordered = [by_id[uid] for uid in uuids if uid in by_id]
    if not ordered:
        raise HTTPException(status_code=404, detail="Aucun produit trouvé")

    pngs = [
        base64.b64encode(
            render_label_png(label_snapshot(product_to_label_data(p)))
        ).decode("ascii")
        for p in ordered
    ]
    html_doc = _render_a4_sheet_from_pngs(pngs, cols=cols, rows=rows)
    return HTMLResponse(content=html_doc, headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------------------
# Agent endpoints (Raspberry Pi) — token-authenticated, no JWT
# ---------------------------------------------------------------------------


@router.get("/agent/jobs/next", dependencies=[Depends(require_agent_token)])
async def agent_next_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    max: int = Query(5, ge=1, le=20),
):
    """Claim the next pending jobs and return them with a print-ready PDF.

    Each job carries a base64 PDF (page sized exactly 25×52 mm @ 203 dpi) so
    the agent prints at 100 % scale via ``lp``. Polling also refreshes the
    agent heartbeat, so an empty response still marks the printer online.
    """
    jobs = await label_queue.claim_next(
        db, limit=max, stale_seconds=settings.RPI_AGENT_STALE_SECONDS
    )
    return {
        "jobs": [
            {
                "id": str(job.id),
                "job_type": job.job_type,
                "product_id": str(job.product_id) if job.product_id else None,
                "copies": job.copies,
                "ref": (job.payload or {}).get("ref"),
                "format": "pdf",
                "content_b64": base64.b64encode(
                    render_label_pdf(job.payload or {}, copies=job.copies)
                ).decode("ascii"),
            }
            for job in jobs
        ]
    }


@router.post("/agent/jobs/{job_id}/ack", dependencies=[Depends(require_agent_token)])
async def agent_ack_job(
    job_id: uuid.UUID,
    payload: AckRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Report the print result for a claimed job."""
    job = await label_queue.ack(db, job_id, success=payload.success, error=payload.error)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable")
    return {"id": str(job.id), "status": job.status}


# ---------------------------------------------------------------------------
# A4 fallback sheet renderer
# ---------------------------------------------------------------------------


def _render_a4_sheet_from_pngs(
    pngs_b64: list[str], *, cols: int, rows: int,
) -> str:
    """Wrap label PNGs in an A4-sized HTML page that auto-prints."""
    per_page = cols * rows
    cells = "\n".join(
        f'<div class="cell"><img alt="Étiquette" src="data:image/png;base64,{b64}" /></div>'
        for b64 in pngs_b64
    )
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
    padding: 8px 16px; border-radius: 8px; font-weight: 600; cursor: pointer;
  }}
  .sheet {{
    display: grid;
    grid-template-columns: repeat({cols}, 1fr);
    grid-auto-rows: 1fr; gap: 3mm; padding: 4mm;
  }}
  .cell {{
    border: 1px dashed #d5d3cc; padding: 2mm;
    display: flex; align-items: center; justify-content: center;
    page-break-inside: avoid; break-inside: avoid;
  }}
  .cell img {{ max-width: 100%; max-height: 100%; object-fit: contain; display: block; }}
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
{cells}
  </div>
  <script>
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
