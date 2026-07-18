"""Historique des lectures douchette (scan log POS).

Outil de diagnostic — PAS un registre fiscal. Chaque appel à
``GET /inventory/products/by-barcode/{barcode}`` laisse une ligne, hit OU
miss, pour reconstituer le panier d'une vente CB « orpheline » (paiement
SumUp encaissé mais vente jamais validée) : les scans qui précèdent le
paiement donnent le contenu du panier. ``product_name`` / ``sale_price``
sont dénormalisés pour survivre à la suppression du produit (FK en
SET NULL). Rétention 7 jours — purge quotidienne dans ``app/jobs.py``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProductScanLog(Base):
    __tablename__ = "product_scan_logs"
    # La purge (7 j) et la reconstitution d'un panier filtrent sur une
    # fenêtre horaire → index sur created_at (colonne héritée de Base).
    __table_args__ = (Index("ix_product_scan_logs_created_at", "created_at"),)

    # Code tel qu'arrivé de la douchette (garbage AZERTY/CapsLock compris)
    # vs code après strip/normalisation — les deux servent au diagnostic
    # « pourquoi ce scan n'a rien trouvé ».
    barcode_raw: Mapped[str] = mapped_column(String(100), nullable=False)
    barcode_normalized: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    permanent_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permanent_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sale_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
