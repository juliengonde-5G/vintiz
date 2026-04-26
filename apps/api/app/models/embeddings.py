"""Vector embeddings for products and customers (P1-004).

Two tables, each holding two parallel vector spaces:
- ``visual`` — derived from Claude Vision attributes (category, color,
  brand tier, condition, season, style, …) hot-encoded into a fixed
  vector. Until a real CNN/CLIP encoder is plugged in, this is a
  deterministic signature that captures the structured attributes.
- ``text`` — derived from the description / brand / category names via
  a simple bag-of-features encoder; will be replaced with a sentence
  encoder (Voyage AI or similar) later. The split mirrors the audit's
  V1 §4.6.1 schema and lets us upgrade each axis independently.

Customer taste profiles are weighted centroids of their purchased
products' embeddings. Recomputed by a daily batch (see
``EmbeddingService.recompute_taste_profile``) so the recommender always
sees a fresh signal.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import UUIDType, vector_type


# Dimension chosen to balance expressivity vs. storage / compute cost.
# Vernon's catalogue tops out around 10 k products; 256-dim is plenty for
# nearest-neighbour search and small enough that JSON tests stay cheap.
EMBEDDING_DIM = 256


class ProductEmbedding(Base):
    __tablename__ = "product_embeddings"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("products.id"), unique=True, nullable=False
    )
    visual_embedding: Mapped[list[float] | None] = mapped_column(
        vector_type(EMBEDDING_DIM), nullable=True
    )
    text_embedding: Mapped[list[float] | None] = mapped_column(
        vector_type(EMBEDDING_DIM), nullable=True
    )
    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Pinned at compute time so a future ``recompute_all`` can detect
    # which rows are stale relative to the current encoder version.
    algo_version: Mapped[str | None] = mapped_column(String(50), nullable=True)


class CustomerTasteProfile(Base):
    __tablename__ = "customer_taste_profiles"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("clients.id"), unique=True, nullable=False
    )
    visual_centroid: Mapped[list[float] | None] = mapped_column(
        vector_type(EMBEDDING_DIM), nullable=True
    )
    text_centroid: Mapped[list[float] | None] = mapped_column(
        vector_type(EMBEDDING_DIM), nullable=True
    )
    n_purchases_analyzed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    algo_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
