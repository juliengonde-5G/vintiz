"""AI Vision service: analyze product photos using Claude Vision.

Detects clothing type, color, size estimate, brand clues, condition,
and suggests category + price range.

The system prompt lives in ``apps/api/prompts/v1/ai_vision.md`` and is
loaded by ``app.core.prompts.load_prompt`` (see T2 audit tech debt —
unification des prompts dispersés).
"""

import base64
import logging

import anthropic

from app.core.config import settings
from app.core.prompts import load_prompt

logger = logging.getLogger("vintiz.ai.vision")


_AI_VISION_FALLBACK = (
    "Tu es un assistant expert en mode feminine seconde main premium. "
    "Analyse la photo et renvoie un JSON avec : type, couleur, matiere, "
    "marque, taille, etat, saison, style, occasion, motif, coupe, "
    "defauts, description, gamme_estimee, confiance. Repondez UNIQUEMENT "
    "en JSON valide."
)


def _system_prompt() -> str:
    return load_prompt("ai_vision", fallback=_AI_VISION_FALLBACK)


# Allowed values per enriched field (P2-013). Validators below enforce
# these so a hallucinated value from Claude doesn't pollute downstream
# embeddings or scoring.
ALLOWED_STYLES = {
    "minimaliste", "vintage", "boheme", "chic", "sport",
    "rock", "romantique", "casual", "business",
}
ALLOWED_OCCASIONS = {
    "quotidien", "bureau", "soiree", "weekend",
    "ceremonie", "ete", "festival",
}
ALLOWED_PATTERNS = {
    "uni", "raye", "fleuri", "carreaux", "pois",
    "animal", "geometrique", "autre",
}
ALLOWED_CUTS = {
    "slim", "droit", "oversize", "cintre", "fluide", "ample", "ajuste",
}
# Genre détecté — aligné sur l'enum Gender (modèle) : base de l'affectation
# automatique des zones. "mixte" = unisexe / indéterminé.
ALLOWED_GENDERS = {"homme", "femme", "enfant", "mixte"}


_GENDER_SYNONYMS = {
    "homme": "homme", "h": "homme", "men": "homme", "man": "homme",
    "masculin": "homme",
    "femme": "femme", "f": "femme", "women": "femme", "woman": "femme",
    "feminin": "femme", "feminine": "femme",
    "enfant": "enfant", "kid": "enfant", "kids": "enfant", "child": "enfant",
    "fille": "enfant", "garcon": "enfant", "bebe": "enfant", "junior": "enfant",
    "mixte": "mixte", "unisexe": "mixte", "unisex": "mixte", "u": "mixte",
}


def normalize_gender(value) -> str | None:
    """Map a free-form gender to one of homme|femme|enfant|mixte (or None).

    Tolerant to FR/EN synonyms and accents so a slightly off Vision answer
    still lands on a valid value; unknown → None (caller decides the default).
    """
    if not isinstance(value, str):
        return None
    s = value.strip().lower()
    for accented, plain in (
        ("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"), ("ç", "c"), ("à", "a"),
    ):
        s = s.replace(accented, plain)
    if not s:
        return None
    mapped = _GENDER_SYNONYMS.get(s)
    if mapped:
        return mapped
    return s if s in ALLOWED_GENDERS else None


def normalize_vision_payload(payload: dict) -> dict:
    """Normalise the JSON returned by Claude Vision (P2-013).

    - Lowercases free-form strings, strips accents-aware.
    - Filters style / occasion / motif / coupe against the allowed sets.
    - Coerces ``defauts`` to a clean list[str].
    - Clamps ``confiance`` to [0, 1].

    Returns a fresh dict, leaving the original untouched. Unknown enum
    values fall back to ``None`` so callers can spot the gap.
    """
    if not isinstance(payload, dict):
        return {}

    def _lower(value):
        if not isinstance(value, str):
            return None
        s = value.strip().lower()
        return s or None

    def _filter(value, allowed):
        v = _lower(value)
        return v if v in allowed else None

    out = dict(payload)
    out["style"] = _filter(payload.get("style"), ALLOWED_STYLES)
    out["motif"] = _filter(payload.get("motif"), ALLOWED_PATTERNS)
    out["coupe"] = _filter(payload.get("coupe"), ALLOWED_CUTS)
    out["genre"] = normalize_gender(payload.get("genre"))

    raw_occ = payload.get("occasion")
    if isinstance(raw_occ, str):
        raw_occ = [raw_occ]
    if isinstance(raw_occ, list):
        out["occasion"] = [
            o for o in (_lower(x) for x in raw_occ) if o in ALLOWED_OCCASIONS
        ]
    else:
        out["occasion"] = []

    raw_def = payload.get("defauts")
    if isinstance(raw_def, str):
        raw_def = [raw_def]
    if isinstance(raw_def, list):
        out["defauts"] = [
            d.strip() for d in raw_def
            if isinstance(d, str) and d.strip()
        ]
    else:
        out["defauts"] = []

    conf = payload.get("confiance")
    try:
        conf_f = float(conf) if conf is not None else None
    except (TypeError, ValueError):
        conf_f = None
    if conf_f is not None:
        out["confiance"] = max(0.0, min(1.0, conf_f))

    return out


async def analyze_product_photo(
    image_data: bytes,
    media_type: str = "image/jpeg",
) -> dict:
    """Analyze a product photo using Claude Vision.

    Args:
        image_data: Raw image bytes.
        media_type: MIME type (image/jpeg, image/png, image/webp).

    Returns:
        Dict with detected attributes.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    b64_image = base64.b64encode(image_data).decode("utf-8")

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=_system_prompt(),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Analyse cette photo de vetement pour mise en vente dans notre boutique Vintiz (seconde main premium feminin).",
                    },
                ],
            }
        ],
    )

    import json

    raw = message.content[0].text.strip()
    # Handle markdown code blocks
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude Vision response: %s", raw[:200])
        result = {"error": "Impossible d'analyser la photo", "raw": raw[:500]}

    return result


_DICTATION_SYSTEM_PROMPT = (
    "Tu assistes la mise en vente d'un vêtement de seconde main premium chez "
    "Vintiz. À partir d'une DICTÉE LIBRE en français (le vendeur décrit l'article "
    "à voix haute), tu extrais les caractéristiques structurées.\n\n"
    "Renvoie UNIQUEMENT un objet JSON (aucun texte autour) avec ces clés :\n"
    "  type        : nature du vêtement (ex. \"chemise\", \"robe\", \"jean\")\n"
    "  couleur     : couleur principale\n"
    "  matiere     : matière si dictée\n"
    "  marque      : marque si dictée, sinon null\n"
    "  taille      : taille (XS,S,M,L,XL, 36..46, etc.)\n"
    "  etat        : état (\"neuf\", \"très bon état\", \"bon état\", \"satisfaisant\")\n"
    "  genre       : un de \"homme\",\"femme\",\"enfant\",\"mixte\"\n"
    "  prix        : prix de vente en euros (nombre) si dicté, sinon null\n"
    "  description : courte description si pertinente\n"
    "  confiance   : ta confiance globale entre 0 et 1\n\n"
    "Mets null (ou omets) toute information NON dictée — n'invente jamais une "
    "marque ni un prix. Réponds en français."
)


async def analyze_product_dictation(transcript: str) -> dict:
    """Extrait des champs produit structurés à partir d'une dictée libre.

    Pendant l'ajout produit, en complément (optionnel) de la reconnaissance
    photo, le vendeur peut dicter la fiche. On renvoie le MÊME schéma de clés
    que la vision (``type``/``couleur``/``marque``/``taille``/``etat``/``genre``
    …) + ``prix`` pour que le front réutilise le même mapping. Champs non dictés
    → null (jamais d'invention)."""
    transcript = (transcript or "").strip()
    if not transcript:
        return {"error": "Dictée vide"}
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    import json

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=_DICTATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript[:2000]}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse dictation response: %s", raw[:200])
        return {"error": "Impossible d'analyser la dictée", "raw": raw[:500]}

    result = normalize_vision_payload(payload)
    # Prix : tolère "12", "12.5", "12,50", "12 €"…
    raw_price = payload.get("prix")
    price_val = None
    if isinstance(raw_price, (int, float)):
        price_val = float(raw_price)
    elif isinstance(raw_price, str):
        cleaned = (
            raw_price.replace("€", "").replace("EUR", "").replace(",", ".").strip()
        )
        try:
            price_val = float(cleaned)
        except ValueError:
            price_val = None
    result["prix"] = price_val if (price_val is not None and price_val > 0) else None
    result["transcript"] = transcript
    return result


async def analyze_photo_from_url(photo_url: str) -> dict:
    """Analyze a product photo from a URL."""
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=_system_prompt(),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "url",
                            "url": photo_url,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Analyse cette photo de vetement pour mise en vente dans notre boutique Vintiz (seconde main premium feminin).",
                    },
                ],
            }
        ],
    )

    import json

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude Vision response: %s", raw[:200])
        result = {"error": "Impossible d'analyser la photo", "raw": raw[:500]}

    return result
