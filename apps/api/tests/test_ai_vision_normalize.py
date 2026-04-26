"""Tests for the Vision payload normaliser (P2-013)."""

from app.services.ai_vision import (
    ALLOWED_CUTS,
    ALLOWED_OCCASIONS,
    ALLOWED_PATTERNS,
    ALLOWED_STYLES,
    normalize_vision_payload,
)


def test_returns_empty_dict_for_non_dict_input():
    assert normalize_vision_payload(None) == {}
    assert normalize_vision_payload("not a dict") == {}
    assert normalize_vision_payload(42) == {}


def test_known_style_passes_through_lowercased():
    out = normalize_vision_payload({"style": "  CHIC  "})
    assert out["style"] == "chic"


def test_unknown_style_becomes_none():
    out = normalize_vision_payload({"style": "ninja"})
    assert out["style"] is None


def test_motif_and_coupe_filtered_against_allowlist():
    out = normalize_vision_payload({
        "motif": "fleuri",
        "coupe": "OVERSIZE",
    })
    assert out["motif"] == "fleuri"
    assert out["coupe"] == "oversize"

    bad = normalize_vision_payload({"motif": "tie-dye", "coupe": "ninja"})
    assert bad["motif"] is None
    assert bad["coupe"] is None


def test_occasion_string_is_promoted_to_list():
    out = normalize_vision_payload({"occasion": "soiree"})
    assert out["occasion"] == ["soiree"]


def test_occasion_list_is_filtered():
    out = normalize_vision_payload({
        "occasion": ["soiree", "ninja-gala", "BUREAU"],
    })
    assert "soiree" in out["occasion"]
    assert "bureau" in out["occasion"]
    assert "ninja-gala" not in out["occasion"]


def test_occasion_garbage_yields_empty_list():
    assert normalize_vision_payload({"occasion": 42})["occasion"] == []
    assert normalize_vision_payload({})["occasion"] == []


def test_defauts_string_promoted_to_list():
    out = normalize_vision_payload({"defauts": "tâche"})
    assert out["defauts"] == ["tâche"]


def test_defauts_list_strips_blanks():
    out = normalize_vision_payload({
        "defauts": ["trou", "  ", "fermeture cassée"],
    })
    assert out["defauts"] == ["trou", "fermeture cassée"]


def test_defauts_garbage_yields_empty_list():
    out = normalize_vision_payload({"defauts": {"oops": True}})
    assert out["defauts"] == []


def test_confiance_clamped_to_0_1():
    assert normalize_vision_payload({"confiance": -2.0})["confiance"] == 0.0
    assert normalize_vision_payload({"confiance": 5.0})["confiance"] == 1.0
    assert normalize_vision_payload({"confiance": 0.42})["confiance"] == 0.42


def test_confiance_handles_string_or_missing():
    """A string-encoded number coerces; junk returns the original key
    (we don't drop it — caller can detect None)."""
    assert normalize_vision_payload({"confiance": "0.7"})["confiance"] == 0.7
    out = normalize_vision_payload({"confiance": "abc"})
    assert out["confiance"] is None or out["confiance"] == "abc"


def test_allowlists_are_non_empty_safety_check():
    """If the allowlists ever shrink to nothing, normalisation would
    silently throw away every value — guard against that."""
    assert ALLOWED_STYLES
    assert ALLOWED_OCCASIONS
    assert ALLOWED_PATTERNS
    assert ALLOWED_CUTS


def test_full_payload_round_trip():
    """End-to-end: a complete Claude response stays usable."""
    payload = {
        "type": "robe",
        "couleur": "noir",
        "marque": "Sandro",
        "taille": "38",
        "etat": "tres bon",
        "saison": "mi-saison",
        "style": "Chic",
        "occasion": ["bureau", "soiree"],
        "motif": "uni",
        "coupe": "droit",
        "defauts": [],
        "description": "Robe noire midi en crepe.",
        "gamme_estimee": "premium",
        "confiance": 0.87,
    }
    out = normalize_vision_payload(payload)
    assert out["style"] == "chic"
    assert out["occasion"] == ["bureau", "soiree"]
    assert out["motif"] == "uni"
    assert out["coupe"] == "droit"
    assert out["defauts"] == []
    assert out["confiance"] == 0.87
    # Free-form fields are preserved untouched.
    assert out["type"] == "robe"
    assert out["marque"] == "Sandro"
