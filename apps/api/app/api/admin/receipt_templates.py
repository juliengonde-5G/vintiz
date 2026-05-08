"""Admin CRUD for ``ReceiptTemplate`` rows — manager personalises tickets/invoices.

Two kinds of templates coexist (``ReceiptKind``):
- ``ticket``   : everyday B2C receipt printed by the MUNBYN
- ``invoice``  : B2B invoice with SIRET + detailed VAT breakdown (PDF A4)

At least one ``is_default=True`` template per kind exists at all times — the
seed migration 0035 inserts both. ``set-default`` flips the flag atomically so
exactly one default per kind remains.

NF525 note: editing a template never alters historical receipts because the
sale snapshots ``transactions.template_id`` at signature time.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_or_404
from app.core.security import RoleChecker
from app.models.receipt_template import ReceiptKind, ReceiptTemplate

router = APIRouter(tags=["admin"])

manager_only = RoleChecker(["manager"])


class ReceiptTemplateRequest(BaseModel):
    name: str
    kind: ReceiptKind
    title: str
    footer: str = ""
    conditions_retour: str | None = None
    show_tva_breakdown: bool = False
    show_loyalty_footer: bool = True
    is_active: bool = True


def _serialize(t: ReceiptTemplate) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "kind": t.kind.value,
        "title": t.title,
        "footer": t.footer or "",
        "conditions_retour": t.conditions_retour,
        "show_tva_breakdown": bool(t.show_tva_breakdown),
        "show_loyalty_footer": bool(t.show_loyalty_footer),
        "is_default": bool(t.is_default),
        "is_active": bool(t.is_active),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("/receipt-templates", dependencies=[Depends(manager_only)])
async def list_receipt_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    kind: ReceiptKind | None = Query(default=None),
    only_active: bool = Query(default=False),
):
    """List receipt/invoice templates, optionally filtered by kind/active."""
    stmt = select(ReceiptTemplate).order_by(
        ReceiptTemplate.kind,
        ReceiptTemplate.is_default.desc(),
        ReceiptTemplate.name,
    )
    if kind is not None:
        stmt = stmt.where(ReceiptTemplate.kind == kind)
    if only_active:
        stmt = stmt.where(ReceiptTemplate.is_active.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    return {"templates": [_serialize(t) for t in rows]}


@router.get("/receipt-templates/{template_id}", dependencies=[Depends(manager_only)])
async def get_receipt_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await get_or_404(db, ReceiptTemplate, template_id, detail="Template introuvable")
    return _serialize(row)


@router.post(
    "/receipt-templates",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(manager_only)],
)
async def create_receipt_template(
    payload: ReceiptTemplateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = ReceiptTemplate(
        name=payload.name.strip(),
        kind=payload.kind,
        title=payload.title.strip(),
        footer=payload.footer or "",
        conditions_retour=payload.conditions_retour,
        show_tva_breakdown=payload.show_tva_breakdown,
        show_loyalty_footer=payload.show_loyalty_footer,
        is_default=False,
        is_active=payload.is_active,
    )
    db.add(row)
    await db.flush()
    await db.commit()
    return _serialize(row)


@router.put(
    "/receipt-templates/{template_id}",
    dependencies=[Depends(manager_only)],
)
async def update_receipt_template(
    template_id: uuid.UUID,
    payload: ReceiptTemplateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await get_or_404(db, ReceiptTemplate, template_id, detail="Template introuvable")
    row.name = payload.name.strip()
    row.kind = payload.kind
    row.title = payload.title.strip()
    row.footer = payload.footer or ""
    row.conditions_retour = payload.conditions_retour
    row.show_tva_breakdown = payload.show_tva_breakdown
    row.show_loyalty_footer = payload.show_loyalty_footer
    row.is_active = payload.is_active
    await db.flush()
    await db.commit()
    return _serialize(row)


@router.delete(
    "/receipt-templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(manager_only)],
)
async def delete_receipt_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Soft-delete (mark ``is_active=false``). Refuses if the template is the
    default for its kind — flip the default elsewhere first."""
    row = await get_or_404(db, ReceiptTemplate, template_id, detail="Template introuvable")
    if row.is_default:
        raise HTTPException(
            status_code=400,
            detail=(
                "Ce template est défini par défaut pour le kind "
                f"'{row.kind.value}'. Désignez un autre template par défaut "
                "avant de le désactiver."
            ),
        )
    row.is_active = False
    await db.flush()
    await db.commit()
    return None


@router.post(
    "/receipt-templates/{template_id}/set-default",
    dependencies=[Depends(manager_only)],
)
async def set_default_receipt_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Promote the template as the default for its kind, atomically demoting
    the previous default. The selected template must be active."""
    row = await get_or_404(db, ReceiptTemplate, template_id, detail="Template introuvable")
    if not row.is_active:
        raise HTTPException(
            status_code=400,
            detail="Impossible de définir un template inactif comme défaut.",
        )

    await db.execute(
        update(ReceiptTemplate)
        .where(
            ReceiptTemplate.kind == row.kind,
            ReceiptTemplate.id != row.id,
        )
        .values(is_default=False)
    )
    row.is_default = True
    await db.flush()
    await db.commit()
    return _serialize(row)
