"""Add tva_rate to products and transaction_items.

Régime normal de TVA confirmé (cf. audit conformité 2026-05). Default 20 %
sur les vêtements adultes ; le champ permet d'auditer le taux appliqué à
chaque ligne de transaction lors d'un contrôle DGFiP, et d'ouvrir le cas
échéant un taux réduit (5,5 % livres, chaussures enfant, etc.) sans
casser la chaîne NF525 existante.

Idempotente : peut être rejouée sans dupliquer la colonne, grâce au check
``_column_exists`` (cohérent avec la migration 0035).

Revision ID: 0036
Revises: 0035
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return column in {c["name"] for c in inspector.get_columns(table)}
    except Exception:
        return False


def upgrade() -> None:
    # Default 20 % TVA — taux normal France pour les vêtements.
    # NUMERIC(4,2) couvre 0.00 à 99.99 (suffisant pour 0/2.1/5.5/10/20).
    if not _column_exists("products", "tva_rate"):
        op.add_column(
            "products",
            sa.Column(
                "tva_rate",
                sa.Numeric(4, 2),
                nullable=False,
                server_default=sa.text("20.00"),
            ),
        )

    if not _column_exists("transaction_items", "tva_rate"):
        op.add_column(
            "transaction_items",
            sa.Column(
                "tva_rate",
                sa.Numeric(4, 2),
                nullable=False,
                server_default=sa.text("20.00"),
            ),
        )


def downgrade() -> None:
    if _column_exists("transaction_items", "tva_rate"):
        op.drop_column("transaction_items", "tva_rate")
    if _column_exists("products", "tva_rate"):
        op.drop_column("products", "tva_rate")
