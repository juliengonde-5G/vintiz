"""add pin_hash on users and cashier_id on transactions/cash_drawers/z_reports

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-26

Tickets P1-002 (PIN cashier) + P1-014 (cashier_id on transactions).

The migration is idempotent: it skips columns that already exist so it can be
safely re-run on environments at varying states.
"""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
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


def upgrade() -> None:
    if not _column_exists("users", "pin_hash"):
        op.add_column(
            "users",
            sa.Column("pin_hash", sa.String(length=255), nullable=True),
        )

    for table in ("transactions", "cash_drawers", "z_reports"):
        if not _column_exists(table, "cashier_id"):
            op.add_column(
                table,
                sa.Column(
                    "cashier_id",
                    sa.dialects.postgresql.UUID(as_uuid=True),
                    nullable=True,
                ),
            )
            op.create_foreign_key(
                f"fk_{table}_cashier_id_users",
                table,
                "users",
                ["cashier_id"],
                ["id"],
            )


def downgrade() -> None:
    for table in ("z_reports", "cash_drawers", "transactions"):
        op.drop_constraint(
            f"fk_{table}_cashier_id_users", table, type_="foreignkey"
        )
        op.drop_column(table, "cashier_id")
    op.drop_column("users", "pin_hash")
