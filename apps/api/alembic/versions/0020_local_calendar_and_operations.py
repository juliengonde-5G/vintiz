"""local_events + commercial_operations + cahier_archive (L2.4)

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-02

Tables :
- ``local_events`` : événements Vernon / Giverny / vacances scolaires zone B,
   pour le moteur prédictif du cahier du jour
- ``commercial_operations`` : soldes, ventes privées, opérations adhérent…
   visibles dans le cahier + auto-application au POS
- ``cahier_day_archive`` : archive jour J-1 avec commentaires manager
   (modifiable jusqu'à J+7, verrouillé après)

Idempotente.
"""

from alembic import op
import sqlalchemy as sa


revision = "0020"
down_revision = "0019"
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
    if not _table_exists("local_events"):
        op.create_table(
            "local_events",
            sa.Column("id", sa.UUID(as_uuid=True) if hasattr(sa, "UUID") else sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("date_start", sa.Date(), nullable=False),
            sa.Column("date_end", sa.Date(), nullable=False),
            sa.Column("location", sa.String(50), nullable=False, server_default="Vernon"),
            sa.Column("expected_traffic_boost_pct", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("source_url", sa.Text(), nullable=True),
            sa.Column("is_school_holiday", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_local_events_date_start", "local_events", ["date_start"])

    if not _table_exists("commercial_operations"):
        op.create_table(
            "commercial_operations",
            sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("date_start", sa.Date(), nullable=False),
            sa.Column("date_end", sa.Date(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("op_type", sa.String(50), nullable=False),
            sa.Column("discount_pct", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("applicable_categories", sa.JSON(), nullable=True),
            sa.Column("applicable_zones", sa.JSON(), nullable=True),
            sa.Column("visible_pos", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("visible_site", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_commercial_operations_status", "commercial_operations", ["status"])
        op.create_index("ix_commercial_operations_date_start", "commercial_operations", ["date_start"])

    if not _table_exists("cahier_day_archive"):
        op.create_table(
            "cahier_day_archive",
            sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("report_date", sa.Date(), nullable=False, unique=True),
            sa.Column("forecast_revenue", sa.Numeric(10, 2), nullable=True),
            sa.Column("actual_revenue", sa.Numeric(10, 2), nullable=True),
            sa.Column("forecast_tickets", sa.Integer(), nullable=True),
            sa.Column("actual_tickets", sa.Integer(), nullable=True),
            sa.Column("manager_morning_note", sa.Text(), nullable=True),
            sa.Column("manager_evening_comment", sa.Text(), nullable=True),
            sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )


def downgrade() -> None:
    if _table_exists("cahier_day_archive"):
        op.drop_table("cahier_day_archive")
    if _table_exists("commercial_operations"):
        op.drop_index("ix_commercial_operations_date_start", table_name="commercial_operations")
        op.drop_index("ix_commercial_operations_status", table_name="commercial_operations")
        op.drop_table("commercial_operations")
    if _table_exists("local_events"):
        op.drop_index("ix_local_events_date_start", table_name="local_events")
        op.drop_table("local_events")
