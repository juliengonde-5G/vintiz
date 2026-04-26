"""add is_test flag on Product and Client (L3.1)

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-01

Allows seed/demo data to be marked and selectively purged without touching
the pre-opening base. Idempotent : guards against repeat runs and against
``Base.metadata.create_all`` having already added the column.
"""

from alembic import op
import sqlalchemy as sa


revision = "0019"
down_revision = "0018"
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


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :n"
        ),
        {"n": name},
    ).fetchone() is not None


def upgrade() -> None:
    if not _column_exists("products", "is_test"):
        op.add_column(
            "products",
            sa.Column(
                "is_test",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not _column_exists("clients", "is_test"):
        op.add_column(
            "clients",
            sa.Column(
                "is_test",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not _index_exists("ix_products_is_test"):
        op.create_index("ix_products_is_test", "products", ["is_test"])
    if not _index_exists("ix_clients_is_test"):
        op.create_index("ix_clients_is_test", "clients", ["is_test"])


def downgrade() -> None:
    if _index_exists("ix_clients_is_test"):
        op.drop_index("ix_clients_is_test", table_name="clients")
    if _index_exists("ix_products_is_test"):
        op.drop_index("ix_products_is_test", table_name="products")
    if _column_exists("clients", "is_test"):
        op.drop_column("clients", "is_test")
    if _column_exists("products", "is_test"):
        op.drop_column("products", "is_test")
