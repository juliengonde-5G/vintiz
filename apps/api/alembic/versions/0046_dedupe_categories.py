"""merge duplicate categories and add a unique name index

Revision ID: 0046
Revises: 0045
Create Date: 2026-05-25

D'anciens seeds non idempotents et le formulaire admin (sans garde-fou)
créaient plusieurs lignes pour la même catégorie ("Robes", "robes",
"Robes "), d'où la liste des catégories qui apparaissait en double.

Cette migration fusionne les doublons : pour chaque nom normalisé
(``lower(btrim(name))``) on garde la catégorie la plus ancienne comme
canonique, on réaffecte toutes les références FK (products, price_grids,
trend_analyses, et le parent_id auto-référent), puis on supprime les
copies. Un index unique sur le nom normalisé empêche la réapparition.

Irréversible : le ``downgrade`` ne fait que retirer l'index unique — les
lignes fusionnées ne peuvent pas être recréées.
"""

from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Mapping doublon -> canonique (la plus ancienne par nom normalisé).
    op.execute(
        """
        CREATE TEMP TABLE _cat_merge ON COMMIT DROP AS
        SELECT id AS dupe_id, canonical_id
        FROM (
            SELECT id,
                   first_value(id) OVER (
                       PARTITION BY lower(btrim(name))
                       ORDER BY created_at ASC, id ASC
                   ) AS canonical_id
            FROM categories
        ) ranked
        WHERE id <> canonical_id;
        """
    )

    # Réaffecter toutes les références FK vers la catégorie canonique.
    op.execute(
        "UPDATE products p SET category_id = m.canonical_id "
        "FROM _cat_merge m WHERE p.category_id = m.dupe_id;"
    )
    op.execute(
        "UPDATE price_grids g SET category_id = m.canonical_id "
        "FROM _cat_merge m WHERE g.category_id = m.dupe_id;"
    )
    op.execute(
        "UPDATE trend_analyses t SET category_id = m.canonical_id "
        "FROM _cat_merge m WHERE t.category_id = m.dupe_id;"
    )
    op.execute(
        "UPDATE categories c SET parent_id = m.canonical_id "
        "FROM _cat_merge m WHERE c.parent_id = m.dupe_id;"
    )

    # Supprimer les doublons désormais orphelins.
    op.execute("DELETE FROM categories WHERE id IN (SELECT dupe_id FROM _cat_merge);")

    # Empêcher toute réapparition au niveau base (insensible casse/espaces).
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_name_lower "
        "ON categories (lower(btrim(name)));"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_categories_name_lower;")
