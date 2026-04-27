"""Create offers table + extend coupon_source enum.

Revision ID: 0029
Revises: 0028
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # Extend coupon_source enum (Postgres only — SQLite stores text)
    # ------------------------------------------------------------------
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE coupon_source ADD VALUE IF NOT EXISTS 'progressive'")
        op.execute("ALTER TYPE coupon_source ADD VALUE IF NOT EXISTS 'loyalty_milestone'")

    # ------------------------------------------------------------------
    # Create offers table
    # ------------------------------------------------------------------
    offer_type = sa.Enum(
        "end_of_series",
        "birthday",
        "shoes_third_free",
        "progressive_voucher",
        "bundle_3_for_2",
        "seasonal_gift",
        name="offer_type",
    )
    if bind.dialect.name == "postgresql":
        offer_type.create(bind, checkfirst=True)

    op.create_table(
        "offers",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql"
            else sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if bind.dialect.name == "postgresql"
            else None,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("type", offer_type, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requires_loyalty", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json"
            if bind.dialect.name == "postgresql" else "'{}'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "updated_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql"
            else sa.String(36),
            nullable=True,
        ),
    )
    op.create_index("ix_offers_active_type", "offers", ["active", "type"])


def downgrade() -> None:
    op.drop_index("ix_offers_active_type", "offers")
    op.drop_table("offers")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS offer_type")
