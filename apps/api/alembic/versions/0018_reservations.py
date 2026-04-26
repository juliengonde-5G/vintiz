"""add reservations table (P4-005)

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-26

Idempotent like prior migrations. Wraps enum creation in DO/EXCEPTION
to stay safe when ``Base.metadata.create_all`` (lifespan) raced ahead.
"""

from alembic import op
import sqlalchemy as sa


revision = "0018"
down_revision = "0017"
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


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE reservation_status AS ENUM (
                'active', 'redeemed', 'cancelled', 'expired'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    if not _table_exists("reservations"):
        op.create_table(
            "reservations",
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
            sa.Column(
                "client_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("clients.id"),
                nullable=False,
            ),
            sa.Column(
                "product_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("products.id"),
                nullable=False,
            ),
            sa.Column(
                "status",
                sa.dialects.postgresql.ENUM(
                    "active", "redeemed", "cancelled", "expired",
                    name="reservation_status",
                    create_type=False,
                ),
                nullable=False,
                server_default=sa.text("'active'::reservation_status"),
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "redeemed_transaction_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("transactions.id"),
                nullable=True,
            ),
            sa.Column(
                "manager_user_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
            sa.Column("notes", sa.Text(), nullable=True),
        )
        op.create_index("ix_reservations_client_id", "reservations", ["client_id"])
        op.create_index("ix_reservations_product_id", "reservations", ["product_id"])
        op.create_index("ix_reservations_status", "reservations", ["status"])
        op.create_index("ix_reservations_expires_at", "reservations", ["expires_at"])

        # Partial unique index — only one ACTIVE reservation per product at a time.
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_reservations_active_product "
            "ON reservations (product_id) WHERE status = 'active'"
        )


def downgrade() -> None:
    if _table_exists("reservations"):
        op.execute("DROP INDEX IF EXISTS uq_reservations_active_product")
        op.drop_index("ix_reservations_expires_at", table_name="reservations")
        op.drop_index("ix_reservations_status", table_name="reservations")
        op.drop_index("ix_reservations_product_id", table_name="reservations")
        op.drop_index("ix_reservations_client_id", table_name="reservations")
        op.drop_table("reservations")
    op.execute("DROP TYPE IF EXISTS reservation_status")
