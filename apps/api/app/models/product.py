import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.types import JSONType


class Gender(str, enum.Enum):
    femme = "femme"
    homme = "homme"
    enfant = "enfant"
    mixte = "mixte"


# Shared enum type instance so ``categories.gender`` and ``products.gender``
# map to the SAME Postgres ``gender`` type (a second ``Enum(Gender, name=...)``
# instance would make create_all attempt a duplicate CREATE TYPE on boot).
GENDER_ENUM = Enum(Gender, name="gender")


class ProductStatus(str, enum.Enum):
    """Explicit life cycle of a thrift item from intake to terminal.

    Backward-compatible: ``stock`` and ``display`` predate the explicit
    flow and are kept; ``returned`` is now an alias for the more precise
    ``returned_to_sorting`` (kept for old rows). The new states map the
    V1 audit §2.2.6 flow:

    received → sorted → tagged → displayed →
      ├── sold                (terminal — paid)
      ├── donated             (terminal — commercial gesture)
      ├── returned_to_sorting (terminal — sent back to Solidarité Textiles)
      └── discounted → deep_discounted → returned_to_sorting
    """

    # Legacy values — kept so existing rows / queries still work.
    stock = "stock"
    display = "display"
    sold = "sold"
    returned = "returned"

    # New explicit life-cycle values.
    received = "received"
    sorted = "sorted"
    tagged = "tagged"
    displayed = "displayed"
    discounted = "discounted"
    deep_discounted = "deep_discounted"
    donated = "donated"
    returned_to_sorting = "returned_to_sorting"


class Category(Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    gender: Mapped[Gender] = mapped_column(
        GENDER_ENUM, nullable=False, default=Gender.mixte
    )
    # Désactivée = masquée des sélecteurs (création produit, picker zone) sans
    # toucher aux produits existants qui y sont rattachés. Additif : colonne
    # NOT NULL default true → les catégories existantes restent actives.
    # Voir migration 0050.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parent: Mapped["Category | None"] = relationship(
        "Category", remote_side="Category.id", lazy="selectin"
    )
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="category", lazy="noload"
    )


class Product(Base):
    __tablename__ = "products"

    barcode: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    size: Mapped[str | None] = mapped_column(String(20), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Convenience pointer to the primary image. Kept in sync with ProductPhoto
    # rows by PhotoService so existing call sites that read photo_url keep
    # working unchanged. Multi-photo support lives in the photos relation.
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Branded, background-removed copy of the primary photo — the image the
    # public storefront uses. Mirrors the primary ProductPhoto.processed_url,
    # maintained by PhotoService alongside photo_url.
    storefront_photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_price: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    sale_price: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    # Taux de TVA appliqué à ce produit en régime normal. Default 20 %
    # (taux normal vêtements adultes France). Override possible pour les
    # catégories à taux réduit (livres 5.5, chaussures enfant ≤ certains
    # seuils). Stocké au niveau produit + copié sur la ligne de
    # transaction au moment de la vente, pour audit DGFiP.
    tva_rate: Mapped[float] = mapped_column(
        Numeric(4, 2), nullable=False, default=20.00
    )
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status"),
        nullable=False,
        default=ProductStatus.stock,
    )
    condition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Genre du produit (homme | femme | enfant | mixte/unisexe). Saisi à
    # l'étape 2 de l'assistant d'ajout (proposé par la détection image) et
    # base de l'affectation automatique des zones (merchandising.suggest_zone).
    # Nullable + ajouté en additif : les fiches existantes restent à NULL et
    # retombent sur le genre de leur catégorie. Voir migration 0048.
    gender: Mapped[Gender | None] = mapped_column(GENDER_ENUM, nullable=True)
    week_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Life-cycle anchors (P1-006). ``received_at`` is set on first arrival
    # in the boutique; ``displayed_at`` snaps when the product first hits
    # the floor. They drive both the sell-through KPI (DOH) and the
    # automatic return-to-sorting cron (P3-007).
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    displayed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Append-only ledger of price changes. Each entry is a dict with at
    # least {"at", "from_price", "to_price", "reason"}. Read by the
    # markdown engine (P3-001) and the fiscal export.
    markdown_history: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("store_zones.id"), nullable=True
    )
    # Intake lot the product came in with (P2-015). Nullable so seed and
    # legacy products don't need to be backfilled.
    intake_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake_batches.id"), nullable=True
    )
    trend_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # v3 scoring (price positioning) — Claude-estimated median market price
    # on Vinted/LBC. Refreshed weekly by the Monday cron.
    market_price_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_price_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    shelf_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Flag for seed / demo data that should be selectively purged before
    # public opening. The pre-opening base (real intake) keeps the default
    # ``False`` and is therefore safe from ``scripts/purge_test_data.py``.
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    category: Mapped["Category"] = relationship(
        "Category", back_populates="products", lazy="selectin"
    )
    photos: Mapped[list["ProductPhoto"]] = relationship(
        "ProductPhoto",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductPhoto.order_index",
        lazy="selectin",
    )


class ProductPhoto(Base):
    """A single image attached to a Product.

    Ordering is explicit via ``order_index`` (lower → shown first). Exactly
    one row per product carries ``is_primary=True``; PhotoService enforces
    this invariant and mirrors the primary URL onto Product.photo_url.
    The AI-related fields capture Vision's analysis output so the score
    photos sub-component (P2-011) can later weight by quality + count.
    """

    __tablename__ = "product_photos"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # Background-removed, branded copy used by the storefront (generated
    # automatically at upload by StorefrontPhotoService). NULL until/unless a
    # background-removal backend is available.
    processed_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Generation outcome: ``done`` | ``skipped`` | ``failed`` | ``pending``
    # (NULL for legacy rows / photos added by URL without processing).
    processing_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    product: Mapped["Product"] = relationship(
        "Product", back_populates="photos", lazy="selectin"
    )


class PriceGrid(Base):
    __tablename__ = "price_grids"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    min_purchase: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    max_purchase: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    sale_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    category: Mapped["Category"] = relationship("Category", lazy="selectin")
