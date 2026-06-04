"""Articles permanents — produits à quantité illimitée vendus en caisse.

Distincts de ``Product`` (qui modélise une pièce unique seconde main) : un
``PermanentItem`` représente un article neuf en libre flux (sac réutilisable,
papier cadeau, accessoires...). Pas d'inventaire / sell-through / lifecycle —
un même code-barres se scanne autant de fois qu'on veut. Toutes les ventes
sont attribuées à la zone virtuelle "Vente Caisse" pour le suivi de
performance.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PermanentItem(Base):
    __tablename__ = "permanent_items"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    barcode: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    sale_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tva_rate: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, default=20.00)
    # Photo brute et copie vitrine détourée (off-white + logo). Suit la même
    # convention que ``Product.photo_url`` / ``storefront_photo_url`` pour
    # rester compatible avec ``StorefrontPhotoService``.
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storefront_photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Date à partir de laquelle l'article est mis en vente. Avant cette
    # date, la fiche est créée mais l'article n'est ni proposé en caisse
    # ni listé dans les recherches publiques (utile pour préparer un lancement).
    available_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Activation : un article désactivé n'est plus scannable (le POS le
    # refuse) mais reste consultable dans /inventory/permanent pour
    # l'historique de ses ventes passées.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
