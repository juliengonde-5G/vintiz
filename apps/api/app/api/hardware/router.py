"""Hardware peripherals API — receipt printer, label printer, cash drawer.

Exposes endpoints for the back-office "Materiel" settings tab:

* ``GET  /hardware/config``         — read the persisted hardware config
* ``PUT  /hardware/config``         — update hardware config (merge)
* ``GET  /hardware/compatibility``  — static matrix of supported peripherals
* ``POST /hardware/receipt/test``   — send a test ticket (MUNBYN)
* ``POST /hardware/drawer/kick``    — pulse the Safescan drawer
* ``POST /hardware/label/test``     — send a test label (Zebra ZD421d)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_user
from app.models.user import User
from app.services import escpos_service
from app.services.hardware_config import load_config, save_config

router = APIRouter(prefix="/hardware", tags=["hardware"])


class HardwareConfigUpdate(BaseModel):
    receipt_printer: dict[str, Any] | None = None
    cash_drawer: dict[str, Any] | None = None
    label_printer: dict[str, Any] | None = None
    barcode_scanner: dict[str, Any] | None = None
    payment_terminal: dict[str, Any] | None = None


COMPATIBILITY_MATRIX = [
    {
        "category": "receipt_printer",
        "label": "Imprimante de recus",
        "model": "MUNBYN 047P-WiFi",
        "connection": "WiFi / USB (ESC/POS, 80 mm)",
        "supported": True,
        "notes": "Impression des tickets NF525 et ouverture du tiroir-caisse via ESC/POS (TCP 9100).",
    },
    {
        "category": "cash_drawer",
        "label": "Tiroir-caisse",
        "model": "Safescan SD-4141",
        "connection": "RJ-12 (via imprimante)",
        "supported": True,
        "notes": "Ouverture automatique a l'encaissement especes ou au click-in POS.",
    },
    {
        "category": "barcode_scanner",
        "label": "Douchette code-barres",
        "model": "Inateck BCST-35",
        "connection": "Bluetooth / USB dongle (HID)",
        "supported": True,
        "notes": "Mode clavier HID : scan vers le champ POS, ajout auto au panier.",
    },
    {
        "category": "label_printer",
        "label": "Imprimante d'etiquettes",
        "model": "Zebra ZD421d",
        "connection": "Ethernet local (ZPL TCP 9100) ou cloud (Weblink + SendFileToPrinter)",
        "supported": True,
        "notes": "Etiquettes Vintiz 80x120 mm (thermique direct 203 dpi). Apercu via Labelary. Mode cloud : l'imprimante se connecte a Zebra Data Services, le backend pousse le ZPL par API (utile quand l'API tourne hors site).",
    },
    {
        "category": "payment_terminal",
        "label": "Terminal de paiement",
        "model": "SumUp",
        "connection": "Cloud (API SumUp)",
        "supported": True,
        "notes": "Deja integre : POST /api/pos/payments/cb/initiate.",
    },
]


@router.get("/compatibility")
async def get_compatibility(current_user: User = Depends(get_current_user)):
    """Return the static matrix of supported hardware."""
    return {"items": COMPATIBILITY_MATRIX}


def _mask_label_secrets(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the config with the Zebra cloud API key masked.

    The key is a secret persisted in ``hardware.json``; we never echo it
    back to the browser. Instead we expose a boolean + last-4 hint so the
    UI can show "configurée" without revealing the value.
    """
    lp = dict(cfg.get("label_printer") or {})
    key = lp.get("cloud_api_key") or ""
    lp["cloud_api_key"] = ""
    lp["cloud_api_key_set"] = bool(key)
    lp["cloud_api_key_hint"] = key[-4:] if key else ""
    out = dict(cfg)
    out["label_printer"] = lp
    return out


@router.get("/config")
async def get_config(current_user: User = Depends(get_current_user)):
    return _mask_label_secrets(load_config())


@router.put("/config")
async def update_config(
    update: HardwareConfigUpdate,
    current_user: User = Depends(get_current_user),
):
    payload = {k: v for k, v in update.model_dump(exclude_none=True).items()}
    lp = payload.get("label_printer")
    if isinstance(lp, dict):
        # Drop the read-only mask helpers if the UI echoes them back.
        lp.pop("cloud_api_key_set", None)
        lp.pop("cloud_api_key_hint", None)
        # A blank api key means "leave the stored one untouched": never let
        # an empty field (or the masked placeholder) wipe the saved secret.
        if not (lp.get("cloud_api_key") or "").strip():
            lp.pop("cloud_api_key", None)
    save_config(payload)
    return _mask_label_secrets(load_config())


class TestPrintRequest(BaseModel):
    host: str | None = None
    port: int | None = None


@router.post("/receipt/test")
async def receipt_test(
    req: TestPrintRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a test ticket to the MUNBYN receipt printer."""
    cfg = load_config()["receipt_printer"]
    host = req.host or cfg.get("host") or ""
    port = int(req.port or cfg.get("port") or 9100)
    if not host:
        raise HTTPException(status_code=400, detail="Adresse IP de l'imprimante non configuree")
    try:
        escpos_service.print_test(host, port, width=int(cfg.get("width_chars") or 42))
    except Exception as exc:  # noqa: BLE001 — surface hardware error
        raise HTTPException(status_code=502, detail=f"Imprimante injoignable : {exc}") from exc
    return {"success": True, "host": host, "port": port}


@router.get("/receipt/test-escpos")
async def receipt_test_escpos(
    current_user: User = Depends(get_current_user),
):
    """Return raw ESC/POS bytes for a test ticket.

    Used by the front-end's WebUSB flow so the "Imprimer ticket de test"
    button works in USB mode without going through the backend TCP path
    — the bytes are streamed straight to the MUNBYN over USB-OTG.
    """
    from fastapi.responses import Response

    cfg = load_config()["receipt_printer"]
    payload = escpos_service.build_test_ticket(width=int(cfg.get("width_chars") or 42))
    return Response(
        content=bytes(payload),
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/drawer/kick")
async def drawer_kick(
    req: TestPrintRequest,
    current_user: User = Depends(get_current_user),
):
    """Kick open the Safescan cash drawer via the receipt printer (network path).

    USB-mode callers should use ``GET /api/hardware/drawer/kick-escpos``
    instead — it returns the same ``ESC p`` bytes for the front to send
    over WebUSB.
    """
    cfg = load_config()
    rp = cfg["receipt_printer"]
    drawer = cfg["cash_drawer"]
    host = req.host or rp.get("host") or ""
    port = int(req.port or rp.get("port") or 9100)
    if not host:
        raise HTTPException(status_code=400, detail="Imprimante non configuree : impossible d'ouvrir le tiroir")
    try:
        escpos_service.kick_drawer(
            host,
            port,
            pin=int(drawer.get("kick_pin") or 0),
            on_time=int(drawer.get("on_time_ms") or 50),
            off_time=int(drawer.get("off_time_ms") or 250),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Tiroir injoignable : {exc}") from exc
    return {"success": True}


@router.get("/drawer/kick-escpos")
async def drawer_kick_escpos(
    current_user: User = Depends(get_current_user),
):
    """Return the raw ESC/POS pulse bytes that open the cash drawer.

    Used by the WebUSB path on the cashier tablet : the front fetches
    these bytes and pushes them to the MUNBYN over USB-OTG, which
    bridges the pulse to the Safescan drawer via the RJ-12 port.

    Without this endpoint, the test button and the cash-sale auto-kick
    silently fail in USB mode because the legacy network endpoint
    opens a TCP socket that doesn't exist on the tablet.
    """
    from fastapi.responses import Response

    drawer = load_config()["cash_drawer"]
    payload = escpos_service.build_drawer_kick(
        pin=int(drawer.get("kick_pin") or 0),
        on_time=int(drawer.get("on_time_ms") or 50),
        off_time=int(drawer.get("off_time_ms") or 250),
    )
    return Response(
        content=bytes(payload),
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/label/test")
async def label_test(
    req: TestPrintRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a test ZPL label to the Zebra ZD421d.

    Kept under /hardware/label/test for legacy compatibility with the
    settings UI, but the actual driver is now ``zebra_printer``. The
    canonical endpoint going forward is ``POST /api/labels/test-print``.

    Honours the configured transport: in ``cloud`` mode the test label is
    pushed via Zebra's SendFileToPrinter API; the host/port override only
    applies to the local TCP path.
    """
    from app.services import zebra_cloud, zebra_printer

    cfg = load_config()["label_printer"]
    connection = (cfg.get("connection") or "network").strip().lower()

    if connection == "cloud":
        try:
            serial = await zebra_cloud.send_zpl(zebra_printer.build_test_label_zpl(), cfg)
        except zebra_cloud.CloudConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except zebra_printer.PrinterUnreachable as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"success": True, "target": f"cloud:{serial}"}

    host = req.host or cfg.get("host") or ""
    port = int(req.port or cfg.get("port") or zebra_printer.DEFAULT_PORT)
    if not host:
        raise HTTPException(
            status_code=400, detail="Imprimante étiquettes non configurée"
        )
    try:
        zebra_printer.send_test_label(host=host, port=port)
    except zebra_printer.PrinterUnreachable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"success": True, "host": host, "port": port}
