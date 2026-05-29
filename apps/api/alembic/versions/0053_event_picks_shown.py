"""Add customer.picks_shown event type (PS 360 V3)

Revision ID: 0053
Revises: 0052
Create Date: 2026-05-29

Personal Shopper 360 — Vague V3 (Aide à la vente). Le bouton « Pépites du
jour » émet un événement ``customer.picks_shown`` (frequency cap 24 h +
mesure d'adoption). Le type ``event_type`` étant un enum natif PostgreSQL, il
faut ajouter la valeur explicitement.

``ADD VALUE IF NOT EXISTS`` est supporté depuis PG 9.6 et idempotent — même
pattern que 0006/0009/0029/0032. Aucun impact SQLite (enum = VARCHAR+CHECK
recréé par create_all dans les tests).
"""

from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'customer.picks_shown'")


def downgrade() -> None:
    # PostgreSQL ne sait pas retirer une valeur d'enum sans recréer le type —
    # no-op volontaire (additif, non bloquant).
    pass
