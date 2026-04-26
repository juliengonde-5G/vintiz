"""Cold-start onboarding for the Personal Shopper (P2-004).

A new customer has no purchase history, so the recommender has no
``CustomerTasteProfile`` to anchor the similarity search. The
onboarding flow asks them to pick 0–5 style profiles + answer 3 quiz
questions, then we synthesise a starter centroid from those choices
and persist it. The hashing-trick encoder from
``app.services.embeddings`` does the actual vector computation, so the
encoder version stays consistent with whatever the recommender is
already using.

Re-running the onboarding overwrites the previous cold-start row so
customers can iterate. Once they make a real purchase, the daily
``recompute_taste_profile`` cron replaces the cold-start centroid with
a real one and stamps ``algo_version`` accordingly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.embeddings import CustomerTasteProfile
from app.services.embeddings import _encode_features


COLD_START_ALGO_VERSION = "cold-start-v1-2026-04"


# Each style key maps to a bag of (feature_name, value) pairs. They feed the
# same hashing-trick encoder used by ProductEmbedding, so a customer whose
# cold-start centroid is built from "minimaliste" naturally lands close to
# minimalist products in the catalogue.
STYLE_PROFILES: dict[str, list[tuple[str, str]]] = {
    "minimaliste": [
        ("color", "noir"), ("color", "blanc"), ("color", "gris"),
        ("color", "beige"), ("style", "minimaliste"), ("style", "epure"),
    ],
    "vintage": [
        ("color", "marron"), ("color", "ocre"), ("color", "moutarde"),
        ("style", "vintage"), ("style", "retro"), ("pattern", "fleurs"),
    ],
    "boho": [
        ("color", "terracotta"), ("color", "blanc casse"),
        ("style", "boho"), ("style", "ethnique"), ("cut", "fluide"),
    ],
    "chic": [
        ("color", "noir"), ("color", "marine"),
        ("style", "chic"), ("style", "classique"), ("cut", "droit"),
    ],
    "sport": [
        ("color", "gris"), ("color", "bleu"),
        ("style", "sport"), ("style", "decontracte"), ("cut", "ample"),
    ],
    "rock": [
        ("color", "noir"), ("color", "rouge"),
        ("style", "rock"), ("style", "edgy"), ("material", "cuir"),
    ],
}


VALID_PRICE_BUCKETS = {"<10", "10-25", "25-50", "50-100", "100-200", ">=200"}
VALID_OCCASIONS = {"quotidien", "bureau", "soiree", "weekend", "ceremonie"}


def _features_from_choices(
    liked_style_keys: list[str],
    preferred_occasions: list[str] | None,
    preferred_price_buckets: list[str] | None,
    preferred_categories: list[str] | None,
) -> list[tuple[str, str]]:
    """Translate the onboarding answers into encoder features."""
    features: list[tuple[str, str]] = []

    for key in liked_style_keys:
        normalized = key.strip().lower()
        if normalized in STYLE_PROFILES:
            features.extend(STYLE_PROFILES[normalized])

    for occ in (preferred_occasions or []):
        norm = occ.strip().lower()
        if norm in VALID_OCCASIONS:
            features.append(("occasion", norm))

    for bucket in (preferred_price_buckets or []):
        norm = bucket.strip()
        if norm in VALID_PRICE_BUCKETS:
            features.append(("price_bucket", norm))

    for cat in (preferred_categories or []):
        norm = cat.strip().lower()
        if norm:
            features.append(("category_label", norm))

    return features


async def cold_start_taste_profile(
    db: AsyncSession,
    client: Client,
    *,
    liked_style_keys: list[str],
    preferred_occasions: list[str] | None = None,
    preferred_price_buckets: list[str] | None = None,
    preferred_categories: list[str] | None = None,
) -> CustomerTasteProfile:
    """Synthesise (or refresh) a cold-start CustomerTasteProfile."""
    visual_features = _features_from_choices(
        liked_style_keys,
        preferred_occasions,
        preferred_price_buckets,
        preferred_categories,
    )
    text_features = list(visual_features)  # same bag — works fine for v1

    visual_centroid = _encode_features(visual_features)
    text_centroid = _encode_features(text_features)

    existing = await db.execute(
        select(CustomerTasteProfile).where(
            CustomerTasteProfile.customer_id == client.id
        )
    )
    profile = existing.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if profile is None:
        profile = CustomerTasteProfile(
            customer_id=client.id,
            visual_centroid=visual_centroid,
            text_centroid=text_centroid,
            n_purchases_analyzed=0,
            computed_at=now,
            algo_version=COLD_START_ALGO_VERSION,
        )
        db.add(profile)
    else:
        # Refresh in place. n_purchases_analyzed stays at 0 to mark this
        # as cold-start; the daily cron replaces it with a real count
        # after the first purchase.
        profile.visual_centroid = visual_centroid
        profile.text_centroid = text_centroid
        profile.n_purchases_analyzed = 0
        profile.computed_at = now
        profile.algo_version = COLD_START_ALGO_VERSION

    await db.flush()
    return profile


def list_available_style_profiles() -> list[dict]:
    """Public catalogue of style keys for the picker UI."""
    return [
        {"key": "minimaliste", "label": "Minimaliste", "emoji": "⬜"},
        {"key": "vintage", "label": "Vintage", "emoji": "🎞️"},
        {"key": "boho", "label": "Bohème", "emoji": "🌾"},
        {"key": "chic", "label": "Chic", "emoji": "🖤"},
        {"key": "sport", "label": "Décontracté", "emoji": "👟"},
        {"key": "rock", "label": "Rock", "emoji": "⚡"},
    ]


def list_available_occasions() -> list[dict]:
    return [
        {"key": "quotidien", "label": "Quotidien"},
        {"key": "bureau", "label": "Bureau"},
        {"key": "soiree", "label": "Soirée"},
        {"key": "weekend", "label": "Week-end"},
        {"key": "ceremonie", "label": "Cérémonie"},
    ]


def list_available_price_buckets() -> list[dict]:
    return [
        {"key": "<10", "label": "Moins de 10 €"},
        {"key": "10-25", "label": "10 – 25 €"},
        {"key": "25-50", "label": "25 – 50 €"},
        {"key": "50-100", "label": "50 – 100 €"},
        {"key": "100-200", "label": "100 – 200 €"},
        {"key": ">=200", "label": "200 € et plus"},
    ]
