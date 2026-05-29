"""Add declarative qualification columns on clients (PS 360 V1, layer 1)

Revision ID: 0051
Revises: 0050
Create Date: 2026-05-29

Personal Shopper 360 — Vague V1 (Activation & Web). L'onboarding en couches
collecte, à l'étape obligatoire, le genre et la tranche d'âge déclaratifs de
la cliente. On les persiste pour amorcer le taste profile, filtrer les
candidats du cold-start visuel et cibler les communications.

Additif : deux colonnes VARCHAR nullable → les fiches existantes restent à
NULL (repli sur le genre des pièces achetées / aucune nuance d'âge).
Idempotent (IF NOT EXISTS). Les signaux *calculés* (season_bias,
price_ceiling, price_sensitivity, trend_affinity) arrivent en V2.
"""

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE clients "
        "ADD COLUMN IF NOT EXISTS gender_profile VARCHAR(10);"
    ))
    conn.execute(sa.text(
        "ALTER TABLE clients "
        "ADD COLUMN IF NOT EXISTS age_band VARCHAR(10);"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE clients DROP COLUMN IF EXISTS age_band;"))
    conn.execute(sa.text("ALTER TABLE clients DROP COLUMN IF EXISTS gender_profile;"))
