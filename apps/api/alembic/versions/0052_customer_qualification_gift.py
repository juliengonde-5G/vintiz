"""Customer qualification signals + gift flags (PS 360 V2)

Revision ID: 0052
Revises: 0051
Create Date: 2026-05-29

Personal Shopper 360 — Vague V2 (Profilage métier).

- ``clients`` gagne les signaux *calculés* par le service customer_qualification
  (à chaque transaction + batch nightly) : season_bias, price_ceiling_cents,
  price_sensitivity, trend_affinity. (gender_profile / age_band déclaratifs
  sont arrivés en V1, migration 0051.)
- ``transactions`` gagne la détection cadeau : is_gift (réponse caisse / client)
  et exclude_from_taste (exclut l'achat du profil de goûts). Un cadeau pollue
  le centroïde (demi-vie 180 j) — on l'exclut du calcul.

Additif : colonnes nullable (signaux) ou NOT NULL DEFAULT false (flags) →
les lignes existantes restent neutres. Idempotent (IF NOT EXISTS).
"""

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for col, ddl in (
        ("season_bias", "VARCHAR(10)"),
        ("price_ceiling_cents", "INTEGER"),
        ("price_sensitivity", "DOUBLE PRECISION"),
        ("trend_affinity", "DOUBLE PRECISION"),
    ):
        conn.execute(sa.text(
            f"ALTER TABLE clients ADD COLUMN IF NOT EXISTS {col} {ddl};"
        ))
    for col in ("is_gift", "exclude_from_taste"):
        conn.execute(sa.text(
            f"ALTER TABLE transactions "
            f"ADD COLUMN IF NOT EXISTS {col} BOOLEAN NOT NULL DEFAULT false;"
        ))


def downgrade() -> None:
    conn = op.get_bind()
    for col in ("exclude_from_taste", "is_gift"):
        conn.execute(sa.text(f"ALTER TABLE transactions DROP COLUMN IF EXISTS {col};"))
    for col in ("trend_affinity", "price_sensitivity", "price_ceiling_cents", "season_bias"):
        conn.execute(sa.text(f"ALTER TABLE clients DROP COLUMN IF EXISTS {col};"))
