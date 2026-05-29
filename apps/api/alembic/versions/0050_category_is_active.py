"""Add is_active flag on categories

Revision ID: 0050
Revises: 0049
Create Date: 2026-05-29

Permet d'activer / désactiver une catégorie (masquée des sélecteurs sans
toucher aux produits rattachés). Additif : colonne NOT NULL DEFAULT true →
les catégories existantes restent actives. Idempotent (IF NOT EXISTS).
"""

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE categories "
        "ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE categories DROP COLUMN IF EXISTS is_active;"))
