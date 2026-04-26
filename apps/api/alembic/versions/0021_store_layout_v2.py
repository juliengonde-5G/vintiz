"""furniture_items + zone_tags + Store.floor_plan_url (L2.2)

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-02

Idempotent.
"""

from alembic import op
import sqlalchemy as sa


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
        ),
        {"t": name},
    ).fetchone() is not None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).fetchone() is not None


def upgrade() -> None:
    # New columns on store_zones for floor plan + layout orientation.
    if not _column_exists("store_zones", "floor_plan_url"):
        op.add_column(
            "store_zones",
            sa.Column("floor_plan_url", sa.Text(), nullable=True),
        )
    if not _column_exists("store_zones", "layout_orientation"):
        op.add_column(
            "store_zones",
            sa.Column("layout_orientation", sa.Integer(), nullable=False, server_default="0"),
        )

    # furniture_items table — drag-droppable items in the iso canvas.
    if not _table_exists("furniture_items"):
        op.create_table(
            "furniture_items",
            sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("zone_id", sa.dialects.postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("store_zones.id", ondelete="SET NULL"), nullable=True),
            sa.Column("type", sa.String(50), nullable=False),  # portant|mannequin|etagere|...
            sa.Column("variant", sa.String(50), nullable=True),
            sa.Column("pos_x", sa.Float(), nullable=False, server_default="0"),
            sa.Column("pos_y", sa.Float(), nullable=False, server_default="0"),
            sa.Column("rotation", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("scale", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("label", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_furniture_items_zone", "furniture_items", ["zone_id"])

    # zone_tags table — multi-tag per zone (homme | femme | derniere_demarque…).
    if not _table_exists("zone_tags"):
        op.create_table(
            "zone_tags",
            sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("zone_id", sa.dialects.postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("store_zones.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tag", sa.String(50), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("zone_id", "tag", name="uq_zone_tag"),
        )
        op.create_index("ix_zone_tags_zone", "zone_tags", ["zone_id"])
        op.create_index("ix_zone_tags_tag", "zone_tags", ["tag"])


def downgrade() -> None:
    if _table_exists("zone_tags"):
        op.drop_index("ix_zone_tags_tag", table_name="zone_tags")
        op.drop_index("ix_zone_tags_zone", table_name="zone_tags")
        op.drop_table("zone_tags")
    if _table_exists("furniture_items"):
        op.drop_index("ix_furniture_items_zone", table_name="furniture_items")
        op.drop_table("furniture_items")
    if _column_exists("store_zones", "layout_orientation"):
        op.drop_column("store_zones", "layout_orientation")
    if _column_exists("store_zones", "floor_plan_url"):
        op.drop_column("store_zones", "floor_plan_url")
