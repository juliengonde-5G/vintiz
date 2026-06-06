"""Moteur vocal d'ajout produit : extraction des champs depuis une dictée.

L'appel Claude est mocké — on teste le mapping (même schéma que la vision) et
le parsing du prix ("8,00 €" → 8.0). Dictée vide → erreur sans appel réseau.
"""
from types import SimpleNamespace

import pytest

from app.services import ai_vision


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeMessages:
    def __init__(self, text: str):
        self._text = text

    async def create(self, **_kw):
        return SimpleNamespace(content=[SimpleNamespace(text=self._text)])


class _FakeClient:
    _text = "{}"

    def __init__(self, *_a, **_k):
        self.messages = _FakeMessages(self._text)


@pytest.mark.anyio
async def test_dictation_empty_returns_error_without_network():
    out = await ai_vision.analyze_product_dictation("   ")
    assert out == {"error": "Dictée vide"}


@pytest.mark.anyio
async def test_dictation_maps_fields_and_parses_price(monkeypatch):
    payload = (
        '{"type":"chemise","marque":"Brice","taille":"L","genre":"homme",'
        '"etat":"très bon état","couleur":"bleu","prix":"8,00 €"}'
    )

    class C(_FakeClient):
        _text = payload

    monkeypatch.setattr(ai_vision.settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(ai_vision.anthropic, "AsyncAnthropic", C)

    out = await ai_vision.analyze_product_dictation("chemise Brice taille L homme 8 euros")
    assert out["type"] == "chemise"
    assert out["marque"] == "Brice"
    assert out["taille"] == "L"
    assert out["genre"] == "homme"        # normalisé via normalize_gender
    assert out["couleur"] == "bleu"
    assert out["prix"] == 8.0             # "8,00 €" → 8.0
    assert out["transcript"].startswith("chemise Brice")


@pytest.mark.anyio
async def test_dictation_no_price_is_none(monkeypatch):
    class C(_FakeClient):
        _text = '{"type":"robe","genre":"femme"}'

    monkeypatch.setattr(ai_vision.settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(ai_vision.anthropic, "AsyncAnthropic", C)

    out = await ai_vision.analyze_product_dictation("une robe pour femme")
    assert out["prix"] is None
    assert out["genre"] == "femme"
