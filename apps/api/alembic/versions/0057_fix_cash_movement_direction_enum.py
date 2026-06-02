"""Fix cash_movement_direction enum labels (inflow/outflow → in/out)

Revision ID: 0057
Revises: 0056
Create Date: 2026-06-02

Bug en prod : la clôture de caisse (``POST /api/pos/drawer/close``) tombait
en 500 ``invalid input value for enum cash_movement_direction: "in"`` qui
cassait la connexion → côté navigateur « failed to fetch ».

Cause racine : le type enum PostgreSQL ``cash_movement_direction`` a été créé
par ``Base.metadata.create_all`` (lifespan au boot) AVANT que le modèle
``CashMovement`` ne gagne son ``values_callable``. À ce moment-là, SQLAlchemy a
créé le type avec les **noms** des membres Python (``inflow`` / ``outflow``)
au lieu de leurs **valeurs** (``in`` / ``out``). Depuis, le modèle persiste
``in`` / ``out`` (valeurs), que le type enum stale rejette.

Cette migration aligne les labels existants sur les valeurs attendues, de
manière idempotente : on ne renomme que si le label legacy est présent. Si la
base a déjà les bons labels (déploiement récent post-fix du modèle), c'est un
no-op complet. Aucune donnée touchée — ``ALTER TYPE ... RENAME VALUE`` ne
réécrit pas les lignes, juste l'étiquette du type.

PostgreSQL ≥ 10 requis pour ``RENAME VALUE`` (la stack tourne sur PG 16).
"""

import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # SQLite (tests) : le type enum portable n'existe pas, rien à faire.
    if not _is_postgres():
        return

    # Renommage conditionnel des labels legacy. Le DO-block PL/pgSQL nous
    # permet de tester l'existence du label avant de renommer (idempotent,
    # ne plante pas si le label cible existe déjà).
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'cash_movement_direction'
                      AND e.enumlabel = 'inflow'
                ) THEN
                    ALTER TYPE cash_movement_direction RENAME VALUE 'inflow' TO 'in';
                END IF;

                IF EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'cash_movement_direction'
                      AND e.enumlabel = 'outflow'
                ) THEN
                    ALTER TYPE cash_movement_direction RENAME VALUE 'outflow' TO 'out';
                END IF;
            END$$;
            """
        )
    )


def downgrade() -> None:
    # Retour aux labels legacy (symétrique), idempotent lui aussi.
    if not _is_postgres():
        return
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'cash_movement_direction'
                      AND e.enumlabel = 'in'
                ) THEN
                    ALTER TYPE cash_movement_direction RENAME VALUE 'in' TO 'inflow';
                END IF;

                IF EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'cash_movement_direction'
                      AND e.enumlabel = 'out'
                ) THEN
                    ALTER TYPE cash_movement_direction RENAME VALUE 'out' TO 'outflow';
                END IF;
            END$$;
            """
        )
    )
