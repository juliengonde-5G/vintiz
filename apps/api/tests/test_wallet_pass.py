"""Tests pour le payload Wallet (Apple .pkpass + Google JWT).

Tests pure-fonction sur les blocs Apple/Google + sérialisation, sans
toucher la DB ni Anthropic. Vérifie :
- Conformité au schéma Apple Wallet (passTypeIdentifier, storeCard, barcodes)
- Conformité au schéma Google Wallet (classId, loyaltyPoints, barcode)
- QR payload dérivé de PUBLIC_SITE_URL + membership_number
- Sérialisation `payload_to_dict` (asdict round-trip)
- Détection signing keys (apple_wallet_available / google_wallet_available)
"""

from dataclasses import dataclass

import pytest

from app.services.wallet import (
    BENEFIT_TEXT,
    PRIMARY_COLOR,
    WalletPassPayload,
    _apple_block,
    _apple_certs_configured,
    _google_block,
    _google_creds_configured,
    _qr_payload,
    apple_wallet_available,
    google_wallet_available,
    payload_to_dict,
)


@dataclass
class FakeClient:
    """Mimics the ORM `Client` shape needed by wallet helpers."""

    id: str = "fb1c1c3a-1234-4abc-9def-000000000000"
    first_name: str = "Alice"
    last_name: str = "Martin"


# -- _qr_payload ---------------------------------------------------


def test_qr_payload_default_url(monkeypatch):
    monkeypatch.delenv("PUBLIC_SITE_URL", raising=False)
    out = _qr_payload("V123456")
    assert out == "https://vintiz.fr/account/login?membership=V123456"


def test_qr_payload_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://staging.vintiz.fr/")
    out = _qr_payload("V000001")
    assert out == "https://staging.vintiz.fr/account/login?membership=V000001"


def test_qr_payload_includes_membership():
    membership = "V999999"
    assert membership in _qr_payload(membership)


# -- _apple_block --------------------------------------------------


def test_apple_block_required_keys():
    client = FakeClient()
    block = _apple_block(client, 245, "V100001")
    for key in (
        "formatVersion",
        "passTypeIdentifier",
        "teamIdentifier",
        "organizationName",
        "description",
        "serialNumber",
        "logoText",
        "storeCard",
        "barcodes",
    ):
        assert key in block, f"Apple Wallet schema missing {key!r}"


def test_apple_block_organization_is_vintiz():
    block = _apple_block(FakeClient(), 0, "V100001")
    assert block["organizationName"] == "Vintiz"
    assert block["logoText"] == "Vintiz"


def test_apple_block_serial_is_client_id():
    client = FakeClient(id="abc-123")
    block = _apple_block(client, 0, "V100001")
    assert block["serialNumber"] == "abc-123"


def test_apple_block_pass_type_from_env(monkeypatch):
    monkeypatch.setenv("WALLET_PASS_TYPE_IDENTIFIER", "pass.fr.test.loyalty")
    monkeypatch.setenv("WALLET_TEAM_IDENTIFIER", "TEAM12345")
    block = _apple_block(FakeClient(), 0, "V100001")
    assert block["passTypeIdentifier"] == "pass.fr.test.loyalty"
    assert block["teamIdentifier"] == "TEAM12345"


def test_apple_block_default_team_id_placeholder(monkeypatch):
    monkeypatch.delenv("WALLET_TEAM_IDENTIFIER", raising=False)
    block = _apple_block(FakeClient(), 0, "V100001")
    assert block["teamIdentifier"] == "TEAMID0000"


def test_apple_block_storeCard_has_points():
    block = _apple_block(FakeClient(), 245, "V100001")
    primary = block["storeCard"]["primaryFields"]
    assert any(
        f["key"] == "points" and f["value"] == "245" for f in primary
    )


def test_apple_block_holder_name_from_client():
    client = FakeClient(first_name="Léa", last_name="Bernard")
    block = _apple_block(client, 0, "V000123")
    secondary = block["storeCard"]["secondaryFields"]
    assert any(
        f["key"] == "holder" and "Léa Bernard" in f["value"]
        for f in secondary
    )


def test_apple_block_membership_in_aux():
    block = _apple_block(FakeClient(), 0, "V300001")
    aux = block["storeCard"]["auxiliaryFields"]
    assert any(
        f["key"] == "card" and f["value"] == "V300001" for f in aux
    )


def test_apple_block_qr_barcode():
    block = _apple_block(FakeClient(), 0, "V300001")
    assert len(block["barcodes"]) >= 1
    bc = block["barcodes"][0]
    assert bc["format"] == "PKBarcodeFormatQR"
    assert "V300001" in bc["message"]


def test_apple_block_brand_colors_present():
    block = _apple_block(FakeClient(), 0, "V100001")
    assert "foregroundColor" in block
    assert "backgroundColor" in block
    assert "labelColor" in block


# -- _google_block -------------------------------------------------


def test_google_block_required_keys():
    block = _google_block(FakeClient(), 100, "V100001")
    for key in ("id", "classId", "state", "loyaltyPoints", "barcode"):
        assert key in block, f"Google Wallet schema missing {key!r}"


def test_google_block_state_is_active():
    block = _google_block(FakeClient(), 0, "V100001")
    assert block["state"] == "ACTIVE"


def test_google_block_loyalty_points_value():
    block = _google_block(FakeClient(), 537, "V100001")
    assert block["loyaltyPoints"]["balance"] == {"int": 537}


def test_google_block_class_id_from_env(monkeypatch):
    monkeypatch.setenv("WALLET_GOOGLE_ISSUER_ID", "1234567890123456789")
    monkeypatch.setenv("WALLET_GOOGLE_CLASS_SUFFIX", "vintiz_test")
    block = _google_block(FakeClient(), 0, "V100001")
    assert block["classId"] == "1234567890123456789.vintiz_test"


def test_google_block_object_id_includes_client():
    client = FakeClient(id="abc-789")
    block = _google_block(client, 0, "V100001")
    assert block["id"].endswith(".abc-789")


def test_google_block_qr_barcode():
    block = _google_block(FakeClient(), 0, "V200001")
    bc = block["barcode"]
    assert bc["type"] == "QR_CODE"
    assert "V200001" in bc["value"]


def test_google_block_account_name_from_client():
    client = FakeClient(first_name="Julie", last_name="Dupont")
    block = _google_block(client, 0, "V200001")
    assert "Julie Dupont" in block["accountName"]
    assert block["accountId"] == "V200001"


# -- WalletPassPayload + payload_to_dict ---------------------------


def test_wallet_payload_constructor_defaults():
    payload = WalletPassPayload(
        client_id="abc",
        serial_number="abc",
        holder_name="Alice Martin",
        membership_number="V100001",
        points=12,
        benefit_text=BENEFIT_TEXT,
        primary_color=PRIMARY_COLOR,
        issued_at="2026-05-08T12:00:00+00:00",
        qr_payload="https://vintiz.fr/account/login?membership=V100001",
    )
    assert payload.apple == {}
    assert payload.google == {}


def test_payload_to_dict_round_trip():
    payload = WalletPassPayload(
        client_id="abc",
        serial_number="abc",
        holder_name="Alice",
        membership_number="V100001",
        points=12,
        benefit_text=BENEFIT_TEXT,
        primary_color=PRIMARY_COLOR,
        issued_at="2026-05-08T12:00:00+00:00",
        qr_payload="https://vintiz.fr/...",
        apple={"x": 1},
        google={"y": 2},
    )
    d = payload_to_dict(payload)
    assert d["client_id"] == "abc"
    assert d["points"] == 12
    assert d["apple"] == {"x": 1}
    assert d["google"] == {"y": 2}


# -- Disponibilité signing -----------------------------------------


def test_apple_certs_not_configured_by_default(monkeypatch):
    """En l'absence de certs, apple_wallet_available() = False."""
    for var in (
        "WALLET_APPLE_CERT_PATH",
        "WALLET_APPLE_KEY_PATH",
        "WALLET_APPLE_WWDR_PATH",
        "WALLET_APPLE_KEY_PASSWORD",
    ):
        monkeypatch.delenv(var, raising=False)
    assert _apple_certs_configured() is False
    assert apple_wallet_available() is False


def test_google_creds_not_configured_by_default(monkeypatch):
    for var in (
        "WALLET_GOOGLE_SERVICE_ACCOUNT_JSON",
        "WALLET_GOOGLE_SERVICE_ACCOUNT_PATH",
        "WALLET_GOOGLE_ISSUER_ID",
    ):
        monkeypatch.delenv(var, raising=False)
    assert _google_creds_configured() is False
    assert google_wallet_available() is False


@pytest.mark.parametrize("points", [0, 1, 100, 999, 99999])
def test_apple_block_points_serialized_as_string(points):
    block = _apple_block(FakeClient(), points, "V100001")
    primary = block["storeCard"]["primaryFields"]
    pts_field = next(f for f in primary if f["key"] == "points")
    assert pts_field["value"] == str(points)


@pytest.mark.parametrize("points", [0, 1, 100, 999, 99999])
def test_google_block_points_serialized_as_int(points):
    block = _google_block(FakeClient(), points, "V100001")
    assert block["loyaltyPoints"]["balance"]["int"] == points
