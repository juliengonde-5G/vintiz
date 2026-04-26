"""enable pgvector + add product_embeddings and customer_taste_profiles (P1-004)

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-26

The recommender (Personal Shopper v2, P2-001 → P2-004) reads from these
tables. We use pgvector's native ``vector`` type so HNSW indexes and the
``<->``/``<=>`` cosine operator are available; on SQLite (tests) the
SQLAlchemy model falls back to JSON.

The HNSW index is created with vector_cosine_ops because we compute
cosine similarity between centroids and product vectors. m=16 / ef_construction=64
are pgvector defaults — fine until the catalogue exceeds ~100 k rows.

Idempotent like prior migrations.
"""

from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 256


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
    ).fetchone() is not None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    if not _table_exists("product_embeddings"):
        op.create_table(
            "product_embeddings",
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
                unique=True,
                nullable=False,
            ),
            # raw SQL because pgvector type isn't a stock alembic type
            sa.Column(
                "visual_embedding",
                sa.dialects.postgresql.ARRAY(sa.Float),
                nullable=True,
            ),
            sa.Column(
                "text_embedding",
                sa.dialects.postgresql.ARRAY(sa.Float),
                nullable=True,
            ),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("algo_version", sa.String(length=50), nullable=True),
        )
        # Switch the placeholder ARRAY columns to pgvector's native vector(N)
        # so HNSW indexes and the cosine operator are usable.
        op.execute(
            f"ALTER TABLE product_embeddings "
            f"ALTER COLUMN visual_embedding TYPE vector({EMBEDDING_DIM}) "
            f"USING visual_embedding::vector({EMBEDDING_DIM})"
        )
        op.execute(
            f"ALTER TABLE product_embeddings "
            f"ALTER COLUMN text_embedding TYPE vector({EMBEDDING_DIM}) "
            f"USING text_embedding::vector({EMBEDDING_DIM})"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_product_visual_hnsw "
            "ON product_embeddings USING hnsw (visual_embedding vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_product_text_hnsw "
            "ON product_embeddings USING hnsw (text_embedding vector_cosine_ops)"
        )

    if not _table_exists("customer_taste_profiles"):
        op.create_table(
            "customer_taste_profiles",
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
                "customer_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("clients.id"),
                unique=True,
                nullable=False,
            ),
            sa.Column(
                "visual_centroid",
                sa.dialects.postgresql.ARRAY(sa.Float),
                nullable=True,
            ),
            sa.Column(
                "text_centroid",
                sa.dialects.postgresql.ARRAY(sa.Float),
                nullable=True,
            ),
            sa.Column(
                "n_purchases_analyzed",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("algo_version", sa.String(length=50), nullable=True),
        )
        op.execute(
            f"ALTER TABLE customer_taste_profiles "
            f"ALTER COLUMN visual_centroid TYPE vector({EMBEDDING_DIM}) "
            f"USING visual_centroid::vector({EMBEDDING_DIM})"
        )
        op.execute(
            f"ALTER TABLE customer_taste_profiles "
            f"ALTER COLUMN text_centroid TYPE vector({EMBEDDING_DIM}) "
            f"USING text_centroid::vector({EMBEDDING_DIM})"
        )
        # Centroids are queried by id (FK lookup) rather than nearest-
        # neighbour search, so no HNSW index here.


def downgrade() -> None:
    if _table_exists("customer_taste_profiles"):
        op.drop_table("customer_taste_profiles")
    if _table_exists("product_embeddings"):
        op.execute("DROP INDEX IF EXISTS ix_product_text_hnsw")
        op.execute("DROP INDEX IF EXISTS ix_product_visual_hnsw")
        op.drop_table("product_embeddings")
    # Don't drop the extension — other tables may depend on it.
