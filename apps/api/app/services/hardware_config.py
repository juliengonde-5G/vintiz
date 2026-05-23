"""Persistent hardware configuration for Vintiz peripherals.

Stores the network/USB settings for the receipt printer (MUNBYN 047P-WiFi),
the label printer (driven by the in-store Raspberry Pi agent over CUPS), the
cash drawer (Safescan SD-4141 wired via the receipt printer's RJ-12 port) and
the Bluetooth / USB barcode scanner (Inateck BCST-35).

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
    # Label printer — driven by the in-store Raspberry Pi agent over CUPS.
    #
    # The API no longer talks to a printer directly. Manager actions enqueue a
    # LabelPrintJob; the Pi polls /api/labels/agent/* (outbound only) and prints
    # the server-rendered PDF on whatever printer is attached to it (USB or a
    # local network printer), via CUPS. ``cups_printer_name`` is purely
    # informational here — the authoritative printer name lives in the Pi's own
    # agent config; the Pi agent token is a server secret (RPI_AGENT_TOKEN), not
    # stored in this file.
    "label_printer": {
        "enabled": False,
        "model": "Raspberry Pi · CUPS",
        "agent": "raspberry-cups",
        "dpi": 203,
        "label_width_mm": 25,
        "label_height_mm": 52,
        "cups_printer_name": os.getenv("RPI_CUPS_PRINTER_NAME", ""),
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
