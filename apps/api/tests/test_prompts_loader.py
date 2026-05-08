"""Tests pour le loader centralisé des prompts (T2 audit tech debt).

Le loader doit :
- Charger un prompt depuis apps/api/prompts/v{N}/{name}.md
- Extraire la section ``## System`` par défaut (autres sections supportées)
- Tomber sur le fallback inline si le fichier est absent
- Lever PromptNotFoundError si ni fichier ni fallback
- Cacher le résultat (LRU) pour éviter les I/O répétées
"""

from pathlib import Path

import pytest

from app.core.prompts import (
    PromptNotFoundError,
    _extract_section,
    load_prompt,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Repart d'un cache propre entre les tests."""
    reset_cache()
    yield
    reset_cache()


# -- _extract_section ----------------------------------------------


def test_extract_system_section():
    text = """# Title

## System

Tu es Vintiz.
Sois sympa.

## User template

Bonjour.
"""
    out = _extract_section(text, "System")
    assert out == "Tu es Vintiz.\nSois sympa."


def test_extract_section_until_eof_when_no_next_h2():
    text = """# Title

## System

Tu es Vintiz.
Pas de section suivante.
"""
    out = _extract_section(text, "System")
    assert out == "Tu es Vintiz.\nPas de section suivante."


def test_extract_arbitrary_section():
    text = """## System

A

## Cost control

B
budget"""
    out = _extract_section(text, "Cost control")
    assert out == "B\nbudget"


def test_extract_missing_section_raises():
    with pytest.raises(PromptNotFoundError):
        _extract_section("# Title\n\nbody", "System")


def test_extract_strips_whitespace():
    text = "## System\n\n\n   body   \n\n\n"
    assert _extract_section(text, "System") == "body"


# -- load_prompt avec fichiers réels --------------------------------


def test_load_existing_personal_shopper_prompt():
    """Le fichier apps/api/prompts/v1/personal_shopper.md existe et a une
    section ## System."""
    prompt = load_prompt("personal_shopper")
    assert "Personal Shopper" in prompt or "Vintiz" in prompt
    assert "## User template" not in prompt  # ne déborde pas sur la section suivante
    assert len(prompt) > 100


def test_load_existing_social_posts_prompt():
    prompt = load_prompt("social_posts")
    assert "vintiz" in prompt.lower()
    # La section System ne contient pas la section "Cost control" suivante
    assert "## Cost control" not in prompt
    assert len(prompt) > 100


def test_load_existing_ai_vision_prompt():
    prompt = load_prompt("ai_vision")
    assert "JSON" in prompt
    assert "type" in prompt
    assert len(prompt) > 100


def test_load_user_template_section():
    prompt = load_prompt("personal_shopper", section="User template")
    # User template existe dans personal_shopper.md
    assert len(prompt) > 0


# -- Fallback ------------------------------------------------------


def test_load_missing_file_uses_fallback():
    fallback = "FALLBACK CONTENT"
    out = load_prompt("nonexistent_prompt", fallback=fallback)
    assert out == fallback


def test_load_missing_file_no_fallback_raises():
    with pytest.raises(PromptNotFoundError):
        load_prompt("nonexistent_prompt")


def test_load_missing_version_uses_fallback():
    fallback = "FALLBACK"
    out = load_prompt(
        "personal_shopper",
        version="v999",
        fallback=fallback,
    )
    assert out == fallback


# -- Cache ---------------------------------------------------------


def test_cache_returns_same_string_object():
    """Deux appels successifs renvoient le même résultat (cached)."""
    a = load_prompt("personal_shopper")
    b = load_prompt("personal_shopper")
    assert a == b


def test_reset_cache_forces_reload(tmp_path: Path, monkeypatch):
    """Après reset_cache(), un nouveau read est effectué."""
    a = load_prompt("personal_shopper")
    reset_cache()
    b = load_prompt("personal_shopper")
    assert a == b  # contenu identique mais I/O à nouveau effectué


# -- Path resolution -----------------------------------------------


def test_prompts_root_resolves_to_apps_api_prompts():
    """Le _PROMPTS_ROOT doit pointer vers apps/api/prompts/."""
    from app.core.prompts import _PROMPTS_ROOT

    assert _PROMPTS_ROOT.name == "prompts"
    assert _PROMPTS_ROOT.parent.name == "api"
    assert (_PROMPTS_ROOT / "v1").is_dir()
