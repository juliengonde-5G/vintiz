"""AI Vision service: analyze product photos using Claude Vision.

Detects clothing type, color, size estimate, brand clues, condition,
and suggests category + price range.
"""

import base64
import logging
from pathlib import Path

import anthropic

from app.core.config import settings

logger = logging.getLogger("vintiz.ai.vision")

SYSTEM_PROMPT = """Tu es un assistant expert en mode feminine seconde main premium.
Tu analyses des photos de vetements pour une boutique de seconde main haut de gamme.

A partir de la photo, tu dois identifier :
1. **type** : le type de vetement (robe, pantalon, veste, manteau, pull, chemise, jupe, top, accessoire, chaussures, sac, etc.)
2. **couleur** : la couleur principale et eventuellement secondaire
3. **matiere** : la matiere estimee (coton, laine, soie, polyester, cuir, jean/denim, lin, etc.)
4. **marque** : si une etiquette ou un logo est visible, identifier la marque. Sinon "non identifiee"
5. **taille** : si une etiquette de taille est visible, la lire. Sinon estimer (XS, S, M, L, XL, ou taille numerique)
6. **etat** : excellent, tres bon, bon, correct (pour de la seconde main premium, on attend minimum "bon")
7. **saison** : ete, hiver, mi-saison, toute saison
8. **style** : casual, chic, sportswear, soiree, business, boheme, etc.
9. **description** : une description courte (1-2 phrases) pour l'etiquette/fiche produit
10. **gamme_estimee** : entree, moyenne, premium (basee sur la qualite apparente, la marque, la matiere)

Reponds UNIQUEMENT en JSON valide, sans texte autour. Format :
{
  "type": "...",
  "couleur": "...",
  "couleur_secondaire": "..." ou null,
  "matiere": "...",
  "marque": "..." ou "non identifiee",
  "taille": "...",
  "etat": "excellent|tres bon|bon|correct",
  "saison": "ete|hiver|mi-saison|toute saison",
  "style": "...",
  "description": "...",
  "gamme_estimee": "entree|moyenne|premium",
  "confiance": 0.0-1.0
}"""


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
        system=SYSTEM_PROMPT,
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


async def analyze_photo_from_url(photo_url: str) -> dict:
    """Analyze a product photo from a URL."""
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
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
