"""Persistent hardware configuration for Vintiz peripherals.

Stores the network/USB settings for the receipt printer (MUNBYN 047P-WiFi),
the label printer (Zebra ZD421d, ZPL over TCP), the cash drawer (Safescan
SD-4141 wired via the receipt printer's RJ-12 port) and the Bluetooth / USB
barcode scanner (Inateck BCST-35).

The config is persisted on disk under ``data/hardware.json`` (next to the
API process) so it survives reloads. Defaults can be overridden via env
vars to ease deployment.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(
    os.getenv(
        "VINTIZ_HARDWARE_CONFIG",
        str(Path(__file__).resolve().parents[2] / "data" / "hardware.json"),
    )
)


DEFAULT_CONFIG: dict[str, Any] = {
    # Receipt printer — MUNBYN 047P, ESC/POS, 80 mm
    # ``connection`` switches between network (port 9100, fixed station)
    # and usb (WebUSB on the cashier tablet — Lenovo Idea Tab Pro Gen 2).
    # When connection=usb, ``usb_vendor_id``/``usb_product_id`` let the
    # front-end auto-reconnect to the previously paired device without
    # re-prompting the operator on every reload.
    "receipt_printer": {
        "enabled": False,
        "model": "MUNBYN 047P",
        "protocol": "escpos",
        "connection": "network",  # network | usb
        "host": os.getenv("RECEIPT_PRINTER_HOST", ""),
        "port": int(os.getenv("RECEIPT_PRINTER_PORT", "9100")),
        "width_chars": 42,  # 80 mm paper, Font A
        "cut_paper": True,
        "beep": False,
        # WebUSB metadata — populated by the front when the operator
        # pairs the device via ``navigator.usb.requestDevice()``.
        "usb_vendor_id": None,
        "usb_product_id": None,
        "usb_serial_number": None,
        "usb_product_label": None,
    },
    # Cash drawer — Safescan SD-4141, RJ-12, kicked by the receipt printer
    "cash_drawer": {
        "enabled": False,
        "model": "Safescan SD-4141",
        "kick_on_cash": True,
        "kick_pin": 0,  # ESC p m — 0 = pin 2, 1 = pin 5
        "on_time_ms": 50,
        "off_time_ms": 250,
    },
    # Label printer — Zebra ZD421d, ZPL II, 4 inch direct thermal
    #
    # ``connection`` selects the transport:
    #   network   = ZPL over TCP 9100 on the LAN. Only works when the API can
    #               reach the printer's IP (API + printer on the same network).
    #   cloud     = Weblink + Zebra's SendFileToPrinter API. The printer dials
    #               out to Zebra Data Services and we push ZPL via REST. Use
    #               this when the API runs off-site (cloud) and the printer is
    #               on the boutique LAN behind NAT. See services/zebra_cloud.py.
    #   bluetooth = Web Bluetooth (BLE) from the cashier tablet. The SERVER
    #               can't reach a BLE printer, so server-side print endpoints
    #               return 400 in this mode; the tablet fetches the raw ZPL
    #               (GET /api/labels/{id}/zpl) and writes it to the Zebra's BLE
    #               Parser service. ``bt_device_name`` is a reconnection hint.
    "label_printer": {
        "enabled": False,
        "model": "Zebra ZD421d",
        "protocol": "zpl",
        "connection": os.getenv("ZEBRA_CONNECTION", "network"),  # network | cloud | bluetooth
        "host": os.getenv("ZEBRA_PRINTER_IP", os.getenv("LABEL_PRINTER_HOST", "")),
        "port": int(os.getenv("ZEBRA_PRINTER_PORT", os.getenv("LABEL_PRINTER_PORT", "9100"))),
        "dpi": 203,
        "label_width_mm": 25,
        "label_height_mm": 52,
        # Cloud mode (Weblink + SendFileToPrinter) — Zebra Data Services creds
        "cloud_api_key": os.getenv("ZEBRA_CLOUD_API_KEY", ""),
        "cloud_tenant": os.getenv("ZEBRA_CLOUD_TENANT", ""),
        "cloud_serial": os.getenv("ZEBRA_CLOUD_SERIAL", ""),
        "cloud_endpoint": os.getenv("ZEBRA_CLOUD_ENDPOINT", ""),  # blank → default
        # Bluetooth mode — name of the paired BLE printer (reconnection hint)
        "bt_device_name": "",
    },
    # Barcode scanner — Inateck BCST-35 2D (HID keyboard mode by default)
    "barcode_scanner": {
        "enabled": True,
        "model": "Inateck BCST-35",
        "mode": "hid",  # hid = keyboard wedge
        "suffix": "enter",
        "min_length": 4,
    },
    # Payment terminal — SumUp (already integrated via SumUp API)
    "payment_terminal": {
        "enabled": True,
        "model": "SumUp",
        "mode": "api",
    },
}


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_config(path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """Load the hardware config, merging with defaults for missing keys."""
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(DEFAULT_CONFIG))

    # Merge so new defaults are always present
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for section, values in (data or {}).items():
        if section in merged and isinstance(values, dict):
            merged[section].update(values)
        else:
            merged[section] = values
    return merged


def save_config(config: dict[str, Any], path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """Persist the hardware config to disk and return the merged result."""
    _ensure_parent(path)
    # Merge with current so partial updates are supported
    current = load_config(path)
    for section, values in (config or {}).items():
        if isinstance(values, dict) and section in current and isinstance(current[section], dict):
            current[section].update(values)
        else:
            current[section] = values
    with path.open("w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=2, ensure_ascii=False)
    return current


def update_section(section: str, values: dict[str, Any], path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """Update a single section of the hardware config."""
    return save_config({section: values}, path=path)
