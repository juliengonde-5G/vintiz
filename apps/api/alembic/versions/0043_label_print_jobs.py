"""label print queue drained by the in-store Raspberry Pi agent

Replaces direct Zebra printing (network/cloud/Bluetooth transports, all
removed) with a queue: the manager's "print label" action enqueues a row, and
the in-store Raspberry Pi polls /api/labels/agent/* (outbound only) to print
the server-rendered PDF via CUPS.

The printable content is snapshotted into ``payload`` at enqueue time so the
label reflects what the manager saw even if the product changes later.

Idempotent: skips the CREATE when the table is already present.

Revision ID: 0043
Revises: 0042
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in set(inspector.get_table_names())


def upgrade() -> None:
    if _table_exists("label_print_jobs"):
        return

    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    uuid_type = postgresql.UUID(as_uuid=True) if is_pg else sa.String(length=36)
    json_type = postgresql.JSONB if is_pg else sa.JSON
    now_default = sa.text("now()" if is_pg else "CURRENT_TIMESTAMP")
    empty_json = sa.text("'{}'::jsonb" if is_pg else "'{}'")

    op.create_table(
        "label_print_jobs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=now_default, nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=now_default, nullable=False
        ),
        sa.Column("job_type", sa.String(length=16), nullable=False, server_default="product"),
        sa.Column("product_id", uuid_type, nullable=True),
        sa.Column("copies", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("payload", json_type, nullable=False, server_default=empty_json),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", uuid_type, nullable=True),
    )
    op.create_index("ix_label_print_jobs_status", "label_print_jobs", ["status"])
    # The agent claims the oldest pending job first.
    op.create_index(
        "ix_label_print_jobs_status_created",
        "label_print_jobs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    if not _table_exists("label_print_jobs"):
        return
    op.drop_index("ix_label_print_jobs_status_created", table_name="label_print_jobs")
    op.drop_index("ix_label_print_jobs_status", table_name="label_print_jobs")
    op.drop_table("label_print_jobs")
