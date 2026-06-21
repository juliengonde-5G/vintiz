"""exhaustive backups — archive kind + manifest + include_files toggle

Revision ID: 0062
Revises: 0061
Create Date: 2026-06-21

Makes the nightly/manual backup *exhaustive*: a "full" backup is now a single
``.tar.gz`` bundling the gzipped SQL dump together with everything that lives
outside the database — uploaded product/permanent photos and the on-disk config
(``app_config.json``, ``hardware.json``, the branding logo).

Adds:
  - ``database_backups.kind``      full | db   (which coverage the archive has)
  - ``database_backups.manifest``  JSON inventory of the archive contents
  - ``database_backup_configs.include_files``  master toggle (default ON)

Idempotent: each column is added only when missing, so re-running ``upgrade``
(or running it after ``create_all`` already added the column in dev) is safe.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    cols = [c["name"] for c in sa.inspect(conn).get_columns(table)]
    return column in cols


def _json_type():
    """JSONB on PostgreSQL, portable JSON elsewhere (SQLite tests)."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    if not _has_column("database_backups", "kind"):
        op.add_column(
            "database_backups",
            sa.Column("kind", sa.String(20), nullable=False, server_default="full"),
        )
    if not _has_column("database_backups", "manifest"):
        op.add_column(
            "database_backups",
            sa.Column("manifest", _json_type(), nullable=True),
        )
    if not _has_column("database_backup_configs", "include_files"):
        op.add_column(
            "database_backup_configs",
            sa.Column(
                "include_files",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )


def downgrade() -> None:
    if _has_column("database_backup_configs", "include_files"):
        op.drop_column("database_backup_configs", "include_files")
    if _has_column("database_backups", "manifest"):
        op.drop_column("database_backups", "manifest")
    if _has_column("database_backups", "kind"):
        op.drop_column("database_backups", "kind")
