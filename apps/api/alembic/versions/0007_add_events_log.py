"""add events_log table for analytics + recommender training (P1-003)

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-26

Single-table event store for Vernon. Volume estimate is ~500 k events/year,
so partitioning is deferred until usage justifies it — adding RANGE
partitioning later only requires a follow-up migration that swaps the
underlying physical table; the SQLAlchemy model stays unchanged.

Idempotent like prior migrations.
"""

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
    ).fetchone() is not None


def upgrade() -> None:
    if _table_exists("events_log"):
        return

    # Idempotent enum creation: PG has no CREATE TYPE IF NOT EXISTS so we
    # wrap each one in a DO/EXCEPTION block.
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE event_type AS ENUM (
                'product.created', 'product.viewed',
                'product.try_requested', 'product.try_in_store',
                'product.sold', 'product.refunded',
                'product.donated', 'product.returned_to_sorting',
                'product.markdown_applied', 'product.zone_changed',
                'customer.signed_up', 'customer.visited',
                'customer.recommendation_shown', 'customer.recommendation_clicked',
                'cashier.session_opened', 'cashier.session_closed'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE event_source AS ENUM (
                'pos', 'site', 'admin', 'api', 'system'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    event_type = sa.dialects.postgresql.ENUM(
        name="event_type", create_type=False,
    )
    event_source = sa.dialects.postgresql.ENUM(
        name="event_source", create_type=False,
    )

    op.create_table(
        "events_log",
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
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("event_type", event_type, nullable=False),
        sa.Column("source", event_source, nullable=False),
        sa.Column(
            "customer_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id"),
            nullable=True,
        ),
        sa.Column(
            "product_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=True,
        ),
        sa.Column(
            "transaction_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "session_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("algo_version", sa.String(length=50), nullable=True),
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_events_log_occurred_at", "events_log", ["occurred_at"]
    )
    op.create_index(
        "ix_events_log_event_type", "events_log", ["event_type"]
    )
    op.create_index(
        "ix_events_log_customer_id", "events_log", ["customer_id"]
    )
    op.create_index(
        "ix_events_log_product_id", "events_log", ["product_id"]
    )
    op.create_index(
        "ix_events_customer_time", "events_log", ["customer_id", "occurred_at"]
    )
    op.create_index(
        "ix_events_product_time", "events_log", ["product_id", "occurred_at"]
    )
    op.create_index(
        "ix_events_type_time", "events_log", ["event_type", "occurred_at"]
    )


def downgrade() -> None:
    if not _table_exists("events_log"):
        return
    for idx in (
        "ix_events_type_time",
        "ix_events_product_time",
        "ix_events_customer_time",
        "ix_events_log_product_id",
        "ix_events_log_customer_id",
        "ix_events_log_event_type",
        "ix_events_log_occurred_at",
    ):
        op.drop_index(idx, table_name="events_log")
    op.drop_table("events_log")
    op.execute("DROP TYPE IF EXISTS event_source")
    op.execute("DROP TYPE IF EXISTS event_type")
