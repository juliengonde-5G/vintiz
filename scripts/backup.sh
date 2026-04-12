#!/usr/bin/env bash
# ===========================================
# Vintiz V2 - Backup quotidien PostgreSQL
# ===========================================
# Ajouter au crontab: 0 3 * * * /path/to/vintiz/scripts/backup.sh
# Conserve 30 jours de backups.

set -euo pipefail

BACKUP_DIR="/opt/vintiz/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Backup PostgreSQL Vintiz..."

docker exec vintiz-db pg_dump -U vintiz vintiz | gzip > "$BACKUP_DIR/vintiz_${DATE}.sql.gz"

echo "[$(date)] Backup cree: vintiz_${DATE}.sql.gz ($(du -h "$BACKUP_DIR/vintiz_${DATE}.sql.gz" | cut -f1))"

# Nettoyage des anciens backups
find "$BACKUP_DIR" -name "vintiz_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

echo "[$(date)] Nettoyage: backups de plus de ${RETENTION_DAYS} jours supprimes."
