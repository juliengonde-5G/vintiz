"""personal_shopper_messages — persisted PS selections sent to a client

Revision ID: 0064
Revises: 0063
Create Date: 2026-06-21

Records each time a manager sends a Personal Shopper selection to a client
(narrative + products, with a snapshot so the history renders after items sell).
Surfaced in the client fiche ("le personal shopper a envoyé un message").

Idempotent: skips creation when the table already exists.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return sa.inspect(conn).has_table(table)


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    if _table_exists("personal_shopper_messages"):
        return
    op.create_table(
        "personal_shopper_messages",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "client_id", sa.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("product_ids", _json_type(), nullable=False),
        sa.Column("products_snapshot", _json_type(), nullable=True),
        sa.Column("channel", sa.String(10), nullable=False, server_default="email"),
        sa.Column("status", sa.String(16), nullable=False, server_default="sent"),
        sa.Column("backend", sa.String(20), nullable=True),
        sa.Column("algo_version", sa.String(60), nullable=True),
        sa.Column("sent_by_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index(
        "ix_personal_shopper_messages_client_id",
        "personal_shopper_messages", ["client_id"],
    )


def downgrade() -> None:
    if not _table_exists("personal_shopper_messages"):
        return
    op.drop_index(
        "ix_personal_shopper_messages_client_id",
        table_name="personal_shopper_messages",
    )
    op.drop_table("personal_shopper_messages")
