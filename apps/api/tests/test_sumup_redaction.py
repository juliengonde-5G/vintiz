"""Tests pour redact_sumup_error() — conformité PCI-DSS req. 3 et RGPD.

Cible : un payload d'erreur SumUp ne doit jamais persister en DB ni dans
les logs avec un PAN, un CVV, un Bearer token ou une clé API en clair.
"""

import pytest

from app.services.sumup_service import redact_sumup_error


# -- PAN (13-19 digits) ---------------------------------------------


def test_redact_visa_pan():
    text = 'Card declined: 4111111111111111 invalid'
    out = redact_sumup_error(text)
    assert "4111111111111111" not in out
    assert "<PAN_REDACTED>" in out


def test_redact_mastercard_pan():
    text = "PAN=5555555555554444 declined"
    out = redact_sumup_error(text)
    assert "5555555555554444" not in out


def test_redact_amex_15_digits():
    text = "Amex 378282246310005 invalid"
    out = redact_sumup_error(text)
    assert "378282246310005" not in out


def test_redact_pan_with_dashes():
    text = "card 4111-1111-1111-1111 expired"
    out = redact_sumup_error(text)
    assert "4111" not in out or "<PAN_REDACTED>" in out


def test_redact_pan_with_spaces():
    text = "card 4111 1111 1111 1111 invalid"
    out = redact_sumup_error(text)
    assert "4111 1111" not in out


def test_keep_short_numbers_intact():
    """Codes HTTP, montants, IDs courts ne doivent PAS matcher PAN."""
    text = "HTTP 422 amount=12.50 attempt=3"
    out = redact_sumup_error(text)
    assert "422" in out
    assert "12.50" in out
    assert "attempt=3" in out


def test_keep_12_digit_id_intact():
    """12 digits = en dessous du seuil PAN (13 mini)."""
    text = "merchant_id=123456789012 ok"
    out = redact_sumup_error(text)
    assert "123456789012" in out


# -- CVV / CVC ------------------------------------------------------


def test_redact_cvv_with_colon():
    text = "card refused cvv: 123"
    out = redact_sumup_error(text)
    assert "123" not in out
    assert "<CVV_REDACTED>" in out


def test_redact_cvc_with_equals():
    text = "cvc=4567 wrong"
    out = redact_sumup_error(text)
    assert "4567" not in out


def test_redact_cvv2_uppercase():
    text = "CVV2 999 declined"
    out = redact_sumup_error(text)
    assert "999" not in out


def test_redact_security_code():
    text = "card_security_code: 0123 invalid"
    out = redact_sumup_error(text)
    assert "0123" not in out


# -- Tokens et clés API --------------------------------------------


def test_redact_bearer_token():
    text = "Authorization: Bearer abc123def456ghi789jkl012"
    out = redact_sumup_error(text)
    assert "abc123def456ghi789jkl012" not in out


def test_redact_authorization_header():
    text = "Authorization: Basic dXNlcjpwYXNzd29yZA=="
    out = redact_sumup_error(text)
    assert "dXNlcjpwYXNzd29yZA" not in out


def test_redact_sumup_api_key():
    text = "401: invalid sup_sk_abc123def456ghi789jkl012mno345"
    out = redact_sumup_error(text)
    assert "abc123def456ghi789jkl012mno345" not in out
    assert "<API_KEY_REDACTED>" in out


def test_redact_stripe_live_key():
    # Concaténation runtime pour éviter que GitHub Push Protection /
    # secret scanners ne match un faux positif sur ce pattern de test.
    fake_key_body = "A" * 24
    text = "fallback " + "sk_live_" + fake_key_body + " used"
    out = redact_sumup_error(text)
    assert fake_key_body not in out


def test_redact_anthropic_key():
    fake_key_body = "X" * 24
    text = "sk-ant-" + "api03-" + fake_key_body + " leaked"
    out = redact_sumup_error(text)
    assert fake_key_body not in out


def test_redact_jwt():
    text = (
        "token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJ1c2VyIjoiYWRtaW4ifQ.s5dx9qB3e4rN7K2vP9wE1aZ"
    )
    out = redact_sumup_error(text)
    assert "<JWT_REDACTED>" in out


# -- Truncation et edge cases ---------------------------------------


def test_truncate_long_text():
    text = "X" * 500
    out = redact_sumup_error(text, max_len=300)
    assert len(out) <= 301  # 300 + ellipsis


def test_empty_input_returns_empty_string():
    assert redact_sumup_error("") == ""
    assert redact_sumup_error(None) == ""


def test_normal_message_passes_through():
    text = "Insufficient funds — please try another card"
    out = redact_sumup_error(text)
    assert out == text


def test_combined_pan_and_cvv():
    text = "card 4111111111111111 cvv 123 declined"
    out = redact_sumup_error(text)
    assert "4111111111111111" not in out
    assert "123" not in out


@pytest.mark.parametrize(
    "raw,must_not_contain",
    [
        ("Bearer eyJhbGciOiJIUzI1NiJ9.PAYLOAD.SIG", "Bearer eyJ"),
        ("PAN: 4242424242424242", "4242424242424242"),
        ("cvv2: 9999", "9999"),
        ("authorization: token abc12345xyz", "token abc12345xyz"),
        ("sup_" + "sk_live_" + ("A" * 24), "sup_" + "sk_live_" + ("A" * 24)),
    ],
)
def test_no_secret_leaks(raw, must_not_contain):
    out = redact_sumup_error(raw)
    assert must_not_contain not in out
