"""Product location ledger — mouvements de stock (flux vertical / horizontal).

Historise chaque déplacement physique d'un article dans la boutique :

- **flux vertical** : réserve (``ProductStatus.stock``, la cave) ↔ rayon
  (``display`` / ``displayed``). C'est le réassort « au fil de l'eau » : le
  personnel monte des pièces de la réserve quand les ventes vident un portant.
- **flux horizontal** : zone A → zone B en rayon. C'est l'aménagement
  hebdomadaire proposé par Vintiz IA (on déplace les pièces entre zones).

Table append-only, **typée** (colonnes ``from_*`` / ``to_*`` dédiées plutôt que
JSON) pour deux usages directs :

1. la fiche produit affiche la timeline complète de ses emplacements ;
2. les métriques de rotation agrègent ces lignes (rythme vertical = nb de
   mises en rayon / jour, rythme horizontal = nb de changements de zone /
   semaine), sans avoir à parser ``events_log.metadata``.

Les écritures passent toutes par ``app/services/stock_movement.py`` :
- ``ProductLifecycleService.transition`` (réserve↔rayon, sorties) ;
- l'édition inline d'une fiche (changement de zone) ;
- l'exécution scan du module de mouvements.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import UUIDType


class LocationMoveType(str, enum.Enum):
    """Nature du mouvement — pilote la classification des métriques."""

    intake = "intake"            # arrivée en boutique (réception / tri / étiquetage)
    to_floor = "to_floor"        # réserve → rayon (flux VERTICAL montant — mise en rayon)
    to_stock = "to_stock"        # rayon → réserve (flux VERTICAL descendant — retour réserve)
    zone_change = "zone_change"  # zone A → zone B en rayon (flux HORIZONTAL)
    exit = "exit"                # sortie définitive (don / retour centre de tri)


# native_enum=False → rendu VARCHAR + CHECK sur PostgreSQL ET SQLite (tests),
# donc pas de CREATE TYPE et la migration peut créer une simple colonne VARCHAR.
_MOVE_TYPE = Enum(
    LocationMoveType,
    name="location_move_type",
    native_enum=False,
    length=20,
    values_callable=lambda x: [e.value for e in x],
)


class ProductLocationEvent(Base):
    """Une ligne = un déplacement physique d'un article (cf. module docstring)."""

    __tablename__ = "product_location_events"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Distinct de created_at pour pouvoir backfiller des mouvements antérieurs
    # (intake rétroactif) sans réécrire l'horodatage technique de la ligne.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    move_type: Mapped[LocationMoveType] = mapped_column(_MOVE_TYPE, nullable=False, index=True)
    # Statuts produit (valeurs de ProductStatus) avant / après — stockés en
    # texte libre pour ne pas coupler la table au type enum ``product_status``.
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    from_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("store_zones.id"), nullable=True
    )
    to_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("store_zones.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("users.id"), nullable=True
    )
    # D'où vient le mouvement : scan | admin_edit | lifecycle | cron | seed.
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_product_location_product_time", "product_id", "occurred_at"),
        Index("ix_product_location_type_time", "move_type", "occurred_at"),
    )
