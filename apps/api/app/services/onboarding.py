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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.embeddings import (
    EMBEDDING_DIM,
    CustomerTasteProfile,
    ProductEmbedding,
)
from app.models.product import Gender, Product, ProductStatus
from app.services.embeddings import _encode_features, _l2_normalize


COLD_START_ALGO_VERSION = "cold-start-v1-2026-04"

# V1 onboarding "layer 1" — declarative qualification vocabularies. Locked by
# the PS 360 audit (§4.2 + §11 décision #6). Kept here so the API request
# models, the options endpoint and the persistence path share one source.
VALID_GENDERS = ("femme", "homme", "mixte")
VALID_AGE_BANDS = ("<25", "25-34", "35-44", "45-54", "55+")


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
    preferred_brands: list[str] | None = None,
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

    # L3 — marques préférées. Same ``brand`` feature key the product encoder
    # uses (see embeddings._visual_features), so a declared brand lands near
    # that brand's pieces.
    for brand in (preferred_brands or []):
        norm = brand.strip().lower()
        if norm:
            features.append(("brand", norm))

    return features


async def _liked_products_centroid(
    db: AsyncSession, liked_product_ids: list[str] | None
) -> tuple[list[float] | None, list[float] | None]:
    """Mean-pool the real ``ProductEmbedding`` vectors of the liked products.

    This is the "cold-start visuel" (layer 2): the customer hand-picks pieces
    she likes, and we average their existing catalogue embeddings into a first
    ``visual_centroid`` from *real* items (no recency decay — these are
    explicit, equally-weighted likes). Returns ``(None, None)`` when there is
    nothing to pool, so the caller can fall back to the declarative features.
    """
    if not liked_product_ids:
        return None, None

    ids: list = []
    for raw in liked_product_ids:
        try:
            ids.append(uuid.UUID(str(raw)))
        except (ValueError, TypeError, AttributeError):
            continue
    if not ids:
        return None, None

    result = await db.execute(
        select(ProductEmbedding).where(ProductEmbedding.product_id.in_(ids))
    )
    embeddings = result.scalars().all()

    visual_sum = [0.0] * EMBEDDING_DIM
    text_sum = [0.0] * EMBEDDING_DIM
    n_visual = 0
    n_text = 0
    for emb in embeddings:
        if emb.visual_embedding is not None:
            for i in range(EMBEDDING_DIM):
                visual_sum[i] += emb.visual_embedding[i]
            n_visual += 1
        if emb.text_embedding is not None:
            for i in range(EMBEDDING_DIM):
                text_sum[i] += emb.text_embedding[i]
            n_text += 1

    visual = _l2_normalize(visual_sum) if n_visual else None
    text = _l2_normalize(text_sum) if n_text else None
    return visual, text


def _blend(a: list[float] | None, b: list[float] | None) -> list[float] | None:
    """Combine two L2-normalised centroids into one (re-normalised) centroid.

    Returns whichever is present when only one is, ``None`` when neither is.
    Equal weight is deliberate for V1 — the declarative layers and the visual
    likes both deserve a say while the catalogue is cold.
    """
    if a is None:
        return b
    if b is None:
        return a
    return _l2_normalize([a[i] + b[i] for i in range(len(a))])


async def cold_start_taste_profile(
    db: AsyncSession,
    client: Client,
    *,
    gender: str | None = None,
    age_band: str | None = None,
    liked_style_keys: list[str] | None = None,
    preferred_occasions: list[str] | None = None,
    preferred_price_buckets: list[str] | None = None,
    preferred_categories: list[str] | None = None,
    preferred_brands: list[str] | None = None,
    liked_product_ids: list[str] | None = None,
) -> CustomerTasteProfile | None:
    """Run the layered onboarding for ``client`` and persist the outcome.

    - **Layer 1** (declarative, obligatoire): ``gender`` + ``age_band`` are
      stored on the ``Client`` row when valid.
    - **Layer 2** (cold-start visuel): ``liked_product_ids`` mean-pool into a
      first *real* ``visual_centroid`` from hand-picked pieces.
    - **Layer 3** (détaillé, facultatif): styles / occasions / budget / brands
      feed the hashing-trick encoder.

    Layers 2 and 3 are blended into one centroid (equal weight). Returns the
    upserted ``CustomerTasteProfile`` — or ``None`` when only layer 1 was
    completed (no style/visual signal yet): we deliberately do **not** write an
    all-zero centroid. The assumed empty state + trend alerts carry her until a
    real signal arrives.
    """
    # --- Layer 1: declarative qualification on the Client row ---------------
    if gender:
        g = gender.strip().lower()
        if g in VALID_GENDERS:
            client.gender_profile = g
    if age_band:
        band = age_band.strip()
        if band in VALID_AGE_BANDS:
            client.age_band = band

    # --- Layer 3: declarative style features (same bag for both axes) -------
    decl_features = _features_from_choices(
        liked_style_keys or [],
        preferred_occasions,
        preferred_price_buckets,
        preferred_categories,
        preferred_brands,
    )
    decl_centroid = _encode_features(decl_features) if decl_features else None

    # --- Layer 2: visual cold-start from real liked items -------------------
    liked_visual, liked_text = await _liked_products_centroid(
        db, liked_product_ids
    )

    visual_centroid = _blend(decl_centroid, liked_visual)
    text_centroid = _blend(decl_centroid, liked_text)

    if visual_centroid is None and text_centroid is None:
        # Layer 1 only — nothing to anchor a centroid on yet. The declarative
        # fields are already set above; flush so they persist, then stop.
        await db.flush()
        return None

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


def list_available_genders() -> list[dict]:
    """Layer 1 — declarative gender picker (vouvoiement, sans 'enfant')."""
    return [
        {"key": "femme", "label": "Femme"},
        {"key": "homme", "label": "Homme"},
        {"key": "mixte", "label": "Peu importe"},
    ]


def list_available_age_bands() -> list[dict]:
    """Layer 1 — declarative age band picker (bornes verrouillées §11)."""
    return [
        {"key": "<25", "label": "Moins de 25 ans"},
        {"key": "25-34", "label": "25 – 34 ans"},
        {"key": "35-44", "label": "35 – 44 ans"},
        {"key": "45-54", "label": "45 – 54 ans"},
        {"key": "55+", "label": "55 ans et plus"},
    ]


async def list_available_brands(db: AsyncSession, limit: int = 24) -> list[dict]:
    """Layer 3 — preferred-brands picker, drawn from the live catalogue.

    Returns the most-represented in-stock brands so the customer recognises the
    options. Empty list (the UI hides the section) when the catalogue is bare.
    """
    result = await db.execute(
        select(Product.brand, func.count(Product.id))
        .where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
            Product.brand.is_not(None),
            Product.brand != "",
        )
        .group_by(Product.brand)
        .order_by(func.count(Product.id).desc())
        .limit(limit)
    )
    return [
        {"key": brand, "label": brand}
        for brand, _count in result.all()
        if brand
    ]


async def pick_visual_candidates(
    db: AsyncSession, *, gender: str | None = None, n: int = 6
) -> list[dict]:
    """Layer 2 — products to show in the 5-photo "j'aime / j'aime pas" step.

    Picks a diverse (one-per-category), attractive set of in-stock pieces that
    actually have a photo, optionally narrowed to the declared gender (always
    keeping ``mixte`` / unset pieces). Prefers the Photoroom-styled image so
    the picker matches the editorial look of the rest of the espace client.
    """
    query = (
        select(Product)
        .where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
            Product.photo_url.is_not(None),
            Product.photo_url != "",
        )
    )
    g = (gender or "").strip().lower()
    if g in ("femme", "homme"):
        query = query.where(
            Product.gender.in_([Gender(g), Gender.mixte])
            | Product.gender.is_(None)
        )
    # Surface attractive pieces first; NULL trend scores sort last.
    query = query.order_by(
        Product.trend_score.is_(None),
        Product.trend_score.desc(),
        Product.created_at.desc(),
    ).limit(max(n * 6, 24))

    rows = (await db.execute(query)).scalars().all()

    diversified: list[Product] = []
    seen_categories: set = set()
    for product in rows:
        if product.category_id in seen_categories:
            continue
        diversified.append(product)
        seen_categories.add(product.category_id)
        if len(diversified) >= n:
            break
    # Top up from the remaining pool if categories were too few to reach n.
    if len(diversified) < n:
        for product in rows:
            if product in diversified:
                continue
            diversified.append(product)
            if len(diversified) >= n:
                break

    return [
        {
            "id": str(p.id),
            "name": p.name,
            "brand": p.brand,
            "size": p.size,
            "color": p.color,
            "price_cents": int(round(float(p.sale_price or 0) * 100)),
            "photo_url": p.storefront_photo_url or p.photo_url,
        }
        for p in diversified
    ]
