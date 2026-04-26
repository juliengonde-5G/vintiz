"""add brand_tiers table + seed (P2-012)

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-26

Migrates the hardcoded brand-tier sets from scoring_service.py into a
table Camille can edit from the admin. Initial seed reproduces the
audit V1 §2.1.6 list 1:1 so the scoring output stays identical until
the manager starts curating.

Idempotent like prior migrations.
"""

from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


_SEED = [
    # luxury
    *[("hermes", "luxury"), ("chanel", "luxury"), ("dior", "luxury"),
      ("vuitton", "luxury"), ("gucci", "luxury"), ("prada", "luxury"),
      ("celine", "luxury"), ("saint laurent", "luxury"),
      ("balenciaga", "luxury")],
    # premium
    *[("sandro", "premium"), ("maje", "premium"), ("ba&sh", "premium"),
      ("gerard darel", "premium"), ("the kooples", "premium"),
      ("claudie pierlot", "premium"), ("des petits hauts", "premium")],
    # mid
    *[("zara", "mid"), ("h&m", "mid"), ("mango", "mid"), ("apc", "mid"),
      ("jacquemus", "mid"), ("sessun", "mid")],
]


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
    ).fetchone() is not None


def upgrade() -> None:
    if not _table_exists("brand_tiers"):
        op.execute(
            """
            DO $$ BEGIN
                CREATE TYPE brand_tier_level AS ENUM (
                    'luxury', 'premium', 'mid', 'basic'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
        brand_tier_level = sa.dialects.postgresql.ENUM(
            "luxury", "premium", "mid", "basic",
            name="brand_tier_level",
            create_type=False,
        )
        op.create_table(
            "brand_tiers",
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
            sa.Column("name", sa.String(length=100), nullable=False, unique=True),
            sa.Column("tier", brand_tier_level, nullable=False),
            sa.Column("score_override", sa.Float(), nullable=True),
        )

    # Seed — INSERT ... ON CONFLICT DO NOTHING so re-runs don't barf.
    # Cast :tier to the enum explicitly: asyncpg/PG won't auto-coerce a
    # VARCHAR bind param to a custom ENUM column.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    for name, tier in _SEED:
        op.execute(
            sa.text(
                "INSERT INTO brand_tiers (id, name, tier, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :name, CAST(:tier AS brand_tier_level), now(), now()) "
                "ON CONFLICT (name) DO NOTHING"
            ).bindparams(name=name, tier=tier)
        )


def downgrade() -> None:
    if _table_exists("brand_tiers"):
        op.drop_table("brand_tiers")
