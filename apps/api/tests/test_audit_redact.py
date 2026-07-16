"""Tests pour la fonction _redact() de l'audit service.

Conformité RGPD (minimisation art. 5-1-c) + NF525 (rétention 6 ans) :
- email et phone : hashés SHA-256 tronqué 12 caractères, déterministes,
  non-réversibles
- pin_hash / password_hash : marqués <set>/<empty> seulement
- first_name / last_name : conservés en clair (utilité audit, non-identifiants
  isolément)
- types non-JSON natifs : coercés (Decimal, UUID, Enum, datetime)
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.services.audit import _hash_pii, _redact


# -- email hashing --------------------------------------------------


def test_email_is_hashed():
    out = _redact("email", "alice@vintiz.fr")
    assert isinstance(out, str)
    assert out.startswith("sha256:")
    assert len(out) == len("sha256:") + 12
    assert "alice" not in out
    assert "vintiz" not in out


def test_email_hash_is_deterministic():
    """Même email → même hash, pour corréler les entrées d'audit."""
    a = _redact("email", "alice@vintiz.fr")
    b = _redact("email", "alice@vintiz.fr")
    assert a == b


def test_email_hash_is_case_insensitive():
    """Alice@Vintiz.FR === alice@vintiz.fr (norme RFC 5321)."""
    a = _redact("email", "Alice@Vintiz.FR")
    b = _redact("email", "alice@vintiz.fr")
    assert a == b


def test_email_hash_strips_whitespace():
    a = _redact("email", "  alice@vintiz.fr  ")
    b = _redact("email", "alice@vintiz.fr")
    assert a == b


def test_email_hash_differs_per_email():
    a = _redact("email", "alice@vintiz.fr")
    b = _redact("email", "bob@vintiz.fr")
    assert a != b


def test_email_none_returns_none():
    assert _redact("email", None) is None


def test_email_empty_returns_none():
    assert _redact("email", "") is None
    assert _redact("email", "   ") is None


# -- phone hashing --------------------------------------------------


def test_phone_is_hashed():
    out = _redact("phone", "+33 6 12 34 56 78")
    assert isinstance(out, str)
    assert out.startswith("sha256:")
    assert "612345678" not in out
    assert out != "+33 6 12 34 56 78"


def test_phone_normalization_strips_spaces_and_punctuation():
    """+33 6 12 34 56 78 et 33-612-345678 sont le même numéro."""
    a = _redact("phone", "+33 6 12 34 56 78")
    b = _redact("phone", "33-612-345678")
    c = _redact("phone", "33612345678")
    assert a == b == c


def test_phone_none_returns_none():
    assert _redact("phone", None) is None


def test_phone_empty_returns_none():
    assert _redact("phone", "") is None
    assert _redact("phone", "   ") is None
    assert _redact("phone", "---") is None


def test_phone_differs_from_email_with_same_digits():
    """Sécurité: un email contenant '123' et un phone '123' ne donnent
    PAS le même hash, parce que la normalisation diffère (lowercase
    string complet vs digits-only)."""
    e = _redact("email", "user123@x.fr")
    p = _redact("phone", "0123")
    assert e != p


# -- pin_hash / password_hash unchanged -----------------------------


def test_pin_hash_set_returns_marker():
    assert _redact("pin_hash", "$2b$12$abc...") == "<set>"


def test_pin_hash_empty_returns_marker():
    assert _redact("pin_hash", None) == "<empty>"
    assert _redact("pin_hash", "") == "<empty>"


def test_password_hash_set_returns_marker():
    assert _redact("password_hash", "$2b$12$xyz...") == "<set>"


# -- first_name / last_name kept in clear ---------------------------


def test_first_name_not_hashed():
    assert _redact("first_name", "Alice") == "Alice"


def test_last_name_not_hashed():
    assert _redact("last_name", "Martin") == "Martin"


# -- type coercion preserved ---------------------------------------


def test_uuid_coerced_to_string():
    u = uuid.uuid4()
    assert _redact("id", u) == str(u)


def test_decimal_coerced_to_float():
    assert _redact("total_ttc", Decimal("19.99")) == 19.99


def test_enum_coerced_to_value():
    class Color(str, enum.Enum):
        red = "red"

    assert _redact("color", Color.red) == "red"


def test_datetime_coerced_to_isoformat():
    d = datetime(2026, 5, 8, 12, 0, 0)
    assert _redact("created_at", d) == "2026-05-08T12:00:00"


def test_date_coerced_to_isoformat():
    d = date(2026, 5, 8)
    assert _redact("birth_date", d) == "2026-05-08"


def test_plain_value_passes_through():
    assert _redact("score", 42) == 42
    assert _redact("status", "active") == "active"
    assert _redact("is_open", True) is True


# -- _hash_pii direct check ----------------------------------------


def test_hash_pii_format():
    h = _hash_pii("alice@vintiz.fr")
    assert h.startswith("sha256:")
    # 12 hex chars after prefix
    assert len(h.split(":", 1)[1]) == 12
    # Hex only
    assert all(c in "0123456789abcdef" for c in h.split(":", 1)[1])


@pytest.mark.parametrize(
    "field,value,want_hash_prefix",
    [
        ("email", "alice@vintiz.fr", True),
        ("phone", "0612345678", True),
        ("first_name", "Alice", False),
        ("last_name", "Martin", False),
        ("status", "active", False),
        ("score", 42, False),
    ],
)
def test_redact_per_field(field, value, want_hash_prefix):
    out = _redact(field, value)
    if want_hash_prefix:
        assert isinstance(out, str)
        assert out.startswith("sha256:")
    else:
        assert out == value or (out is not None and not str(out).startswith("sha256:"))
