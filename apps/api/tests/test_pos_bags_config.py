"""Tests for POS quick-add bags config (multi-bag).

Couvre la résolution rétrocompatible (legacy single-bag → liste synthétique),
la validation des entrées (libellé requis, prix borné, plafond 10 sacs) et le
mirroir legacy du premier sac quand la liste est posée.
"""

from pathlib import Path

import pytest

from app.services.app_config import (
    DEFAULT_CONFIG,
    load_config,
    resolved_pos_bags,
    save_config,
)


@pytest.fixture
def tmp_config_path(tmp_path: Path) -> Path:
    return tmp_path / "app_config.json"


def test_resolved_bags_uses_list_when_set():
    section = {
        "bag_label": "Legacy",
        "bag_default_price_eur": 0.10,
        "bags": [
            {"label": "Sac Kraft", "price_eur": 0.25},
            {"label": "Grand Sac Kraft", "price_eur": 0.50},
        ],
    }
    assert resolved_pos_bags(section) == [
        {"label": "Sac Kraft", "price_eur": 0.25},
        {"label": "Grand Sac Kraft", "price_eur": 0.50},
    ]


def test_resolved_bags_falls_back_to_legacy_single_bag():
    section = {"bag_label": "Sac boutique Vintiz", "bag_default_price_eur": 0.25}
    assert resolved_pos_bags(section) == [
        {"label": "Sac boutique Vintiz", "price_eur": 0.25},
    ]


def test_resolved_bags_drops_empty_labels():
    section = {
        "bag_label": "",
        "bag_default_price_eur": 0,
        "bags": [
            {"label": "", "price_eur": 1.0},
            {"label": "Sac Kraft", "price_eur": 0.25},
        ],
    }
    assert resolved_pos_bags(section) == [
        {"label": "Sac Kraft", "price_eur": 0.25},
    ]


def test_resolved_bags_empty_when_no_legacy_or_list():
    assert resolved_pos_bags({}) == []
    assert resolved_pos_bags({"bag_label": "", "bag_default_price_eur": 0}) == []


def test_default_pos_section_has_bags_key():
    # New deployments start with an empty list (legacy fields seed the single
    # button via resolved_pos_bags until the manager picks a multi-bag layout).
    assert DEFAULT_CONFIG["pos"]["bags"] == []
    assert DEFAULT_CONFIG["pos"]["bag_label"] == "Sac boutique Vintiz"


def test_save_and_reload_round_trips_bag_list(tmp_config_path: Path):
    save_config({"pos": {"bags": [
        {"label": "Sac Kraft", "price_eur": 0.25},
        {"label": "Grand Sac Kraft", "price_eur": 0.50},
    ]}}, path=tmp_config_path)
    cfg = load_config(tmp_config_path)
    assert cfg["pos"]["bags"] == [
        {"label": "Sac Kraft", "price_eur": 0.25},
        {"label": "Grand Sac Kraft", "price_eur": 0.50},
    ]
    # Defaults still merged for unset keys (legacy mirror untouched here).
    assert cfg["pos"]["bag_label"] == "Sac boutique Vintiz"


@pytest.mark.anyio
async def test_put_pos_config_validates_and_mirrors_legacy(monkeypatch, tmp_path):
    """End-to-end : PUT /api/admin/pos-config persists bags + mirrors legacy."""
    from app.api.admin.router import PosConfigUpdate, update_pos_config
    from app.services import app_config

    config_path = tmp_path / "app_config.json"
    monkeypatch.setattr(app_config, "DEFAULT_PATH", config_path)

    section = await update_pos_config(PosConfigUpdate(bags=[
        {"label": "Sac Kraft", "price_eur": 0.25},
        {"label": "Grand Sac Kraft", "price_eur": 0.50},
    ]))
    assert section["bags"] == [
        {"label": "Sac Kraft", "price_eur": 0.25},
        {"label": "Grand Sac Kraft", "price_eur": 0.50},
    ]
    # Legacy mirror points to the first bag.
    assert section["bag_label"] == "Sac Kraft"
    assert section["bag_default_price_eur"] == 0.25


@pytest.mark.anyio
async def test_put_pos_config_rejects_empty_label(monkeypatch, tmp_path):
    from fastapi import HTTPException

    from app.api.admin.router import PosConfigUpdate, update_pos_config
    from app.services import app_config

    monkeypatch.setattr(app_config, "DEFAULT_PATH", tmp_path / "app_config.json")

    with pytest.raises(HTTPException) as exc:
        await update_pos_config(PosConfigUpdate(bags=[
            {"label": "  ", "price_eur": 0.25},
        ]))
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_put_pos_config_rejects_too_many_bags(monkeypatch, tmp_path):
    from fastapi import HTTPException

    from app.api.admin.router import PosConfigUpdate, update_pos_config
    from app.services import app_config

    monkeypatch.setattr(app_config, "DEFAULT_PATH", tmp_path / "app_config.json")

    with pytest.raises(HTTPException) as exc:
        await update_pos_config(PosConfigUpdate(bags=[
            {"label": f"Sac {i}", "price_eur": 0.25} for i in range(11)
        ]))
    assert exc.value.status_code == 400
