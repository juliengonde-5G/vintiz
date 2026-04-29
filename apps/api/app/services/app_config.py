"""Persistent application configuration (shop info + SumUp credentials).

Stores boutique metadata (name, address, hours…) and the SumUp payment
terminal credentials so the manager can edit them from the back-office UI
without redeploying the app.

The config is persisted on disk under ``data/app_config.json`` (next to the
API process) so it survives reloads. Defaults can still be overridden via
env vars; the persisted file takes precedence whenever a value is set.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(
    os.getenv(
        "VINTIZ_APP_CONFIG",
        str(Path(__file__).resolve().parents[2] / "data" / "app_config.json"),
    )
)


DEFAULT_CONFIG: dict[str, Any] = {
    # Shop info — editable via /settings > Boutique
    "shop_info": {
        "name": "Vintiz",
        "tagline": "Boutique seconde main premium",
        "address_line1": "6 rue Saint-Jacques",
        "address_line2": "",
        "postal_code": "27200",
        "city": "Vernon",
        "country": "France",
        "phone": "",
        "email": "contact@vintiz.fr",
        "website": "vintiz.fr",
        "hours": "Mar-Sam : 10h-19h",
        "surface_m2": 98,
        "vat_rate_percent": 20,
        "siret": "",
        "rcs": "",
        "ape": "",
    },
    # SumUp config — editable via /settings > Paiement (overrides env vars)
    "sumup": {
        "environment": "",  # empty = auto-detect (env var fallback)
        "api_key": "",
        "merchant_code": "",
        "reader_id": "",
        "sandbox_auto_delay_sec": 5,
        "return_url": "",
    },
}


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _deep_copy(obj: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(obj))


def load_config(path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """Load app config, merging defaults for missing keys."""
    if not path.exists():
        return _deep_copy(DEFAULT_CONFIG)
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return _deep_copy(DEFAULT_CONFIG)

    merged = _deep_copy(DEFAULT_CONFIG)
    for section, values in (data or {}).items():
        if section in merged and isinstance(values, dict):
            merged[section].update(values)
        else:
            merged[section] = values
    return merged


def save_config(config: dict[str, Any], path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """Persist a partial app config (merged with current state)."""
    _ensure_parent(path)
    current = load_config(path)
    for section, values in (config or {}).items():
        if isinstance(values, dict) and section in current and isinstance(current[section], dict):
            current[section].update(values)
        else:
            current[section] = values
    with path.open("w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=2, ensure_ascii=False)
    return current


def get_section(section: str, path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """Read a single section (returns a copy, never the live dict)."""
    return _deep_copy(load_config(path).get(section, {}))


def update_section(section: str, values: dict[str, Any], path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """Update a single section."""
    return save_config({section: values}, path=path)


def mask_secret(value: str | None, keep: int = 4) -> str:
    """Mask a credential for read-only UI display."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "***" + ("" if len(value) <= keep + 4 else value[-2:])
