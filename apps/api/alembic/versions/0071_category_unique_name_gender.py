"""Categories unique by (name, gender) instead of name alone.

Migration 0046 deduped categories and enforced a UNIQUE index on
``lower(btrim(name))`` — a single row per name. But categories carry a
``gender`` (the add form has a genre selector, and ``suggest_zone`` uses the
category gender for placement), so the shop legitimately needs « Gilet » homme
AND « Gilet » femme as two distinct categories. The name-only index silently
blocked the second one (``create_category`` returned the existing row instead
of inserting), which read as « la catégorie ne se crée pas ».

We drop the name-only index and replace it with a composite unique index on
``(lower(btrim(name)), gender)``. Existing rows are already name-unique, hence
trivially (name, gender)-unique — no data conflict.

Postgres-only (functional index on btrim). On SQLite the test suite builds the
schema from the models, so this migration is a defensive no-op there.
"""

from alembic import op

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS uq_categories_name_lower;")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_name_gender_lower "
        "ON categories (lower(btrim(name)), gender);"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS uq_categories_name_gender_lower;")
    # Best-effort restore of the name-only index. This can fail if per-gender
    # duplicates now exist (« Gilet » homme + femme) — expected: you can't go
    # back to name-only uniqueness while such rows are present.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_name_lower "
        "ON categories (lower(btrim(name)));"
    )
