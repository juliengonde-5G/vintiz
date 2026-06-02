"""Product location events — mouvements de stock (flux vertical / horizontal)

Revision ID: 0055
Revises: 0054
Create Date: 2026-06-02

Table additive ``product_location_events`` : historise chaque déplacement
physique d'un article (réserve ↔ rayon = flux vertical ; zone ↔ zone = flux
horizontal). Source de vérité pour la timeline d'emplacement de la fiche
produit et pour les métriques de rotation.

Idempotent (IF NOT EXISTS). Aucune donnée existante touchée. ``move_type`` est
une simple colonne VARCHAR (l'enum est porté côté applicatif, native_enum=False).
"""

import sqlalchemy as sa
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        """
        CREATE TABLE IF NOT EXISTS product_location_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            move_type VARCHAR(20) NOT NULL,
            from_status VARCHAR(30),
            to_status VARCHAR(30),
            from_zone_id UUID REFERENCES store_zones(id),
            to_zone_id UUID REFERENCES store_zones(id),
            user_id UUID REFERENCES users(id),
            source VARCHAR(20) NOT NULL DEFAULT 'manual',
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    ))
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_product_location_events_product_id "
        "ON product_location_events (product_id);",
        "CREATE INDEX IF NOT EXISTS ix_product_location_events_occurred_at "
        "ON product_location_events (occurred_at);",
        "CREATE INDEX IF NOT EXISTS ix_product_location_events_move_type "
        "ON product_location_events (move_type);",
        "CREATE INDEX IF NOT EXISTS ix_product_location_product_time "
        "ON product_location_events (product_id, occurred_at);",
        "CREATE INDEX IF NOT EXISTS ix_product_location_type_time "
        "ON product_location_events (move_type, occurred_at);",
    ):
        conn.execute(sa.text(stmt))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS product_location_events;"))
