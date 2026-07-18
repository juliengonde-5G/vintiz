"""Ajoute product_scan_logs.product_status (statut au moment du scan).

Audit du 18/07 : une pièce au statut « returned » scannée en caisse a bloqué
la validation APRÈS l'encaissement CB. L'historique douchette n'enregistrait
pas le statut → il a fallu croiser products / audit_logs /
product_location_events pour l'établir. Cette colonne rend le diagnostic
immédiat.

Revision ID: 0074
Revises: 0073
Create Date: 2026-07-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_scan_logs",
        sa.Column("product_status", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product_scan_logs", "product_status")
