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
        "phone": "02 77 19 01 97",
        "email": "contact@vintiz.fr",
        "website": "vintiz.fr",
        "hours": "Mar-Sam : 10h-19h",
        "surface_m2": 98,
        "vat_rate_percent": 20,
        "siret": "",
        "rcs": "",
        "ape": "",
        # Seller legal + banking fields rendered on B2B invoices.
        "legal_form": "",          # e.g. "SARL", "Association loi 1901"
        "capital_social": "",      # e.g. "10 000 €"
        "tva_intracom": "",        # n° TVA intracommunautaire (FRxx…)
        "iban": "",                # IBAN for invoice payment
        "bic": "",                 # BIC / SWIFT
        # Company logo — uploaded via /settings (Tickets & Factures). Absolute
        # path on the API host; used on the invoice PDF and (opt-in) the ticket.
        "logo_path": "",
        "print_logo_on_ticket": False,
    },
    # Installation / paramétrage de la boutique (chaîne d'installation, phase 1).
    # ``installed`` passe à True une fois l'assistant /setup terminé ;
    # ``completed_steps`` mémorise les étapes validées (fiscal, zoning, hardware,
    # users…). Voir docs/MULTI_STORE.md.
    "installation": {
        "installed": False,
        "installed_at": "",
        "completed_steps": [],
    },
    # Feature toggles — activer/désactiver des modules de l'application.
    # ``zoning_enabled`` pilote toute la gestion des zones (placement produit,
    # moteur IA d'aménagement, KPI par zone…). Désactivé → l'app fonctionne en
    # « boutique sans zonage » sans rien casser. Voir app/services/feature_flags.py.
    "features": {
        "zoning_enabled": True,
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
    # Email gateway — editable via /settings > Communication (overrides env vars)
    "email": {
        "provider": "",  # auto | brevo | smtp | simulation (empty = auto)
        "brevo_api_key": "",
        "smtp_host": "",
        "smtp_port": "587",
        "smtp_user": "",
        "smtp_password": "",
        "smtp_from": "",
        "from_address": "noreply@vintiz.fr",
        "from_name": "Vintiz Vernon",
    },
    # SMS gateway — Twilio fallback for OTP magic-link
    "sms": {
        "twilio_account_sid": "",
        "twilio_auth_token": "",
        "twilio_from": "",
    },
    # Manager-curated selection of products surfaced on /account/selection
    # (Lot 5 — list of {product_id, reason})
    "curation_picks": {
        "items": [],
        "curator_note": "",
        "updated_at": "",
    },
    # Cash management defaults (PR 5/6 — POS routine)
    # Drives the CashDrawerOpen/Close modals: default discrepancy
    # tolerance + whether the denomination grid is shown by default +
    # the comptable email used by the Z-report mailer.
    "cash_management": {
        "allowed_discrepancy_eur": 2.0,
        "default_detail_mode": True,
        "comptable_email": "",
    },
    # POS quick-add config — editable via /settings > Caisse.
    # The reusable shopping bags are manual line items (no stock impact,
    # unlimited quantity). Each is rendered as its own quick-add button at
    # the till; the cashier can still edit the price per sale.
    #
    # ``bags`` is the source of truth (multi-bag : Sac Kraft, Grand Sac
    # Kraft…). The legacy ``bag_label`` / ``bag_default_price_eur`` fields
    # are kept as a mirror of the FIRST bag for old consumers (legacy
    # clients pre-list still pre-fill their unique button).
    "pos": {
        "bag_label": "Sac boutique Vintiz",
        "bag_default_price_eur": 0.25,
        "bags": [],
    },
}


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _deep_copy(obj: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(obj))


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load app config, merging defaults for missing keys."""
    # Resolve at call time (not as a default arg) so a monkeypatched/overridden
    # DEFAULT_PATH is honoured — default args bind once at import.
    path = path or DEFAULT_PATH
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


def save_config(config: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Persist a partial app config (merged with current state)."""
    path = path or DEFAULT_PATH
    _ensure_parent(path)
    current = load_config(path)
    for section, values in (config or {}).items():
        if isinstance(values, dict) and section in current and isinstance(current[section], dict):
            current[section].update(values)
        else:
            current[section] = values
    # Atomic write: dump to a temp file in the same dir then os.replace, so a
    # crash mid-write can never truncate app_config.json (which load_config
    # would then silently reset to DEFAULT_CONFIG, wiping SumUp/Brevo keys).
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return current


def get_section(section: str, path: Path | None = None) -> dict[str, Any]:
    """Read a single section (returns a copy, never the live dict)."""
    return _deep_copy(load_config(path or DEFAULT_PATH).get(section, {}))


def update_section(section: str, values: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Update a single section."""
    return save_config({section: values}, path=path or DEFAULT_PATH)


def resolved_pos_bags(pos_section: dict[str, Any]) -> list[dict[str, Any]]:
    """Effective list of POS quick-add bags.

    Uses ``bags`` when non-empty ; otherwise synthesises a single bag from
    the legacy ``bag_label`` / ``bag_default_price_eur`` fields so a config
    file written before the multi-bag feature still renders one button.
    """
    bags = pos_section.get("bags") or []
    cleaned: list[dict[str, Any]] = []
    for entry in bags:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip()
        if not label:
            continue
        try:
            price = float(entry.get("price_eur") or 0)
        except (TypeError, ValueError):
            price = 0.0
        cleaned.append({"label": label, "price_eur": price})
    if cleaned:
        return cleaned
    legacy_label = str(pos_section.get("bag_label") or "").strip()
    if not legacy_label:
        return []
    try:
        legacy_price = float(pos_section.get("bag_default_price_eur") or 0)
    except (TypeError, ValueError):
        legacy_price = 0.0
    return [{"label": legacy_label, "price_eur": legacy_price}]


def mask_secret(value: str | None, keep: int = 4) -> str:
    """Mask a credential for read-only UI display."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "***" + ("" if len(value) <= keep + 4 else value[-2:])
