"""Admin — gestionnaire de base de données.

État de la base, réglages de sauvegarde (rétention / email d'alerte / cron
on-off), liste des sauvegardes (téléchargeables), déclenchement manuel d'une
sauvegarde et exports CSV. Tout est réservé au manager.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker
from app.services import database_backup as svc

router = APIRouter(tags=["admin"])

manager_only = RoleChecker(["manager"])


class BackupConfigIn(BaseModel):
    retention_days: int | None = None
    alert_email: str | None = None
    enabled: bool | None = None


def _config_out(cfg) -> dict:
    return {
        "retention_days": cfg.retention_days,
        "alert_email": cfg.alert_email,
        "enabled": cfg.enabled,
    }


@router.get("/database/state", dependencies=[Depends(manager_only)])
async def database_state(db: Annotated[AsyncSession, Depends(get_db)]):
    """Volumes par table, taille de la base, dernière sauvegarde."""
    return await svc.database_state(db)


@router.get("/database/config", dependencies=[Depends(manager_only)])
async def get_backup_config(db: Annotated[AsyncSession, Depends(get_db)]):
    cfg = await svc.get_config(db)
    await db.commit()
    return _config_out(cfg)


@router.put("/database/config", dependencies=[Depends(manager_only)])
async def update_backup_config(
    body: BackupConfigIn,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cfg = await svc.upsert_config(db, body.model_dump(exclude_unset=True))
    await db.commit()
    return _config_out(cfg)


@router.get("/database/backups", dependencies=[Depends(manager_only)])
async def list_backups(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(100, ge=1, le=500),
):
    return {"backups": await svc.list_backups(db, limit=limit)}


@router.post("/database/backups/run", dependencies=[Depends(manager_only)])
async def run_backup_now(db: Annotated[AsyncSession, Depends(get_db)]):
    """Lancer manuellement une sauvegarde complète de la base."""
    backup = await svc.run_backup(db, trigger="manual")
    out = svc.serialize_backup(backup)
    if backup.status == "failed":
        # Surface the failure to the operator but keep the recorded row.
        return {"ok": False, "backup": out, "detail": backup.error}
    return {"ok": True, "backup": out}


@router.get("/database/backups/{backup_id}/download", dependencies=[Depends(manager_only)])
async def download_backup(
    backup_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    backup = await svc.get_backup(db, backup_id)
    if backup is None:
        raise HTTPException(status_code=404, detail="Sauvegarde introuvable")
    if backup.status != "success":
        raise HTTPException(status_code=409, detail="Sauvegarde non aboutie — rien à télécharger")
    path = Path(backup.path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Fichier de sauvegarde absent (purgé ?)")
    return FileResponse(
        str(path),
        media_type="application/gzip",
        filename=backup.filename,
    )


@router.delete("/database/backups/{backup_id}", dependencies=[Depends(manager_only)])
async def delete_backup(
    backup_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    backup = await svc.get_backup(db, backup_id)
    if backup is None:
        raise HTTPException(status_code=404, detail="Sauvegarde introuvable")
    try:
        p = Path(backup.path)
        if p.exists():
            p.unlink()
    except OSError:
        pass
    await db.delete(backup)
    await db.commit()
    return {"deleted": True, "id": str(backup_id)}


@router.get("/database/export", dependencies=[Depends(manager_only)])
async def export_table(
    db: Annotated[AsyncSession, Depends(get_db)],
    table: str = Query(..., description="Table à exporter (whitelist)"),
):
    """Générer un export CSV d'une table (produits, clients, transactions…)."""
    try:
        filename, content = await svc.export_table_csv(db, table)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
