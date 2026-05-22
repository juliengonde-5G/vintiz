"""Cloud printing for the Zebra ZD421d via Weblink + SendFileToPrinter.

Vintiz runs the API off-site (cloud), while the label printer sits on the
boutique LAN behind the router's NAT. Neither can open a socket to the
other, so the local-TCP path (``zebra_printer.send_zpl`` on port 9100) only
works when the API and the printer share a network.

Zebra's native fix for this topology is **Weblink**: the printer dials
*outbound* to Zebra Data Services over TLS and keeps the connection open.
We then push ZPL by calling Zebra's ``SendFileToPrinter`` REST API, which
relays the bytes down that Weblink channel to the physical printer. No
inbound port, no LAN relay, no extra box — the printer's outbound
connection is the bridge.

(Note: Zebra's *MQTT* connector is management/notifications only — it
cannot deliver print jobs — which is why this uses Weblink, not MQTT.)

One-time setup, per printer:
  1. Create a Zebra Data Services account → get an ``apikey`` + ``tenant``.
  2. Enrol the printer: point ``weblink.ip.conn1.location`` at
     ``https://savanna-device.zpc.zebra.com/weblink/connect?...`` using the
     Zebra Printer Setup Utility (Android / iOS / Windows).
  3. Fill api key / tenant / serial in /settings > Materiel (or the
     ``ZEBRA_CLOUD_*`` env vars).

API contract (confirmed against Zebra developer docs):
  POST https://api.zebra.com/v2/devices/printers/send
  headers     : apikey: <key>, tenant: <account number>
  body (multipart/form-data): sn=<serial>, zpl_file=<ZPL bytes>
"""

from __future__ import annotations

import logging

import httpx

from app.services.zebra_printer import PrinterUnreachable

logger = logging.getLogger("vintiz")

DEFAULT_ENDPOINT = "https://api.zebra.com/v2/devices/printers/send"
DEFAULT_TIMEOUT_S = 15.0


class CloudConfigError(RuntimeError):
    """Cloud transport selected but the credentials/serial are incomplete.

    The label router maps this to a 400 (operator-fixable config) rather
    than a 502 (transient hardware/network).
    """


class CloudPrintError(PrinterUnreachable):
    """The SendFileToPrinter call failed (network error or non-2xx).

    Subclasses ``PrinterUnreachable`` so the label router's existing
    ``except zebra_printer.PrinterUnreachable`` already maps it to a 502 —
    no extra branch needed at the call sites.
    """


def resolve_credentials(cfg: dict) -> tuple[str, str, str, str]:
    """Pull ``(api_key, tenant, serial, endpoint)`` from a label_printer config.

    Raises :class:`CloudConfigError` listing whatever is blank, so the
    /settings UI can tell the operator exactly what to fill in.
    """
    api_key = (cfg.get("cloud_api_key") or "").strip()
    tenant = (cfg.get("cloud_tenant") or "").strip()
    serial = (cfg.get("cloud_serial") or "").strip()
    endpoint = (cfg.get("cloud_endpoint") or "").strip() or DEFAULT_ENDPOINT

    missing = [
        label
        for label, value in (
            ("clé API", api_key),
            ("tenant", tenant),
            ("n° de série", serial),
        )
        if not value
    ]
    if missing:
        raise CloudConfigError(
            "Mode cloud Zebra incomplet : " + ", ".join(missing) + " manquant(s)"
        )
    return api_key, tenant, serial, endpoint


async def send_zpl(zpl: str, cfg: dict, *, timeout: float = DEFAULT_TIMEOUT_S) -> str:
    """Push a ZPL job to the printer via the SendFileToPrinter cloud API.

    Returns the printer serial on success. Raises :class:`CloudConfigError`
    when the config is incomplete and :class:`CloudPrintError` on a
    transport error or a non-2xx response from Zebra.
    """
    api_key, tenant, serial, endpoint = resolve_credentials(cfg)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                endpoint,
                headers={"apikey": api_key, "tenant": tenant},
                data={"sn": serial},
                files={
                    "zpl_file": ("label.zpl", zpl.encode("utf-8"), "application/octet-stream"),
                },
            )
    except httpx.HTTPError as exc:
        raise CloudPrintError(f"Cloud Zebra injoignable : {exc}") from exc

    if resp.status_code // 100 != 2:
        # Surface a trimmed body so the operator sees "printer offline" /
        # "bad serial" without dumping the whole HTML error page.
        raise CloudPrintError(
            f"SendFileToPrinter a renvoyé {resp.status_code} : {resp.text[:200]}"
        )

    logger.info("Zebra cloud print sent (sn=%s, %d bytes ZPL)", serial, len(zpl))
    return serial
