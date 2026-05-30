"""Embedding pipeline for products and customers (P1-004).

The vectors live in two parallel spaces (visual + text) and are computed
by a deterministic hashing-trick encoder. The encoder is intentionally a
placeholder: a future ticket will swap it for a real image encoder
(CLIP / SigLIP) on the visual axis and a sentence encoder (Voyage AI,
sentence-transformers, …) on the text axis. Until then, the structure
captured by the structured Vision attributes (category, brand tier,
colour, season, condition) is enough to drive a useful Personal Shopper
v1.

The service stays portable: both SQLite (tests) and PostgreSQL+pgvector
(prod) accept ``list[float]`` payloads thanks to ``models.types.vector_type``.
Similarity ranking runs in Python with NumPy — Vernon's catalogue tops
out around 10 k products, where a full sweep takes < 50 ms. When volume
justifies it, swap ``find_similar_products`` for an SQL query that uses
the HNSW index created in migration 0008.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import LoyaltyAccount
from app.models.embeddings import (
    EMBEDDING_DIM,
    CustomerTasteProfile,
    ProductEmbedding,
)
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Product, ProductStatus


ALGO_VERSION = "v1-hashing-trick-2026-04"

# How aggressively we down-weight older purchases when computing a customer
# taste centroid. Tuned so a purchase 6 months old has ~half the weight
# of a fresh one.
TASTE_HALF_LIFE_DAYS = 180


# ---------------------------------------------------------------------------
# Hashing-trick encoder (deterministic, portable, no ML deps)
# ---------------------------------------------------------------------------


def _bucket(feature: str, dim: int) -> int:
    """Hash a feature string into a bucket index in [0, dim)."""
    h = hashlib.sha1(feature.encode("utf-8")).digest()
    # Use the first 8 bytes as an unsigned int for a uniform distribution.
    val = int.from_bytes(h[:8], "big", signed=False)
    return val % dim


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def _encode_features(features: Iterable[tuple[str, str]], dim: int = EMBEDDING_DIM) -> list[float]:
    """Encode (feature_name, value) pairs into a fixed-length normalized vector.

    Uses the hashing trick: each ``"name=value"`` pair maps to one bucket;
    a sign hash spreads positive / negative weights so collisions don't
    systematically reinforce. The output is L2-normalised so cosine
    similarity is just a dot product.
    """
    vec = [0.0] * dim
    for name, value in features:
        if not value:
            continue
        token = f"{name}={value}".lower().strip()
        idx = _bucket(token, dim)
        # Second hash for the sign so collisions cancel rather than pile up.
        sign = 1.0 if hashlib.md5(token.encode()).digest()[0] & 1 else -1.0
        vec[idx] += sign
    return _l2_normalize(vec)


def _price_bucket(value) -> str:
    if value is None:
        return "unknown"
    v = float(value)
    if v < 10:
        return "<10"
    if v < 25:
        return "10-25"
    if v < 50:
        return "25-50"
    if v < 100:
        return "50-100"
    if v < 200:
        return "100-200"
    return ">=200"


def _tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    cleaned = re.sub(r"[^a-zA-Zàâäéèêëîïôùûüç0-9 ]", " ", text.lower())
    return [tok for tok in cleaned.split() if len(tok) > 2]


def _visual_features(product: Product) -> list[tuple[str, str]]:
    """Structured signals that capture what the piece *looks* like."""
    feats: list[tuple[str, str]] = [
        ("category_id", str(product.category_id) if product.category_id else ""),
        ("brand", (product.brand or "").lower()),
        ("color", (product.color or "").lower()),
        ("size", (product.size or "").lower()),
        ("condition", (product.condition or "").lower()),
        ("price_bucket", _price_bucket(product.sale_price)),
    ]
    return feats


def _text_features(product: Product) -> list[tuple[str, str]]:
    """Tokens that capture what the piece is *called* and *described* as."""
    feats: list[tuple[str, str]] = [
        ("brand", (product.brand or "").lower()),
        ("category_id", str(product.category_id) if product.category_id else ""),
    ]
    for token in _tokenize(product.name):
        feats.append(("name_token", token))
    for token in _tokenize(getattr(product, "description", None)):
        feats.append(("desc_token", token))
    return feats


def _cosine(a: list[float] | None, b: list[float] | None) -> float:
    """Cosine similarity for two pre-normalised vectors. Returns 0.0 if either
    is missing — the caller decides what to do with a non-comparable pair."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EmbeddingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- Per-product compute -------------------------------------------------

    async def compute_for_product(self, product: Product) -> ProductEmbedding:
        """Compute (or refresh) the embedding row for one product."""
        visual = _encode_features(_visual_features(product))
        text = _encode_features(_text_features(product))

        result = await self.db.execute(
            select(ProductEmbedding).where(
                ProductEmbedding.product_id == product.id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = ProductEmbedding(
                product_id=product.id,
                visual_embedding=visual,
                text_embedding=text,
                computed_at=datetime.now(timezone.utc),
                algo_version=ALGO_VERSION,
            )
            self.db.add(row)
        else:
            row.visual_embedding = visual
            row.text_embedding = text
            row.computed_at = datetime.now(timezone.utc)
            row.algo_version = ALGO_VERSION

        await self.db.flush()
        return row

    async def recompute_all_products(
        self, only_missing: bool = False
    ) -> dict:
        """Iterate the catalogue and (re)compute embeddings.

        Returns a summary with the number of rows touched. Used by the
        admin endpoint and the daily cron.
        """
        # Load every active product. With ~10 k rows this stays in memory.
        query = select(Product).where(
            Product.status.in_(
                [ProductStatus.stock, ProductStatus.display, ProductStatus.sold]
            )
        )
        result = await self.db.execute(query)
        products = result.scalars().all()

        existing_versions: dict = {}
        if only_missing:
            existing = await self.db.execute(
                select(ProductEmbedding.product_id, ProductEmbedding.algo_version)
            )
            existing_versions = dict(existing.all())

        touched = 0
        for product in products:
            if only_missing and existing_versions.get(product.id) == ALGO_VERSION:
                continue
            await self.compute_for_product(product)
            touched += 1

        return {
            "scanned": len(products),
            "recomputed": touched,
            "algo_version": ALGO_VERSION,
        }

    # -- Customer taste centroid --------------------------------------------

    async def recompute_taste_profile(
        self, customer_id, max_transactions: int = 15
    ) -> CustomerTasteProfile | None:
        """Build a customer's taste centroid from the products bought across
        her last ``max_transactions`` sale transactions, weighted exponentially
        by the transaction date.

        A purchase = one transaction = 1+ products; **all** products of those
        transactions feed the centroid (not the last N items). Returns the
        (possibly newly inserted) ``CustomerTasteProfile`` row, or ``None`` if
        the customer has no analyzable purchases.
        """
        # 1. The customer's most-recent sale transactions (newest first).
        #    V2: gifts (exclude_from_taste) are filtered out — an atypical
        #    purchase would otherwise pollute the centroid for 180 days.
        recent_tx = (
            select(Transaction.id, Transaction.created_at)
            .where(
                Transaction.client_id == customer_id,
                Transaction.transaction_type == TransactionType.sale,
                Transaction.exclude_from_taste.is_(False),
            )
            .order_by(Transaction.created_at.desc())
            .limit(max_transactions)
            .subquery()
        )
        # 2. Every line item of those transactions, carrying the transaction
        #    date for the recency weighting below.
        query = (
            select(TransactionItem, recent_tx.c.created_at)
            .join(recent_tx, TransactionItem.transaction_id == recent_tx.c.id)
            .where(TransactionItem.product_id.is_not(None))
        )
        result = await self.db.execute(query)
        rows = result.all()
        if not rows:
            return None

        product_ids = [row[0].product_id for row in rows]
        emb_result = await self.db.execute(
            select(ProductEmbedding).where(
                ProductEmbedding.product_id.in_(product_ids)
            )
        )
        emb_by_product = {
            e.product_id: e for e in emb_result.scalars().all()
        }

        now = datetime.now(timezone.utc)
        visual_sum = [0.0] * EMBEDDING_DIM
        text_sum = [0.0] * EMBEDDING_DIM
        weight_total = 0.0
        analyzed = 0
        for item, created_at in rows:
            emb = emb_by_product.get(item.product_id)
            if emb is None or emb.visual_embedding is None:
                continue
            # Exponential decay: weight halves every TASTE_HALF_LIFE_DAYS.
            if created_at is None:
                age_days = 0
            else:
                created_at_aware = (
                    created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
                )
                age_days = max(0.0, (now - created_at_aware).total_seconds() / 86400.0)
            weight = 0.5 ** (age_days / TASTE_HALF_LIFE_DAYS)
            for i in range(EMBEDDING_DIM):
                visual_sum[i] += weight * emb.visual_embedding[i]
                if emb.text_embedding is not None:
                    text_sum[i] += weight * emb.text_embedding[i]
            weight_total += weight
            analyzed += 1

        if analyzed == 0:
            return None

        visual_centroid = _l2_normalize(
            [x / weight_total for x in visual_sum]
        )
        text_centroid = _l2_normalize([x / weight_total for x in text_sum])

        existing = await self.db.execute(
            select(CustomerTasteProfile).where(
                CustomerTasteProfile.customer_id == customer_id
            )
        )
        profile = existing.scalar_one_or_none()
        if profile is None:
            profile = CustomerTasteProfile(
                customer_id=customer_id,
                visual_centroid=visual_centroid,
                text_centroid=text_centroid,
                n_purchases_analyzed=analyzed,
                computed_at=now,
                algo_version=ALGO_VERSION,
            )
            self.db.add(profile)
        else:
            profile.visual_centroid = visual_centroid
            profile.text_centroid = text_centroid
            profile.n_purchases_analyzed = analyzed
            profile.computed_at = now
            profile.algo_version = ALGO_VERSION

        await self.db.flush()
        return profile

    # -- Similarity search --------------------------------------------------

    async def find_similar_products(
        self,
        profile: CustomerTasteProfile,
        top_k: int = 10,
        statuses: list[ProductStatus] | None = None,
        visual_weight: float = 0.6,
        text_weight: float = 0.4,
    ) -> list[tuple[Product, float]]:
        """Return the ``top_k`` products closest to the profile's centroids.

        Filters out products outside ``statuses`` (default: stock/display).
        Mixes visual + text cosine similarities with the configured weights.
        """
        statuses = statuses or [ProductStatus.stock, ProductStatus.display]

        query = (
            select(Product, ProductEmbedding)
            .join(
                ProductEmbedding,
                ProductEmbedding.product_id == Product.id,
            )
            .where(Product.status.in_(statuses))
        )
        result = await self.db.execute(query)
        rows = result.all()

        scored: list[tuple[Product, float]] = []
        for product, emb in rows:
            v = _cosine(profile.visual_centroid, emb.visual_embedding)
            t = _cosine(profile.text_centroid, emb.text_embedding)
            score = visual_weight * v + text_weight * t
            scored.append((product, score))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]
