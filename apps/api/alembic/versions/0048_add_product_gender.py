"""Add a nullable gender column on products

Revision ID: 0048
Revises: 0047
Create Date: 2026-05-28

Le genre devient un attribut produit (proposé par la détection image à
l'étape 2 de l'assistant), base de l'affectation automatique des zones et
3e variable de la 1re ligne de l'étiquette.

Additif : colonne NULLABLE, sans valeur par défaut → les fiches existantes
restent à NULL (elles retombent sur le genre de leur catégorie). Idempotent
(IF NOT EXISTS) pour survivre à un create_all déjà passé au premier boot.
Réutilise le type enum ``gender`` déjà présent (catégories) ; le bloc DO le
crée seulement s'il manque.
"""

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Le type ``gender`` existe déjà (categories.gender) ; on le (re)crée
    # seulement s'il manque, pour rester robuste sur une base neuve.
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE gender AS ENUM ('femme','homme','enfant','mixte');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))
    conn.execute(sa.text(
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS gender gender;"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE products DROP COLUMN IF EXISTS gender;"))
