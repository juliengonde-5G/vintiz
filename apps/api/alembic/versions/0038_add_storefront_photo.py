"""add storefront photo fields (background-removed branded copy)

Revision ID: 0038
Revises: 0037
Create Date: 2026-05-22

Adds the branded, background-removed storefront copy of product photos:
- ``product_photos.processed_url``      → URL of the cleaned-up vitrine image
- ``product_photos.processing_status``  → done | skipped | failed | pending
- ``products.storefront_photo_url``     → mirror of the primary photo's
  processed_url (kept in sync by PhotoService, alongside ``photo_url``).

All columns are NULL-able : existing rows keep their raw photo as-is until a
new upload (or a manual regenerate) produces a storefront copy.

Idempotent : skips the ALTER when the column is already present (this project
deploys with ``alembic upgrade head`` on every release).
"""

from alembic import op
import sqlalchemy as sa


revision = "0038"
down_revision = "0037"
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


ADDITIONS = [
    ("product_photos", "processed_url", sa.Text()),
    ("product_photos", "processing_status", sa.String(20)),
    ("products", "storefront_photo_url", sa.Text()),
]


def upgrade() -> None:
    for table, name, type_ in ADDITIONS:
        if not _column_exists(table, name):
            op.add_column(table, sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for table, name, _ in ADDITIONS:
        if _column_exists(table, name):
            op.drop_column(table, name)
