"""Database backup bookkeeping — one row per dump + a singleton config.

Backs the admin "gestionnaire de base de données" : the nightly cron and the
manual trigger both write a ``DatabaseBackup`` row (so each backup is listable
and downloadable), and ``DatabaseBackupConfig`` holds the editable settings
(retention, alert email, nightly schedule on/off).
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType


class DatabaseBackup(Base):
    __tablename__ = "database_backups"

    # File on the prod server (under settings.BACKUP_DIR). ``path`` is absolute
    # so the download endpoint can stream it back; ``filename`` is what the
    # operator sees / downloads.
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # pending → success | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # auto (nightly cron) | manual (admin trigger)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    db_engine: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # ``full`` = exhaustive archive (DB dump + uploads + config) as a .tar.gz ;
    # ``db`` = legacy DB-only dump (.sql.gz). Lets the operator pick coverage.
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    # Inventory of what the archive contains (db bytes, photo count/size, config
    # files…) — surfaced in the admin UI so the manager can see the coverage.
    manifest: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    # Sanitised error message when status == failed (full trace stays in logs).
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DatabaseBackupConfig(Base):
    """Singleton — backup settings editable from the manager UI."""

    __tablename__ = "database_backup_configs"

    # Backups older than this are pruned (files + rows) after each run.
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # Recipient of the failure alert. Blank → falls back to SMTP_FROM.
    alert_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Master switch for the nightly 03:00 cron (manual runs always work).
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # When True (default), each backup is an *exhaustive* archive bundling the
    # uploaded photos + on-disk config (app/hardware/branding) next to the DB
    # dump. When False, the backup is the legacy DB-only .sql.gz.
    include_files: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
