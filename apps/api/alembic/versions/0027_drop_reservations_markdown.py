"""Drop reservations and markdown_rules tables.

Reservations: feature removed (no 48h hold).
Markdown rules: feature removed (no automated discount policy in shop).

Revision ID: 0027
Revises: 0026
Create Date: 2026-04-28

Note: this migration is intentionally one-way (no useful downgrade). Both
features are gone from the application code.
"""

from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # markdown_rules
    # ------------------------------------------------------------------
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "markdown_rules" in existing_tables:
        op.drop_table("markdown_rules")

    # ------------------------------------------------------------------
    # reservations
    # ------------------------------------------------------------------
    if "reservations" in existing_tables:
        op.drop_table("reservations")

    # Drop the enum type explicitly on PostgreSQL — SQLite has no enum types
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS reservation_status")


def downgrade() -> None:
    # No-op : these features have been removed from the codebase. Recreating
    # the tables here would require re-importing the deleted models, which
    # we don't want.
    pass
