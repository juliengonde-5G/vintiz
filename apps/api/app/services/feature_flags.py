"""Feature toggles read from the persisted app config (data/app_config.json).

Currently exposes the **zoning** toggle. When zoning is disabled the boutique
runs without any zone management — product intake skips the placement step, the
AI merchandising/optimisation engines return a neutral "disabled" result, and
the per-zone KPIs are omitted from the cahier and reports — all without raising.

Reads are cheap (the config file is small and merged with defaults) so callers
can call :func:`zoning_enabled` freely. The default is ``True`` (zoning on), so
an existing deployment behaves exactly as before until a manager turns it off.
"""

from __future__ import annotations

from app.services.app_config import get_section, update_section

_FEATURES = "features"


def get_features() -> dict:
    """Current feature toggles (merged with defaults)."""
    section = get_section(_FEATURES)
    return {"zoning_enabled": bool(section.get("zoning_enabled", True))}


def zoning_enabled() -> bool:
    """True when zone management is active (default). False → boutique sans zonage."""
    return bool(get_section(_FEATURES).get("zoning_enabled", True))


def set_zoning_enabled(enabled: bool) -> dict:
    """Persist the zoning toggle and return the updated feature set."""
    update_section(_FEATURES, {"zoning_enabled": bool(enabled)})
    return get_features()
