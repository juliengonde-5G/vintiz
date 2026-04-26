"""add product_photos table and backfill from products.photo_url (P1-008)

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-26

Creates the multi-photo table used by carousel UI and downstream Vision /
Personal Shopper enrichments. Existing single photo_url values are
backfilled as the primary photo so no data is lost.

Idempotent: safe to re-run; backfill only inserts rows that don't already
exist for the same product.
"""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
    ).fetchone() is not None


def upgrade() -> None:
    if not _table_exists("product_photos"):
        op.create_table(
            "product_photos",
            sa.Column(
                "id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                primary_key=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "product_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("products.id"),
                nullable=False,
            ),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "is_primary",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "ai_analyzed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column("ai_confidence", sa.Float(), nullable=True),
        )
        op.create_index(
            "ix_product_photos_product",
            "product_photos",
            ["product_id", "order_index"],
        )
        op.create_index(
            "ix_product_photos_primary",
            "product_photos",
            ["product_id", "is_primary"],
        )

    # Backfill: copy each products.photo_url into a primary product_photos row
    # if no row exists yet for that product. uuid_generate_v4() is part of the
    # uuid-ossp extension; fall back to gen_random_uuid() (pgcrypto) if not.
    op.execute(
        """
        INSERT INTO product_photos (id, product_id, url, order_index, is_primary, created_at, updated_at)
        SELECT
            COALESCE(
                (SELECT NULL),
                gen_random_uuid()
            ),
            p.id,
            p.photo_url,
            0,
            true,
            now(),
            now()
        FROM products p
        WHERE p.photo_url IS NOT NULL
          AND p.photo_url <> ''
          AND NOT EXISTS (
            SELECT 1 FROM product_photos pp WHERE pp.product_id = p.id
          )
        """
    )


def downgrade() -> None:
    if _table_exists("product_photos"):
        op.drop_index("ix_product_photos_primary", table_name="product_photos")
        op.drop_index("ix_product_photos_product", table_name="product_photos")
        op.drop_table("product_photos")
