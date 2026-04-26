"""add consents table and deletion_requested_at on clients (P1-007 RGPD)

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-26

- clients.deletion_requested_at: TIMESTAMP nullable, set by the soft-delete
  request endpoint and consumed by the purge cron after 30 days.
- consents: append-only ledger of consent grants/revokes per client × purpose.

Idempotent like prior migrations.
"""

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
        ),
        {"t": table},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if not _column_exists("clients", "deletion_requested_at"):
        op.add_column(
            "clients",
            sa.Column(
                "deletion_requested_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    if not _table_exists("consents"):
        op.execute(
            """
            DO $$ BEGIN
                CREATE TYPE consent_purpose AS ENUM (
                    'email_marketing', 'sms_marketing',
                    'profiling', 'data_sharing'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
        consent_purpose = sa.dialects.postgresql.ENUM(
            "email_marketing", "sms_marketing", "profiling", "data_sharing",
            name="consent_purpose",
            create_type=False,
        )
        op.create_table(
            "consents",
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
                "client_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("clients.id"),
                nullable=False,
            ),
            sa.Column("purpose", consent_purpose, nullable=False),
            sa.Column("granted", sa.Boolean(), nullable=False),
            sa.Column("policy_version", sa.String(length=20), nullable=False),
            sa.Column("source", sa.String(length=50), nullable=False),
            sa.Column(
                "recorded_by_user_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_consents_client_purpose",
            "consents",
            ["client_id", "purpose", "created_at"],
        )


def downgrade() -> None:
    if _table_exists("consents"):
        op.drop_index("ix_consents_client_purpose", table_name="consents")
        op.drop_table("consents")
        op.execute("DROP TYPE IF EXISTS consent_purpose")
    if _column_exists("clients", "deletion_requested_at"):
        op.drop_column("clients", "deletion_requested_at")
