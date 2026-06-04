"""Articles permanents — catalogue à quantité illimitée + zone Vente Caisse

Revision ID: 0058
Revises: 0057
Create Date: 2026-06-04

Crée la table ``permanent_items`` (sacs réutilisables, papier cadeau,
accessoires neufs en libre flux) + la colonne nullable
``transaction_items.permanent_item_id`` pour tracer les ventes dans
l'historique de chaque fiche.

Crée également la zone virtuelle « Vente Caisse » (idempotent) — toutes les
ventes d'articles permanents y sont attribuées pour le suivi de
performance. Idempotent : ne touche rien si la zone existe déjà.
"""
import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    if is_pg:
        conn.execute(sa.text(
            """
            CREATE TABLE IF NOT EXISTS permanent_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                barcode VARCHAR(50) NOT NULL UNIQUE,
                category_id UUID NOT NULL REFERENCES categories(id),
                sale_price NUMERIC(10, 2) NOT NULL DEFAULT 0,
                tva_rate NUMERIC(4, 2) NOT NULL DEFAULT 20.00,
                photo_url TEXT,
                storefront_photo_url TEXT,
                available_from TIMESTAMPTZ,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                description TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        ))
        conn.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_permanent_items_is_active ON permanent_items(is_active);"
        ))
        conn.execute(sa.text(
            "ALTER TABLE transaction_items ADD COLUMN IF NOT EXISTS permanent_item_id UUID REFERENCES permanent_items(id);"
        ))
        conn.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_transaction_items_permanent_item_id ON transaction_items(permanent_item_id);"
        ))

        # Zone virtuelle « Vente Caisse » — idempotent. Pas de plan 2D
        # (pos_x/y minimaux), pas de capacité (-1 sentinelle « illimité »),
        # auto_assign=false pour ne JAMAIS recevoir un produit seconde main
        # via le moteur de placement automatique.
        conn.execute(sa.text(
            """
            INSERT INTO store_zones (
                id, name, description, capacity, color_code,
                pos_x, pos_y, width, height, shape, display_order,
                auto_assign, assignment_priority,
                created_at, updated_at
            )
            SELECT
                gen_random_uuid(), 'Vente Caisse',
                'Articles permanents vendus en caisse (sacs, accessoires neufs)',
                0, '#8E7B57',
                85, 85, 12, 12, 'rounded', 99,
                FALSE, 999,
                NOW(), NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM store_zones WHERE name = 'Vente Caisse'
            );
            """
        ))
    else:
        # SQLite (tests) — types portables.
        op.create_table(
            "permanent_items",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("barcode", sa.String(50), nullable=False, unique=True),
            sa.Column("category_id", sa.String(36), sa.ForeignKey("categories.id"), nullable=False),
            sa.Column("sale_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("tva_rate", sa.Numeric(4, 2), nullable=False, server_default="20.00"),
            sa.Column("photo_url", sa.Text, nullable=True),
            sa.Column("storefront_photo_url", sa.Text, nullable=True),
            sa.Column("available_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.add_column(
            "transaction_items",
            sa.Column("permanent_item_id", sa.String(36), sa.ForeignKey("permanent_items.id"), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"
    if is_pg:
        conn.execute(sa.text("DELETE FROM store_zones WHERE name = 'Vente Caisse';"))
        conn.execute(sa.text("ALTER TABLE transaction_items DROP COLUMN IF EXISTS permanent_item_id;"))
        conn.execute(sa.text("DROP TABLE IF EXISTS permanent_items;"))
    else:
        op.drop_column("transaction_items", "permanent_item_id")
        op.drop_table("permanent_items")
