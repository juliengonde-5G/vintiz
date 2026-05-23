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
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
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
    # Studio fields (mostly invoices) — see ReceiptTemplate model.
    accent_color: str = "#0B7A6A"
    header_note: str | None = None
    payment_terms: str | None = None
    legal_mentions: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    sms_body: str | None = None
    show_payment_block: bool = True
    show_legal_mentions: bool = True
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
        "accent_color": t.accent_color or "#0B7A6A",
        "header_note": t.header_note,
        "payment_terms": t.payment_terms,
        "legal_mentions": t.legal_mentions,
        "email_subject": t.email_subject,
        "email_body": t.email_body,
        "sms_body": t.sms_body,
        "show_payment_block": bool(t.show_payment_block),
        "show_legal_mentions": bool(t.show_legal_mentions),
        "is_default": bool(t.is_default),
        "is_active": bool(t.is_active),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _draft_from_request(payload: ReceiptTemplateRequest) -> ReceiptTemplate:
    """Transient (un-persisted) template carrying the draft's fields, so the
    live preview reflects unsaved edits."""
    return ReceiptTemplate(
        name=payload.name,
        kind=payload.kind,
        title=payload.title,
        footer=payload.footer or "",
        conditions_retour=payload.conditions_retour,
        show_tva_breakdown=payload.show_tva_breakdown,
        show_loyalty_footer=payload.show_loyalty_footer,
        accent_color=payload.accent_color or "#0B7A6A",
        header_note=payload.header_note,
        payment_terms=payload.payment_terms,
        legal_mentions=payload.legal_mentions,
        email_subject=payload.email_subject,
        email_body=payload.email_body,
        show_payment_block=payload.show_payment_block,
        show_legal_mentions=payload.show_legal_mentions,
        is_default=False,
        is_active=payload.is_active,
    )


def _sample_invoice_transaction() -> SimpleNamespace:
    """Synthetic transaction used to render a representative invoice preview."""
    def _item(name: str, qty: int, unit_ttc: float, discount: float = 0.0):
        line_ttc = round(unit_ttc * qty * (1 - discount / 100), 2)
        return SimpleNamespace(
            product=SimpleNamespace(name=name),
            quantity=qty,
            unit_price=unit_ttc,
            line_total=line_ttc,
            discount_percent=discount,
        )

    items = [
        _item("Manteau en laine — Burberry (T.40)", 1, 120.0),
        _item("Sac à main cuir — Lancel", 1, 90.0, 10.0),
        _item("Foulard en soie — Hermès", 2, 45.0),
    ]
    total_ttc = round(sum(i.line_total for i in items), 2)
    total_ht = round(total_ttc / 1.20, 2)
    total_tva = round(total_ttc - total_ht, 2)
    return SimpleNamespace(
        invoice_number=1,
        transaction_number=1042,
        created_at=datetime.now(timezone.utc),
        items=items,
        payments=[SimpleNamespace(method="card", amount=total_ttc)],
        client_company_name="Société Démo SARL",
        client_billing_address="12 rue de l'Exemple\n75000 Paris",
        client_siret="12345678900012",
        total_ht=total_ht,
        total_tva=total_tva,
        total_ttc=total_ttc,
        hash_chain="DEMO0000000000000000000000000000",
    )


@router.post(
    "/receipt-templates/preview-invoice.pdf",
    dependencies=[Depends(manager_only)],
)
async def preview_invoice_pdf(payload: ReceiptTemplateRequest):
    """Render a sample B2B invoice PDF from an unsaved draft template — powers
    the live preview in the Tickets & Factures studio."""
    from app.services.invoice_pdf import generate_invoice_pdf

    draft = _draft_from_request(payload)
    pdf_bytes = generate_invoice_pdf(_sample_invoice_transaction(), template=draft)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="apercu-facture.pdf"'},
    )


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
        accent_color=payload.accent_color or "#0B7A6A",
        header_note=payload.header_note,
        payment_terms=payload.payment_terms,
        legal_mentions=payload.legal_mentions,
        email_subject=payload.email_subject,
        email_body=payload.email_body,
        sms_body=payload.sms_body,
        show_payment_block=payload.show_payment_block,
        show_legal_mentions=payload.show_legal_mentions,
        is_default=False,
        is_active=payload.is_active,
    )
    db.add(row)
    await db.flush()
    await db.commit()
    await db.refresh(row)
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
    row.accent_color = payload.accent_color or "#0B7A6A"
    row.header_note = payload.header_note
    row.payment_terms = payload.payment_terms
    row.legal_mentions = payload.legal_mentions
    row.email_subject = payload.email_subject
    row.email_body = payload.email_body
    row.sms_body = payload.sms_body
    row.show_payment_block = payload.show_payment_block
    row.show_legal_mentions = payload.show_legal_mentions
    row.is_active = payload.is_active
    await db.flush()
    await db.commit()
    await db.refresh(row)
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
    await db.refresh(row)
    return _serialize(row)
