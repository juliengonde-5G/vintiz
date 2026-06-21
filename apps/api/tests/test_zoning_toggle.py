"""Tests for the zoning feature toggle and its graceful degradation.

When zoning is disabled the boutique must keep working: zone suggestion returns
a neutral result (no move ever proposed) and the cahier per-zone breakdown is
empty — none of it raises.
"""

import datetime

import pytest

from app.services import app_config, feature_flags


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    path = tmp_path / "app_config.json"
    monkeypatch.setattr(app_config, "DEFAULT_PATH", path)
    return path


# ---------------------------------------------------------------------------
# Toggle persistence
# ---------------------------------------------------------------------------


def test_zoning_enabled_default_true(temp_config):
    assert feature_flags.zoning_enabled() is True
    assert feature_flags.get_features() == {"zoning_enabled": True}


def test_set_zoning_enabled_persists(temp_config):
    feature_flags.set_zoning_enabled(False)
    assert feature_flags.zoning_enabled() is False
    # Re-read from disk (fresh load) confirms persistence.
    assert app_config.get_section("features")["zoning_enabled"] is False
    feature_flags.set_zoning_enabled(True)
    assert feature_flags.zoning_enabled() is True


# ---------------------------------------------------------------------------
# Degradation: suggest_zone
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_suggest_zone_neutral_when_disabled(monkeypatch):
    from app.models.product import Product
    from app.services.merchandising import MerchandisingService

    monkeypatch.setattr(feature_flags, "zoning_enabled", lambda: False)

    # db is never touched on the disabled path → a sentinel is fine.
    svc = MerchandisingService(db=object())
    suggestion = await svc.suggest_zone(Product())
    assert suggestion.primary_zone_id is None
    assert suggestion.should_go_to_window is False
    assert "désactiv" in suggestion.rationale.lower()


# ---------------------------------------------------------------------------
# Degradation: cahier per-zone breakdown
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_compute_zones_today_empty_when_disabled(monkeypatch):
    from app.services import cahier_service

    monkeypatch.setattr(
        "app.services.feature_flags.zoning_enabled", lambda: False
    )
    # db never touched on the disabled path.
    result = await cahier_service.compute_zones_today(db=object(), report_date=datetime.date.today())
    assert result == []
