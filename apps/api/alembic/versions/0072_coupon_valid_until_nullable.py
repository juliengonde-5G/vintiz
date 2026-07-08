"""Make coupons.valid_until nullable — NULL = no expiry.

Les chèques cadeau fidélité (source=loyalty_milestone) ne doivent plus avoir de
date de péremption : on autorise ``valid_until IS NULL`` (= sans expiration).
Les autres coupons (anniversaire, winback…) continuent de poser une date. Tous
les lecteurs traitent déjà un ``valid_until`` nul comme « toujours valable ».

Postgres-only (ALTER COLUMN). Sur SQLite le schéma de test est reconstruit
depuis les modèles (colonne déjà nullable), donc no-op défensif ici.
"""

from alembic import op

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE coupons ALTER COLUMN valid_until DROP NOT NULL;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # Re-imposing NOT NULL requires backfilling the no-expiry rows first.
    op.execute(
        "UPDATE coupons SET valid_until = '2999-12-31'::timestamptz "
        "WHERE valid_until IS NULL;"
    )
    op.execute("ALTER TABLE coupons ALTER COLUMN valid_until SET NOT NULL;")
