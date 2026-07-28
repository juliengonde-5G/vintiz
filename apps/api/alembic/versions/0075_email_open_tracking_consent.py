"""Ajoute le purpose de consentement ``email_open_tracking``.

Recommandation CNIL 2026 : le pixel d'ouverture des e-mails marketing est un
traceur soumis à consentement spécifique (distinct de l'opt-in newsletter).
On ajoute la valeur à l'enum ``consent_purpose`` (PostgreSQL). No-op sur
SQLite (colonne texte). Voir docs/COMPLIANCE_TRACKING_PIXELS_2026.md.

Revision ID: 0075
Revises: 0074
Create Date: 2026-07-28
"""

from __future__ import annotations

from alembic import op


revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # ADD VALUE ... IF NOT EXISTS est idempotent ; sur SQLite l'enum est
        # stocké en texte donc rien à faire.
        op.execute(
            "ALTER TYPE consent_purpose ADD VALUE IF NOT EXISTS 'email_open_tracking'"
        )


def downgrade() -> None:
    # Postgres ne sait pas retirer proprement une valeur d'enum sans réécrire
    # le type ; on la laisse en place (les nouvelles lignes ne la référencent
    # simplement plus). Cohérent avec la migration 0032.
    pass
