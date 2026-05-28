"""Database backup manager — dump, ledger, retention, state, exports.

Powers the admin "gestionnaire de base de données" :
  - ``run_backup`` dumps the whole database to ``settings.BACKUP_DIR`` (pg_dump
    | gzip in prod, sqlite ``iterdump`` in dev) and records a ``DatabaseBackup``
    row so every backup is listable + downloadable. On failure it records the
    row as ``failed`` and emails the alert recipient.
  - the nightly 03:00 cron (app/jobs.py) calls it with ``trigger="auto"`` ; the
    admin endpoint calls it with ``trigger="manual"``.
  - retention prunes files + rows older than ``config.retention_days``.
  - ``database_state`` / ``export_table_csv`` back the manager's state view and
    the "générer des exports" buttons.

The actual dump command lives in the module-level ``dump_database`` so it can be
monkeypatched in tests (the orchestration is what we unit-test; pg_dump is infra).
"""

from __future__ import annotations

import asyncio
import csv
import gzip
import io
import logging
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.client import Client, LoyaltyAccount
from app.models.database_backup import DatabaseBackup, DatabaseBackupConfig
from app.models.newsletter import NewsletterSubscriber
from app.models.pos import Transaction
from app.models.product import Category, Product
from app.models.user import User

logger = logging.getLogger("vintiz")

_CHUNK = 64 * 1024


def engine_kind() -> str:
    """``sqlite`` | ``postgresql`` from the configured DATABASE_URL."""
    return "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgresql"


def backup_dir() -> Path:
    """Resolve + create the backups directory."""
    d = Path(settings.BACKUP_DIR).expanduser().resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Dump implementation (monkeypatched in tests)
# ---------------------------------------------------------------------------


def _dump_postgres(dest: Path, url: str) -> None:
    parsed = urlparse(url)
    env = dict(os.environ)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    cmd = [
        "pg_dump",
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", unquote(parsed.username or "postgres"),
        "-d", (parsed.path or "/postgres").lstrip("/"),
        "--no-owner", "--no-privileges",
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "pg_dump introuvable dans le conteneur API — installez "
            "postgresql-client (voir docker/Dockerfile.api)."
        ) from exc
    assert proc.stdout is not None
    with gzip.open(dest, "wb") as gz:
        for chunk in iter(lambda: proc.stdout.read(_CHUNK), b""):
            gz.write(chunk)
    proc.stdout.close()
    ret = proc.wait()
    if ret != 0:
        err = proc.stderr.read().decode("utf-8", "replace")[:500] if proc.stderr else ""
        raise RuntimeError(f"pg_dump a échoué (code {ret}) : {err.strip()}")


def _dump_sqlite(dest: Path, url: str) -> None:
    import sqlite3

    path = url.split("///", 1)[1] if "///" in url else ""
    if not path or path == ":memory:":
        raise RuntimeError("Base SQLite en mémoire — sauvegarde fichier impossible")
    con = sqlite3.connect(path)
    try:
        with gzip.open(dest, "wt", encoding="utf-8") as gz:
            for line in con.iterdump():
                gz.write(f"{line}\n")
    finally:
        con.close()


def dump_database(dest: Path) -> None:
    """Dump the whole database to ``dest`` (gzipped). Raises on failure."""
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        _dump_sqlite(dest, url)
    else:
        _dump_postgres(dest, url)


# ---------------------------------------------------------------------------
# Config (singleton)
# ---------------------------------------------------------------------------


async def get_config(db: AsyncSession) -> DatabaseBackupConfig:
    cfg = (await db.execute(select(DatabaseBackupConfig).limit(1))).scalar_one_or_none()
    if cfg is None:
        cfg = DatabaseBackupConfig()
        db.add(cfg)
        await db.flush()
    return cfg


async def upsert_config(db: AsyncSession, data: dict) -> DatabaseBackupConfig:
    cfg = await get_config(db)
    for key in ("retention_days", "alert_email", "enabled"):
        if key in data and data[key] is not None:
            setattr(cfg, key, data[key])
    if cfg.retention_days is not None and cfg.retention_days < 1:
        cfg.retention_days = 1
    await db.flush()
    return cfg


def _alert_recipient(cfg: DatabaseBackupConfig) -> str | None:
    return (
        (cfg.alert_email or "").strip()
        or (settings.BACKUP_ALERT_EMAIL or "").strip()
        or (settings.SMTP_FROM or "").strip()
        or None
    )


def _send_failure_alert(recipient: str, backup: DatabaseBackup) -> None:
    """Best-effort failure email — never raises (called from a cron)."""
    try:
        from app.services.email_gateway import EmailMessage, send_email

        msg = EmailMessage(
            to=recipient,
            subject="⚠️ Vintiz — échec de la sauvegarde base de données",
            html=(
                "<p>La sauvegarde automatique de la base de données a <strong>échoué</strong>.</p>"
                f"<p>Fichier&nbsp;: <code>{backup.filename}</code><br>"
                f"Déclenchement&nbsp;: {backup.trigger}<br>"
                f"Erreur&nbsp;: {backup.error or 'inconnue'}</p>"
                "<p>Vérifiez l'espace disque et la configuration "
                "(gestionnaire de base de données dans l'admin).</p>"
                "<p>— Vintiz Vernon</p>"
            ),
            text=f"Échec sauvegarde DB ({backup.filename}) : {backup.error or 'inconnue'}",
            tags=["backup-alert"],
        )
        result = send_email(msg)
        logger.info("Backup alert email: status=%s backend=%s", result.status, result.backend)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Backup alert email could not be sent: %s", exc)


# ---------------------------------------------------------------------------
# Run a backup
# ---------------------------------------------------------------------------


async def run_backup(db: AsyncSession, *, trigger: str = "manual") -> DatabaseBackup:
    """Dump the DB, record a ledger row, prune old backups, alert on failure."""
    cfg = await get_config(db)
    kind = engine_kind()
    ts = datetime.now(timezone.utc)
    filename = f"vintiz_{ts.strftime('%Y%m%d_%H%M%S')}.sql.gz"
    dest = backup_dir() / filename

    backup = DatabaseBackup(
        filename=filename,
        path=str(dest),
        status="pending",
        trigger=trigger if trigger in ("auto", "manual") else "manual",
        db_engine=kind,
        started_at=ts,
    )
    db.add(backup)
    await db.flush()

    started = time.monotonic()
    try:
        await asyncio.to_thread(dump_database, dest)
        size = dest.stat().st_size if dest.exists() else 0
        backup.status = "success"
        backup.size_bytes = int(size)
        backup.finished_at = datetime.now(timezone.utc)
        backup.duration_ms = int((time.monotonic() - started) * 1000)
        logger.info("DB backup OK: %s (%d bytes, %s)", filename, size, trigger)
    except Exception as exc:  # noqa: BLE001
        logger.exception("DB backup failed: %s", exc)
        backup.status = "failed"
        backup.error = f"{type(exc).__name__}: {exc}"[:500]
        backup.finished_at = datetime.now(timezone.utc)
        backup.duration_ms = int((time.monotonic() - started) * 1000)
        # Drop any partial/corrupt file so it isn't offered for download.
        try:
            if dest.exists():
                dest.unlink()
        except OSError:
            pass
        recipient = _alert_recipient(cfg)
        if recipient:
            await asyncio.to_thread(_send_failure_alert, recipient, backup)
        else:
            logger.warning("Backup failed and no alert recipient configured")

    await db.commit()
    # Retention is best-effort; a failure here must not mask the backup result.
    try:
        await apply_retention(db, cfg.retention_days)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Backup retention pass failed: %s", exc)
    return backup


async def apply_retention(db: AsyncSession, retention_days: int) -> int:
    """Delete backups (file + row) older than ``retention_days``. Returns count."""
    if not retention_days or retention_days < 1:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    rows = (
        await db.execute(select(DatabaseBackup).where(DatabaseBackup.created_at < cutoff))
    ).scalars().all()
    n = 0
    for row in rows:
        try:
            p = Path(row.path)
            if p.exists():
                p.unlink()
        except OSError as exc:
            logger.warning("Could not delete backup file %s: %s", row.path, exc)
        await db.delete(row)
        n += 1
    if n:
        await db.commit()
        logger.info("Backup retention: pruned %d backup(s) older than %dd", n, retention_days)
    return n


# ---------------------------------------------------------------------------
# Listing / state
# ---------------------------------------------------------------------------


def serialize_backup(b: DatabaseBackup) -> dict:
    return {
        "id": str(b.id),
        "filename": b.filename,
        "size_bytes": b.size_bytes,
        "status": b.status,
        "trigger": b.trigger,
        "db_engine": b.db_engine,
        "error": b.error,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "started_at": b.started_at.isoformat() if b.started_at else None,
        "finished_at": b.finished_at.isoformat() if b.finished_at else None,
        "duration_ms": b.duration_ms,
        # A file is downloadable only when the dump succeeded and is on disk.
        "downloadable": b.status == "success" and bool(b.path) and Path(b.path).exists(),
    }


async def list_backups(db: AsyncSession, *, limit: int = 100) -> list[dict]:
    rows = (
        await db.execute(
            select(DatabaseBackup).order_by(DatabaseBackup.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [serialize_backup(b) for b in rows]


async def get_backup(db: AsyncSession, backup_id) -> DatabaseBackup | None:
    return (
        await db.execute(select(DatabaseBackup).where(DatabaseBackup.id == backup_id))
    ).scalar_one_or_none()


async def _db_size_bytes(db: AsyncSession) -> int | None:
    try:
        if engine_kind() == "postgresql":
            return int(
                (await db.execute(text("SELECT pg_database_size(current_database())"))).scalar_one()
            )
        page_count = (await db.execute(text("PRAGMA page_count"))).scalar_one()
        page_size = (await db.execute(text("PRAGMA page_size"))).scalar_one()
        return int(page_count) * int(page_size)
    except Exception as exc:  # noqa: BLE001
        logger.debug("db size unavailable: %s", exc)
        return None


# Curated set surfaced in the manager's state view (also the CSV export whitelist).
_TABLE_MODELS = {
    "products": Product,
    "categories": Category,
    "clients": Client,
    "loyalty_accounts": LoyaltyAccount,
    "transactions": Transaction,
    "users": User,
    "newsletter_subscribers": NewsletterSubscriber,
}
# Tables the operator may export to CSV (subset that is safe / useful, no PII dumps
# beyond what the RGPD exports already allow at row level).
EXPORTABLE_TABLES = ("products", "categories", "clients", "transactions", "newsletter_subscribers")


async def database_state(db: AsyncSession) -> dict:
    counts: dict[str, int] = {}
    for label, model in _TABLE_MODELS.items():
        try:
            counts[label] = int(
                (await db.execute(select(func.count()).select_from(model))).scalar_one()
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("count for %s failed: %s", label, exc)
            counts[label] = -1

    last = (
        await db.execute(select(DatabaseBackup).order_by(DatabaseBackup.created_at.desc()).limit(1))
    ).scalar_one_or_none()
    last_success = (
        await db.execute(
            select(DatabaseBackup)
            .where(DatabaseBackup.status == "success")
            .order_by(DatabaseBackup.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    total = int((await db.execute(select(func.count()).select_from(DatabaseBackup))).scalar_one())

    return {
        "engine": engine_kind(),
        "size_bytes": await _db_size_bytes(db),
        "table_counts": counts,
        "backup_count": total,
        "last_backup": serialize_backup(last) if last else None,
        "last_success_at": last_success.created_at.isoformat() if last_success else None,
        "backup_dir": str(backup_dir()),
        "exportable_tables": list(EXPORTABLE_TABLES),
    }


async def export_table_csv(db: AsyncSession, table_key: str) -> tuple[str, str]:
    """Stream one whitelisted table to CSV. Returns (filename, csv_text)."""
    if table_key not in EXPORTABLE_TABLES:
        raise ValueError(f"Table non exportable : {table_key}")
    table = _TABLE_MODELS[table_key].__table__
    columns = [c.name for c in table.columns]
    # Core select on the table (not the ORM entity) so we don't trigger
    # selectin relationship loads — we just want the raw rows.
    result = await db.execute(table.select())

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(columns)
    for row in result:
        m = row._mapping
        writer.writerow([_csv_value(m[c]) for c in columns])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"vintiz_{table_key}_{stamp}.csv", buf.getvalue()


def _csv_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):  # Enum
        return str(value.value)
    return str(value)
