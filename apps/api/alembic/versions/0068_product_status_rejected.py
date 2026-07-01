"""Add 'rejected' to the product_status enum.

Statut terminal « Rejeté » : pièce refusée à la mise en vente (bouton
« Refuser » des mouvements de stock). Non vendable, retirée du magasin.

Revision ID: 0068
Revises: 0067
Create Date: 2026-07-01
"""

from alembic import op


revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Postgres only — SQLite stores enums as text (CHECK rebuilt from model).
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE product_status ADD VALUE IF NOT EXISTS 'rejected'")


def downgrade() -> None:
    # Postgres ne sait pas retirer proprement une valeur d'enum ; on la laisse.
    pass
