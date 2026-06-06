"""Z report — clôture de régularisation a posteriori

Revision ID: 0060
Revises: 0059
Create Date: 2026-06-06

Ajoute deux colonnes additives sur ``z_reports`` pour tracer un Z établi en
régularisation (jour d'ouverture de caisse oublié) :
  - ``is_regularization``  BOOLEAN NOT NULL DEFAULT FALSE
  - ``regularization_reason`` TEXT NULL (motif obligatoire côté service)

Aucune antidatation : le Z de régularisation est créé à sa date réelle,
numéroté à la suite et chaîné sur le dernier Z. Ces colonnes ne servent qu'à
l'affichage / l'audit ; la période couverte est portée par le tiroir technique
lié. Idempotent (IF NOT EXISTS) pour survivre à un create_all déjà passé.
"""
import sqlalchemy as sa
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"
    if is_pg:
        conn.execute(sa.text(
            "ALTER TABLE z_reports ADD COLUMN IF NOT EXISTS "
            "is_regularization BOOLEAN NOT NULL DEFAULT FALSE;"
        ))
        conn.execute(sa.text(
            "ALTER TABLE z_reports ADD COLUMN IF NOT EXISTS "
            "regularization_reason TEXT;"
        ))
    else:
        # SQLite (tests) — pas de IF NOT EXISTS sur ADD COLUMN ; on inspecte.
        cols = {c["name"] for c in sa.inspect(conn).get_columns("z_reports")}
        if "is_regularization" not in cols:
            op.add_column(
                "z_reports",
                sa.Column(
                    "is_regularization",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )
        if "regularization_reason" not in cols:
            op.add_column(
                "z_reports",
                sa.Column("regularization_reason", sa.Text(), nullable=True),
            )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE z_reports DROP COLUMN IF EXISTS regularization_reason;"))
    conn.execute(sa.text("ALTER TABLE z_reports DROP COLUMN IF EXISTS is_regularization;"))
