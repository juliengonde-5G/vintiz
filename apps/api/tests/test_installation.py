"""Tests for the boutique installation state (chaîne d'installation, phase 1)."""

import pytest

from app.services import app_config


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    path = tmp_path / "app_config.json"
    monkeypatch.setattr(app_config, "DEFAULT_PATH", path)
    return path


def test_installation_default_not_installed(temp_config):
    from app.api.admin.router import _installation_state

    state = _installation_state()
    assert state["installed"] is False
    # Fiscal/zoning/hardware/users not validated yet → not fully installed.
    assert state["all_done"] is False


def test_identity_not_done_when_cleared(temp_config):
    from app.api.admin.router import _installation_state

    # A truly blank boutique (operator cleared the template identity).
    app_config.update_section("shop_info", {"name": "", "city": ""})
    identity = next(c for c in _installation_state()["checklist"] if c["key"] == "identity")
    assert identity["done"] is False


def test_identity_done_when_shop_info_set(temp_config):
    from app.api.admin.router import _installation_state

    app_config.update_section("shop_info", {"name": "Vintiz", "city": "Vernon"})
    state = _installation_state()
    identity = next(c for c in state["checklist"] if c["key"] == "identity")
    assert identity["done"] is True
    assert "identity" in state["completed_steps"]


def test_completed_steps_and_installed_flag(temp_config):
    from app.api.admin.router import _installation_state

    app_config.update_section("shop_info", {"name": "Vintiz", "city": "Vernon"})
    app_config.update_section("installation", {"completed_steps": ["fiscal", "zoning", "hardware", "users"]})
    state = _installation_state()
    assert state["all_done"] is True  # identity (real) + the 4 steps

    app_config.update_section("installation", {"installed": True, "installed_at": "2026-06-21T10:00:00+00:00"})
    state2 = _installation_state()
    assert state2["installed"] is True
    assert state2["installed_at"].startswith("2026-06-21")
