"""add visibility tables: seo_snapshots + social_posts + social_mentions + google_reviews

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-26

P3-003 + P3-004 + P3-005. Idempotent like prior migrations.
"""

from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
    ).fetchone() is not None


def upgrade() -> None:
    # ---- SEO snapshots (P3-005) -------------------------------------------
    if not _table_exists("seo_snapshots"):
        op.create_table(
            "seo_snapshots",
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
            sa.Column("site_url", sa.String(length=255), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("response_ms", sa.Integer(), nullable=True),
            sa.Column(
                "checks", sa.dialects.postgresql.JSONB(), nullable=False
            ),
            sa.Column(
                "fetched_at", sa.DateTime(timezone=True), nullable=False
            ),
        )
        op.create_index(
            "ix_seo_snapshots_fetched_at",
            "seo_snapshots",
            ["fetched_at"],
        )

    # ---- Social posts (P3-004) --------------------------------------------
    if not _table_exists("social_posts"):
        op.execute(
            """
            DO $$ BEGIN
                CREATE TYPE social_post_category AS ENUM (
                    'PRODUIT_STAR', 'VALEURS', 'TEMOIGNAGE', 'ACTU_LOCALE'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
        op.execute(
            """
            DO $$ BEGIN
                CREATE TYPE social_platform AS ENUM (
                    'instagram', 'tiktok', 'both'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
        social_post_category = sa.dialects.postgresql.ENUM(
            "PRODUIT_STAR", "VALEURS", "TEMOIGNAGE", "ACTU_LOCALE",
            name="social_post_category",
            create_type=False,
        )
        social_platform = sa.dialects.postgresql.ENUM(
            "instagram", "tiktok", "both",
            name="social_platform",
            create_type=False,
        )
        op.create_table(
            "social_posts",
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
            sa.Column("iso_week", sa.String(length=8), nullable=False),
            sa.Column("category", social_post_category, nullable=False),
            sa.Column("platform", social_platform, nullable=False),
            sa.Column("caption", sa.Text(), nullable=False),
            sa.Column(
                "hashtags",
                sa.dialects.postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("best_time", sa.String(length=10), nullable=True),
            sa.Column("media_brief", sa.Text(), nullable=True),
            sa.Column(
                "used_llm",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "accepted_by_user_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_social_posts_iso_week",
            "social_posts",
            ["iso_week"],
        )

    # ---- Social mentions (P3-003) -----------------------------------------
    if not _table_exists("social_mentions"):
        op.execute(
            """
            DO $$ BEGIN
                CREATE TYPE social_platform_mention AS ENUM (
                    'instagram', 'tiktok', 'both'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
        social_platform_mention = sa.dialects.postgresql.ENUM(
            "instagram", "tiktok", "both",
            name="social_platform_mention",
            create_type=False,
        )
        op.create_table(
            "social_mentions",
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
            sa.Column("platform", social_platform_mention, nullable=False),
            sa.Column("source_url", sa.String(length=500), nullable=True),
            sa.Column("author", sa.String(length=120), nullable=True),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("sentiment", sa.Float(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "fetched_at", sa.DateTime(timezone=True), nullable=False
            ),
        )

    # ---- Google reviews (P3-003) ------------------------------------------
    if not _table_exists("google_reviews"):
        op.create_table(
            "google_reviews",
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
            sa.Column("author", sa.String(length=120), nullable=True),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "fetched_at", sa.DateTime(timezone=True), nullable=False
            ),
            sa.Column("reply_text", sa.Text(), nullable=True),
            sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    for table in (
        "google_reviews",
        "social_mentions",
        "social_posts",
        "seo_snapshots",
    ):
        if _table_exists(table):
            op.drop_table(table)
