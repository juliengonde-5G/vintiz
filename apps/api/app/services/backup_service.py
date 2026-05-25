"""Backup PostgreSQL → S3-compatible (OVH, Scaleway, AWS…).

Workflow :
1. pg_dump -Fc (format custom, compressé)
2. Upload vers le bucket S3 configuré
3. Email de confirmation avec taille + SHA-256

Variables d'environnement :
  S3_BACKUP_BUCKET       — nom du bucket (obligatoire)
  S3_BACKUP_ENDPOINT     — endpoint S3 (ex : s3.gra.io.cloud.ovh.net)
  S3_BACKUP_ACCESS_KEY   — access key
  S3_BACKUP_SECRET_KEY   — secret key
  S3_BACKUP_PREFIX       — préfixe du chemin (défaut : vintiz-backups)
  S3_BACKUP_REGION       — région (défaut : fr-par)
  BACKUP_ALERT_EMAIL     — destinataire email (défaut : vernon@vintiz.fr)
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

_log = logging.getLogger("vintiz.backup")


@dataclass
class BackupResult:
    success: bool
    filename: str
    size_bytes: int = 0
    sha256: str = ""
    s3_key: str = ""
    error: str = ""
    duration_s: float = 0.0


class BackupService:
    def __init__(self) -> None:
        self.bucket = os.getenv("S3_BACKUP_BUCKET", "")
        self.endpoint = os.getenv("S3_BACKUP_ENDPOINT", "")
        self.access_key = os.getenv("S3_BACKUP_ACCESS_KEY", "")
        self.secret_key = os.getenv("S3_BACKUP_SECRET_KEY", "")
        self.prefix = os.getenv("S3_BACKUP_PREFIX", "vintiz-backups")
        self.region = os.getenv("S3_BACKUP_REGION", "fr-par")
        self.alert_email = os.getenv("BACKUP_ALERT_EMAIL", "vernon@vintiz.fr")

    @property
    def is_configured(self) -> bool:
        return bool(self.bucket and self.access_key and self.secret_key)

    def _parse_db_url(self) -> dict:
        raw = os.getenv("DATABASE_URL", "")
        # Normalize asyncpg → psycopg2 scheme for pg_dump
        raw = raw.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(raw)
        return {
            "host": parsed.hostname or "localhost",
            "port": str(parsed.port or 5432),
            "user": parsed.username or "postgres",
            "password": parsed.password or "",
            "dbname": (parsed.path or "/vintiz").lstrip("/"),
        }

    def _pg_dump(self, tmp_path: Path) -> None:
        params = self._parse_db_url()
        env = os.environ.copy()
        env["PGPASSWORD"] = params["password"]
        cmd = [
            "pg_dump",
            "-h", params["host"],
            "-p", params["port"],
            "-U", params["user"],
            "-Fc",            # custom format (compressed)
            "-f", str(tmp_path),
            params["dbname"],
        ]
        result = subprocess.run(cmd, env=env, capture_output=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr.decode()[:300]}")

    def _sha256_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _upload_s3(self, local_path: Path, s3_key: str) -> None:
        try:
            import boto3
            kwargs: dict = {
                "aws_access_key_id": self.access_key,
                "aws_secret_access_key": self.secret_key,
                "region_name": self.region,
            }
            if self.endpoint:
                kwargs["endpoint_url"] = f"https://{self.endpoint}"
            s3 = boto3.client("s3", **kwargs)
            s3.upload_file(str(local_path), self.bucket, s3_key)
        except ImportError:
            raise RuntimeError("boto3 not installed — pip install boto3")

    async def run_backup(self) -> BackupResult:
        import time
        t0 = time.monotonic()
        now = datetime.now(timezone.utc)
        filename = f"vintiz_{now.strftime('%Y%m%d_%H%M%S')}.dump"
        s3_key = f"{self.prefix}/{now.strftime('%Y/%m')}/{filename}"

        if not self.is_configured:
            _log.warning("Backup skipped — S3 not configured (S3_BACKUP_BUCKET missing)")
            return BackupResult(success=False, filename=filename, error="S3 non configuré")

        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / filename
            try:
                _log.info("Starting pg_dump → %s", filename)
                self._pg_dump(dump_path)
                size = dump_path.stat().st_size
                sha = self._sha256_file(dump_path)
                _log.info("pg_dump OK — %d bytes — uploading to s3://%s/%s", size, self.bucket, s3_key)
                self._upload_s3(dump_path, s3_key)
                duration = round(time.monotonic() - t0, 1)
                _log.info("Backup upload OK — %.1fs", duration)
                result = BackupResult(
                    success=True,
                    filename=filename,
                    size_bytes=size,
                    sha256=sha,
                    s3_key=s3_key,
                    duration_s=duration,
                )
                await self._send_confirmation(result)
                return result
            except Exception as exc:
                duration = round(time.monotonic() - t0, 1)
                _log.error("Backup failed after %.1fs: %s", duration, exc)
                result = BackupResult(
                    success=False,
                    filename=filename,
                    error=str(exc)[:300],
                    duration_s=duration,
                )
                await self._send_failure(result)
                return result

    async def _send_confirmation(self, result: BackupResult) -> None:
        try:
            from app.services.email_gateway import EmailMessage, send_email
            size_mb = result.size_bytes / 1_048_576
            html = f"""
<p>✅ <strong>Backup PostgreSQL réussi</strong></p>
<ul>
  <li>Fichier : <code>{result.filename}</code></li>
  <li>Taille : {size_mb:.2f} Mo</li>
  <li>SHA-256 : <code style="font-size:11px">{result.sha256}</code></li>
  <li>Destination : <code>s3://{self.bucket}/{result.s3_key}</code></li>
  <li>Durée : {result.duration_s:.1f}s</li>
</ul>
"""
            send_email(EmailMessage(
                to=self.alert_email,
                subject=f"✅ Vintiz Backup — {result.filename} ({size_mb:.1f} Mo)",
                html=html,
                tags=["backup", "success"],
            ))
        except Exception as exc:
            _log.warning("Backup confirmation email failed: %s", exc)

    async def _send_failure(self, result: BackupResult) -> None:
        try:
            from app.services.email_gateway import EmailMessage, send_email
            html = f"""
<p>❌ <strong>Backup PostgreSQL ÉCHOUÉ</strong></p>
<ul>
  <li>Fichier : <code>{result.filename}</code></li>
  <li>Durée : {result.duration_s:.1f}s</li>
  <li>Erreur : <code>{result.error}</code></li>
</ul>
<p>Vérifier la connexion PostgreSQL et les variables S3_BACKUP_*.</p>
"""
            send_email(EmailMessage(
                to=self.alert_email,
                subject=f"❌ Vintiz Backup ÉCHOUÉ — {result.filename}",
                html=html,
                tags=["backup", "failure"],
            ))
        except Exception as exc:
            _log.warning("Backup failure email send failed: %s", exc)
