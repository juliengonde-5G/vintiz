"""add clients.birth_date + coupons table (P4-008 + P4-004 foundations)

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-26

Idempotent like prior migrations. Wraps enum creation in DO/EXCEPTION to
stay safe when ``Base.metadata.create_all`` (lifespan) raced ahead.
"""

from alembic import op
import sqlalchemy as sa


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).fetchone() is not None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
        ),
        {"t": name},
    ).fetchone() is not None


def upgrade() -> None:
    # 1. clients.birth_date — nullable, drives the anniversary cron.
    if not _column_exists("clients", "birth_date"):
        op.add_column(
            "clients",
            sa.Column("birth_date", sa.Date(), nullable=True),
        )

    # 2. coupons table + enums (idempotent).
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE coupon_discount_type AS ENUM ('percent', 'amount');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE coupon_source AS ENUM ('anniversary', 'winback', 'welcome', 'manual');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    if not _table_exists("coupons"):
        op.create_table(
            "coupons",
            sa.Column(
                "id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.text("now()"), nullable=False),
            sa.Column("code", sa.String(length=40), nullable=False),
            sa.Column(
                "client_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("clients.id"),
                nullable=True,
            ),
            sa.Column(
                "discount_type",
                sa.dialects.postgresql.ENUM(
                    "percent",
                    "amount",
                    name="coupon_discount_type",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("discount_value", sa.Numeric(10, 2), nullable=False),
            sa.Column(
                "source",
                sa.dialects.postgresql.ENUM(
                    "anniversary",
                    "winback",
                    "welcome",
                    "manual",
                    name="coupon_source",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
            sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "redeemed_transaction_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("transactions.id"),
                nullable=True,
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("code", name="uq_coupons_code"),
        )
        op.create_index("ix_coupons_client_id", "coupons", ["client_id"])
        op.create_index("ix_coupons_valid_until", "coupons", ["valid_until"])


def downgrade() -> None:
    if _table_exists("coupons"):
        op.drop_index("ix_coupons_valid_until", table_name="coupons")
        op.drop_index("ix_coupons_client_id", table_name="coupons")
        op.drop_table("coupons")
    op.execute("DROP TYPE IF EXISTS coupon_source")
    op.execute("DROP TYPE IF EXISTS coupon_discount_type")
    if _column_exists("clients", "birth_date"):
        op.drop_column("clients", "birth_date")
