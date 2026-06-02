"""Event-opening gift vouchers — bons cadeau distribués à l'ouverture

Revision ID: 0056
Revises: 0055
Create Date: 2026-06-02

Bons cadeau crédités sur la fiche client (zone Événementiel du POS) puis
débités au prochain passage en caisse comme moyen de paiement. On réutilise la
table ``coupons`` (nominative, validité, usage unique) en l'étendant :

- ``coupon_source`` += ``event_opening``
- ``coupon_discount_type`` += ``free_item`` (ex. « 1 foulard offert »)
- ``coupons.free_item_label`` (libellé + matching de l'article offert)
- ``payment_method`` += ``voucher`` (ligne de règlement « bon cadeau »)

Idempotent (IF NOT EXISTS). Aucune donnée existante touchée. Les ajouts de
valeur d'enum requièrent PostgreSQL ≥ 12 (le schéma utilise déjà
``gen_random_uuid()`` → PG ≥ 13).
"""

import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Colonne additive (nullable) sur coupons.
    conn.execute(sa.text(
        "ALTER TABLE coupons ADD COLUMN IF NOT EXISTS free_item_label VARCHAR(80);"
    ))
    # Nouvelles valeurs d'enum (no-op si déjà présentes, ex. create_all au boot).
    for stmt in (
        "ALTER TYPE coupon_source ADD VALUE IF NOT EXISTS 'event_opening';",
        "ALTER TYPE coupon_discount_type ADD VALUE IF NOT EXISTS 'free_item';",
        "ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'voucher';",
    ):
        conn.execute(sa.text(stmt))


def downgrade() -> None:
    # PostgreSQL ne sait pas retirer une valeur d'enum ; on ne retire que la
    # colonne additive. Les valeurs d'enum ajoutées restent (sans effet).
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE coupons DROP COLUMN IF EXISTS free_item_label;"))
