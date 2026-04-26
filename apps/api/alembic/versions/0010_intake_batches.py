"""add intake_batches table + products.intake_batch_id (P2-015)

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-26

Idempotent like prior migrations.
"""

from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
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
    if not _table_exists("intake_batches"):
        op.execute(
            """
            DO $$ BEGIN
                CREATE TYPE intake_source AS ENUM (
                    'sorting_center', 'deposit',
                    'direct_donation', 'purchase', 'other'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
        intake_source = sa.dialects.postgresql.ENUM(
            "sorting_center",
            "deposit",
            "direct_donation",
            "purchase",
            "other",
            name="intake_source",
            create_type=False,
        )

        op.create_table(
            "intake_batches",
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
            sa.Column("batch_number", sa.String(length=50), nullable=False, unique=True),
            sa.Column("source", intake_source, nullable=False),
            sa.Column(
                "received_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "recorded_by_user_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
            sa.Column(
                "n_items_received",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    if not _column_exists("products", "intake_batch_id"):
        op.add_column(
            "products",
            sa.Column(
                "intake_batch_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_foreign_key(
            "fk_products_intake_batch",
            "products",
            "intake_batches",
            ["intake_batch_id"],
            ["id"],
        )
        op.create_index(
            "ix_products_intake_batch_id", "products", ["intake_batch_id"]
        )


def downgrade() -> None:
    if _column_exists("products", "intake_batch_id"):
        op.drop_index("ix_products_intake_batch_id", table_name="products")
        op.drop_constraint(
            "fk_products_intake_batch", "products", type_="foreignkey"
        )
        op.drop_column("products", "intake_batch_id")
    if _table_exists("intake_batches"):
        op.drop_table("intake_batches")
        op.execute("DROP TYPE IF EXISTS intake_source")
