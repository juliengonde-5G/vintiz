"""Admin CRUD for ``SumUpTerminal`` rows — multi-terminal registry.

Vintiz can drive several SumUp Solo terminals (e.g. *caisse Lenovo dock* +
*TPE mobile S11 Ultra*). This router lets the manager declare each one with
its ``reader_id`` and a friendly label, mark a default, and probe the live
SumUp Readers API for a heartbeat.

The legacy single-terminal ``SUMUP_READER_ID`` env var / ``sumup-config``
endpoint still works (priority DB > env in ``SumUpService``); when at least
one ``SumUpTerminal`` row is marked ``is_default`` and active, the POS will
prefer it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_or_404
from app.core.security import RoleChecker
from app.models.sumup_terminal import SumUpTerminal, SumUpTerminalStatus
from app.services.sumup_service import SUMUP_API_BASE, SumUpService

router = APIRouter(tags=["admin"])

manager_only = RoleChecker(["manager"])


class SumUpTerminalRequest(BaseModel):
    label: str
    reader_id: str
    location: str | None = None
    is_default: bool = False
    notes: str | None = None
    status: SumUpTerminalStatus | None = None


def _serialize(t: SumUpTerminal) -> dict:
    return {
        "id": str(t.id),
        "label": t.label,
        "reader_id": t.reader_id,
        "status": t.status.value,
        "last_heartbeat_at": (
            t.last_heartbeat_at.isoformat() if t.last_heartbeat_at else None
        ),
        "last_heartbeat_status": t.last_heartbeat_status,
        "location": t.location,
        "is_default": bool(t.is_default),
        "notes": t.notes,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("/sumup-terminals", dependencies=[Depends(manager_only)])
async def list_sumup_terminals(
    db: Annotated[AsyncSession, Depends(get_db)],
    only_active: bool = Query(default=False),
):
    """List declared SumUp terminals + live heartbeat snapshot."""
    stmt = select(SumUpTerminal).order_by(
        SumUpTerminal.is_default.desc(),
        SumUpTerminal.label,
    )
    if only_active:
        stmt = stmt.where(SumUpTerminal.status == SumUpTerminalStatus.active)
    rows = (await db.execute(stmt)).scalars().all()
    return {"terminals": [_serialize(t) for t in rows]}


@router.get("/sumup-terminals/{terminal_id}", dependencies=[Depends(manager_only)])
async def get_sumup_terminal(
    terminal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await get_or_404(db, SumUpTerminal, terminal_id, detail="Terminal introuvable")
    return _serialize(row)


@router.post(
    "/sumup-terminals",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(manager_only)],
)
async def create_sumup_terminal(
    payload: SumUpTerminalRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    reader_id = payload.reader_id.strip()
    if not reader_id:
        raise HTTPException(status_code=400, detail="reader_id requis")

    existing = (
        await db.execute(
            select(SumUpTerminal).where(SumUpTerminal.reader_id == reader_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Un terminal avec ce reader_id existe déjà ({existing.label}).",
        )

    if payload.is_default:
        await db.execute(
            update(SumUpTerminal).values(is_default=False)
        )

    row = SumUpTerminal(
        label=payload.label.strip(),
        reader_id=reader_id,
        status=payload.status or SumUpTerminalStatus.unknown,
        location=payload.location,
        is_default=payload.is_default,
        notes=payload.notes,
    )
    db.add(row)
    try:
        await db.flush()
        await db.commit()
    except IntegrityError:
        # Concurrent create with the same reader_id slipped past the
        # app-level check above and hit the UNIQUE constraint. Surface the
        # friendly 409 instead of a raw 500.
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Un terminal avec ce reader_id existe déjà ({reader_id}).",
        )
    return _serialize(row)


@router.put(
    "/sumup-terminals/{terminal_id}",
    dependencies=[Depends(manager_only)],
)
async def update_sumup_terminal(
    terminal_id: uuid.UUID,
    payload: SumUpTerminalRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await get_or_404(db, SumUpTerminal, terminal_id, detail="Terminal introuvable")

    new_reader_id = payload.reader_id.strip()
    if not new_reader_id:
        raise HTTPException(status_code=400, detail="reader_id requis")
    if new_reader_id != row.reader_id:
        clash = (
            await db.execute(
                select(SumUpTerminal).where(
                    SumUpTerminal.reader_id == new_reader_id,
                    SumUpTerminal.id != row.id,
                )
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Un autre terminal utilise déjà ce reader_id ({clash.label}).",
            )

    if payload.is_default and not row.is_default:
        await db.execute(
            update(SumUpTerminal)
            .where(SumUpTerminal.id != row.id)
            .values(is_default=False)
        )

    row.label = payload.label.strip()
    row.reader_id = new_reader_id
    row.location = payload.location
    row.is_default = payload.is_default
    row.notes = payload.notes
    if payload.status is not None:
        row.status = payload.status
    await db.flush()
    await db.commit()
    return _serialize(row)


@router.delete(
    "/sumup-terminals/{terminal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(manager_only)],
)
async def delete_sumup_terminal(
    terminal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Hard delete: the terminal won't appear anymore in the POS picker."""
    row = await get_or_404(db, SumUpTerminal, terminal_id, detail="Terminal introuvable")
    was_default = bool(row.is_default)
    await db.delete(row)
    await db.flush()
    # If we just removed the default terminal, promote another one so the POS
    # never ends up with zero default (which would silently fall back to the
    # env reader or to no push at all).
    if was_default:
        replacement = (
            await db.execute(
                select(SumUpTerminal)
                .order_by(
                    (SumUpTerminal.status == SumUpTerminalStatus.active).desc(),
                    SumUpTerminal.label,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if replacement is not None:
            replacement.is_default = True
    await db.commit()
    return None


@router.post(
    "/sumup-terminals/{terminal_id}/ping",
    dependencies=[Depends(manager_only)],
)
async def ping_sumup_terminal(
    terminal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Probe the live SumUp Readers API for the terminal's status.

    - Production with credentials → calls
      ``GET /merchants/{merchant_code}/readers/{reader_id}`` and updates
      ``last_heartbeat_at`` + ``last_heartbeat_status`` + ``status``.
    - Sandbox or no creds → marks the heartbeat as ``simulated`` and reports
      ``status=unknown`` to the UI without raising.
    """
    row = await get_or_404(db, SumUpTerminal, terminal_id, detail="Terminal introuvable")

    svc = SumUpService()
    now = datetime.now(timezone.utc)

    if svc.environment != "production" or not svc.api_key or not svc.merchant_code:
        row.last_heartbeat_at = now
        row.last_heartbeat_status = "simulated"
        row.status = SumUpTerminalStatus.unknown
        await db.flush()
        await db.commit()
        return {
            **_serialize(row),
            "probe": {
                "ok": True,
                "mode": "simulated",
                "reason": (
                    "SumUp not in production or credentials missing — "
                    "cannot probe a real terminal."
                ),
            },
        }

    url = f"{SUMUP_API_BASE}/merchants/{svc.merchant_code}/readers/{row.reader_id}"
    probe: dict = {"mode": "live", "url": url}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=svc._headers)
        probe["http_status"] = resp.status_code
        if resp.status_code == 200:
            data = resp.json() if resp.content else {}
            row.status = SumUpTerminalStatus.active
            row.last_heartbeat_status = "ok"
            probe["ok"] = True
            probe["body"] = data
        elif resp.status_code == 404:
            row.status = SumUpTerminalStatus.inactive
            row.last_heartbeat_status = "not_found"
            probe["ok"] = False
            probe["error"] = "Reader unknown to SumUp (deleted?)"
        else:
            row.status = SumUpTerminalStatus.unknown
            row.last_heartbeat_status = f"http_{resp.status_code}"
            probe["ok"] = False
            probe["error"] = resp.text[:300]
    except Exception as exc:
        row.status = SumUpTerminalStatus.unknown
        row.last_heartbeat_status = "unreachable"
        probe["ok"] = False
        probe["error"] = f"network error: {exc}"

    row.last_heartbeat_at = now
    await db.flush()
    await db.commit()
    return {**_serialize(row), "probe": probe}


@router.post(
    "/sumup-terminals/sync",
    dependencies=[Depends(manager_only)],
)
async def sync_sumup_terminals(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Pull the live list of readers from SumUp and surface it to the UI.

    Does NOT auto-create rows — the manager picks which ones to register
    (the merchant account may include archived/test readers). Returns the
    merged view: live readers + already-registered terminals so the front
    can render an "Importer" button per row.
    """
    svc = SumUpService()
    if svc.environment != "production" or not svc.api_key or not svc.merchant_code:
        return {
            "live": [],
            "mode": "simulated",
            "reason": "SumUp not in production or credentials missing.",
        }

    url = f"{SUMUP_API_BASE}/merchants/{svc.merchant_code}/readers"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=svc._headers)
        if resp.status_code != 200:
            return {
                "live": [],
                "mode": "live",
                "http_status": resp.status_code,
                "error": resp.text[:300],
            }
        body = resp.json() if resp.content else {}
        readers = body.get("items") or body.get("data") or []
        return {
            "live": readers,
            "mode": "live",
            "count": len(readers),
        }
    except Exception as exc:
        return {
            "live": [],
            "mode": "live",
            "error": f"network error: {exc}",
        }
