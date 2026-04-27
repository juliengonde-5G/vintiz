"""Create weekly_tasks + window_decors tables.

Revision ID: 0030
Revises: 0029
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    uuid_type = sa.dialects.postgresql.UUID(as_uuid=True) if is_pg else sa.String(36)
    existing_tables = set(sa.inspect(bind).get_table_names())

    # ------------------------------------------------------------------
    # weekly_tasks
    # ------------------------------------------------------------------
    if "weekly_tasks" not in existing_tables:
        if is_pg:
            sa.Enum(
                "monday_scoring_update",
                "morning_restock",
                "tuesday_window_refresh",
                "wednesday_featured_refresh",
                "thursday_six_weeks_exit",
                name="weekly_task_kind",
            ).create(bind, checkfirst=True)
            sa.Enum(
                "pending", "done", "skipped", name="weekly_task_status"
            ).create(bind, checkfirst=True)

        kind_enum = sa.Enum(
            "monday_scoring_update",
            "morning_restock",
            "tuesday_window_refresh",
            "wednesday_featured_refresh",
            "thursday_six_weeks_exit",
            name="weekly_task_kind",
            create_type=False,
        )
        status_enum = sa.Enum(
            "pending", "done", "skipped",
            name="weekly_task_status", create_type=False,
        )

        op.create_table(
            "weekly_tasks",
            sa.Column("id", uuid_type, primary_key=True,
                      server_default=sa.text("gen_random_uuid()") if is_pg else None),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("kind", kind_enum, nullable=False),
            sa.Column("scheduled_for", sa.Date(), nullable=False),
            sa.Column("status", status_enum, nullable=False,
                      server_default=sa.text("'pending'")),
            sa.Column("payload", sa.JSON(), nullable=False,
                      server_default=sa.text("'{}'::json" if is_pg else "'{}'")),
            sa.Column("completed_by_user_id", uuid_type, nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.String(500), nullable=True),
        )
        op.create_index("ix_weekly_tasks_scheduled", "weekly_tasks",
                        ["scheduled_for", "kind"])

    # ------------------------------------------------------------------
    # window_decors
    # ------------------------------------------------------------------
    if "window_decors" in existing_tables:
        return
    op.create_table(
        "window_decors",
        sa.Column("id", uuid_type, primary_key=True,
                  server_default=sa.text("gen_random_uuid()") if is_pg else None),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("ai_analysis", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
    )
    op.create_index("ix_window_decors_period", "window_decors",
                    ["starts_on", "ends_on"])


def downgrade() -> None:
    op.drop_index("ix_window_decors_period", "window_decors")
    op.drop_table("window_decors")
    op.drop_index("ix_weekly_tasks_scheduled", "weekly_tasks")
    op.drop_table("weekly_tasks")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS weekly_task_kind")
        op.execute("DROP TYPE IF EXISTS weekly_task_status")
