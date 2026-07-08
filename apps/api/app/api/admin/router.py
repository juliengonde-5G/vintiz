import asyncio
import csv
import io
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker, get_current_user
from app.models.audit import AuditLog
from app.models.product import Product, ProductStatus
from app.models.user import User

from app.api.admin import seeding as _seeding_module
from app.api.admin import zones as _zones_module
from app.api.admin import offers as _offers_module
from app.api.admin import users as _users_module
from app.api.admin import receipt_templates as _receipt_templates_module
from app.api.admin import sumup_terminals as _sumup_terminals_module
from app.api.admin import database as _database_module
from app.api.admin import price_reference as _price_reference_module

router = APIRouter(prefix="/admin", tags=["admin"])

manager_only = RoleChecker(["manager"])

router.include_router(_seeding_module.router)
router.include_router(_zones_module.router)
router.include_router(_offers_module.router)
router.include_router(_users_module.router)
router.include_router(_receipt_templates_module.router)
router.include_router(_sumup_terminals_module.router)
router.include_router(_database_module.router)
router.include_router(_price_reference_module.router)


# ---------------------------------------------------------------------------
# Monitoring — santé des services externes (DB, Pennylane, SumUp, Brevo)
# ---------------------------------------------------------------------------


@router.get("/monitoring", dependencies=[Depends(manager_only)])
async def get_monitoring_status(db: Annotated[AsyncSession, Depends(get_db)]):
    """Rapport de santé de tous les services externes (manager only)."""
    from app.services.monitoring_service import MonitoringService

    report = await MonitoringService(db).check_all()
    return {
        "all_healthy": report.all_healthy,
        "checked_at": report.checked_at,
        "services": [
            {
                "name": s.name,
                "healthy": s.healthy,
                "latency_ms": s.latency_ms,
                "detail": s.detail,
                "checked_at": s.checked_at,
            }
            for s in report.services
        ],
    }


# ---------------------------------------------------------------------------
# Transactions / payment attempts — admin filterable history (PR 3/6)
# ---------------------------------------------------------------------------


@router.get("/transactions", dependencies=[Depends(manager_only)])
async def list_admin_transactions(
    db: Annotated[AsyncSession, Depends(get_db)],
    period_from: str | None = Query(None, alias="from"),
    period_to: str | None = Query(None, alias="to"),
    method: str | None = Query(None, description="cash | card | cheque | avoir"),
    transaction_type: str | None = Query(
        None, alias="type", description="sale | refund | void"
    ),
    cashier_id: uuid.UUID | None = None,
    min_amount: float | None = Query(None, ge=0),
    max_amount: float | None = Query(None, ge=0),
    is_invoice: bool | None = None,
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
):
    """Filterable transaction history — admin /admin/transactions page.

    Joins payments to filter by method without duplicating rows (DISTINCT).
    Returns the date, ticket #, type (sale / refund / facture), method(s),
    cashier, total TTC + a status flag (locked Z report ⇒ row is fiscal).
    """
    from sqlalchemy import distinct

    from app.models.pos import (
        Payment,
        PaymentMethod,
        Transaction,
        TransactionType,
    )

    stmt = select(Transaction).order_by(Transaction.created_at.desc())

    if period_from:
        stmt = stmt.where(
            Transaction.created_at >= _parse_iso_date(period_from, "from")
        )
    if period_to:
        stmt = stmt.where(
            Transaction.created_at <= _parse_iso_date(period_to, "to")
        )
    if transaction_type:
        try:
            stmt = stmt.where(
                Transaction.transaction_type == TransactionType(transaction_type)
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="type must be one of sale | refund | void",
            )
    if cashier_id is not None:
        stmt = stmt.where(Transaction.cashier_id == cashier_id)
    if min_amount is not None:
        stmt = stmt.where(Transaction.total_ttc >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(Transaction.total_ttc <= max_amount)
    if is_invoice is not None:
        stmt = stmt.where(Transaction.is_invoice.is_(is_invoice))
    if method:
        try:
            method_enum = PaymentMethod(method)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="method must be one of cash | card | cheque | transfer | avoir",
            )
        sub = (
            select(distinct(Payment.transaction_id))
            .where(Payment.method == method_enum)
        )
        stmt = stmt.where(Transaction.id.in_(sub))

    stmt = stmt.offset(max(skip, 0)).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    # Nom de la cliente rattachée — chargé en un seul SELECT groupé (évite le
    # N+1) pour l'afficher directement dans la colonne « Client ».
    from app.models.client import Client

    client_ids = {t.client_id for t in rows if t.client_id}
    client_names: dict[str, str] = {}
    if client_ids:
        crows = await db.execute(
            select(Client.id, Client.first_name, Client.last_name).where(
                Client.id.in_(client_ids)
            )
        )
        for cid, first_name, last_name in crows.all():
            name = f"{(first_name or '').strip()} {(last_name or '').strip()}".strip()
            if name:
                client_names[str(cid)] = name

    out: list[dict] = []
    for t in rows:
        methods = [p.method.value for p in (t.payments or [])]
        # CB Solo detail per card payment — surfaced by the merged
        # /admin/transactions view (transaction ref, masked card, auth code).
        card_payments = [
            {
                "amount": float(p.amount),
                "sumup_transaction_id": p.sumup_transaction_id,
                "sumup_transaction_code": p.sumup_transaction_code,
                "sumup_auth_code": p.sumup_auth_code,
                "sumup_card_brand": p.sumup_card_brand,
                "sumup_card_last4": p.sumup_card_last4,
                "sumup_environment": p.sumup_environment,
            }
            for p in (t.payments or [])
            if p.method == PaymentMethod.card
        ]
        out.append(
            {
                "id": str(t.id),
                "transaction_number": t.transaction_number,
                "type": t.transaction_type.value,
                "is_invoice": bool(t.is_invoice),
                "invoice_number": t.invoice_number,
                "total_ttc": float(t.total_ttc),
                "total_ht": float(t.total_ht),
                "total_tva": float(t.total_tva),
                "methods": methods,
                "card_payments": card_payments,
                "cashier_id": str(t.cashier_id) if t.cashier_id else None,
                "client_id": str(t.client_id) if t.client_id else None,
                "client_name": (
                    client_names.get(str(t.client_id)) if t.client_id else None
                ),
                "client_company_name": t.client_company_name,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
        )
    return {"transactions": out, "count": len(out)}


def _apply_tx_filters(
    stmt,
    *,
    period_from: str | None,
    period_to: str | None,
    transaction_type: str | None,
    method: str | None,
    cashier_id: uuid.UUID | None,
    min_amount: float | None,
    max_amount: float | None,
    is_invoice: bool | None,
):
    """Applique les mêmes filtres que /admin/transactions à un SELECT
    Transaction. Factorisé pour que les exports CSV restent strictement
    alignés sur l'historique affiché à l'écran.
    """
    from sqlalchemy import distinct

    from app.models.pos import Payment, PaymentMethod, Transaction, TransactionType

    if period_from:
        stmt = stmt.where(Transaction.created_at >= _parse_iso_date(period_from, "from"))
    if period_to:
        stmt = stmt.where(Transaction.created_at <= _parse_iso_date(period_to, "to"))
    if transaction_type:
        try:
            stmt = stmt.where(Transaction.transaction_type == TransactionType(transaction_type))
        except ValueError:
            raise HTTPException(status_code=400, detail="type must be one of sale | refund | void")
    if cashier_id is not None:
        stmt = stmt.where(Transaction.cashier_id == cashier_id)
    if min_amount is not None:
        stmt = stmt.where(Transaction.total_ttc >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(Transaction.total_ttc <= max_amount)
    if is_invoice is not None:
        stmt = stmt.where(Transaction.is_invoice.is_(is_invoice))
    if method:
        try:
            method_enum = PaymentMethod(method)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="method must be one of cash | card | cheque | transfer | avoir | voucher",
            )
        sub = select(distinct(Payment.transaction_id)).where(Payment.method == method_enum)
        stmt = stmt.where(Transaction.id.in_(sub))
    return stmt


def _csv_response(rows: list[list], header: list[str], filename: str) -> Response:
    """Sérialise des lignes en CSV (séparateur ';', BOM UTF-8 pour Excel FR)."""
    buf = io.StringIO()
    buf.write("﻿")  # BOM → Excel affiche correctement les accents
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(header)
    for r in rows:
        writer.writerow(["" if v is None else v for v in r])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _ticket_ref(t) -> str:
    if t.is_invoice and t.invoice_number is not None:
        return f"FACT-{t.invoice_number:06d}"
    return f"#{t.transaction_number}"


@router.get("/transactions/export.csv", dependencies=[Depends(manager_only)])
async def export_transactions_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    period_from: str | None = Query(None, alias="from"),
    period_to: str | None = Query(None, alias="to"),
    method: str | None = None,
    transaction_type: str | None = Query(None, alias="type"),
    cashier_id: uuid.UUID | None = None,
    min_amount: float | None = Query(None, ge=0),
    max_amount: float | None = Query(None, ge=0),
    is_invoice: bool | None = None,
):
    """Export CSV — une ligne par transaction (résumé). Mêmes filtres que
    l'historique. Pas de pagination : exporte TOUT le périmètre filtré.
    """
    from app.models.pos import Transaction

    stmt = _apply_tx_filters(
        select(Transaction).order_by(Transaction.created_at.asc()),
        period_from=period_from, period_to=period_to, transaction_type=transaction_type,
        method=method, cashier_id=cashier_id, min_amount=min_amount,
        max_amount=max_amount, is_invoice=is_invoice,
    )
    txns = (await db.execute(stmt)).scalars().all()
    rows = []
    for t in txns:
        rows.append([
            t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
            _ticket_ref(t),
            t.transaction_type.value,
            "facture" if t.is_invoice else "ticket",
            t.client_company_name or "",
            "|".join(p.method.value for p in (t.payments or [])),
            f"{float(t.total_ht):.2f}",
            f"{float(t.total_tva):.2f}",
            f"{float(t.total_ttc):.2f}",
        ])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return _csv_response(
        rows,
        ["Date", "Ticket", "Type", "Document", "Client", "Paiements", "Total HT", "TVA", "Total TTC"],
        f"vintiz_transactions_{stamp}.csv",
    )


# Libellés FR + ordre stable des colonnes par méthode dans l'export détaillé.
# Voucher = bon cadeau ; cheque_cdc = chèque Caisse des Dépôts (collecte
# associative). Si une nouvelle méthode est ajoutée à PaymentMethod, elle
# tombe en colonne « Autre » (cf. _payment_breakdown).
_METHOD_LABELS_FR: list[tuple[str, str]] = [
    ("cash", "Espèces"),
    ("card", "CB"),
    ("cheque", "Chèque"),
    ("cheque_cdc", "Chèque CDC"),
    ("avoir", "Avoir"),
    ("voucher", "Bon cadeau"),
    ("transfer", "Virement"),
]


def _payment_breakdown(payments) -> tuple[str, dict[str, float], float]:
    """Renvoie (mix lisible, montant par méthode, autres).

    - ``mix`` : « Espèces 90,00 € | Bon cadeau 10,00 € » — directement
      lisible dans une cellule. Devises en format FR (virgule), euro.
    - ``per_method`` : {method_key: montant_eur} pour les 7 colonnes
      détaillées (manquantes → vide côté CSV).
    - ``other`` : somme des paiements non-référencés dans
      _METHOD_LABELS_FR (forward-compat si on ajoute un mode).
    """
    label_by_key = dict(_METHOD_LABELS_FR)
    per_method: dict[str, float] = {}
    other = 0.0
    parts: list[tuple[str, float]] = []
    for p in (payments or []):
        key = p.method.value if hasattr(p.method, "value") else str(p.method)
        amt = float(p.amount or 0)
        if key in label_by_key:
            per_method[key] = round(per_method.get(key, 0.0) + amt, 2)
        else:
            other = round(other + amt, 2)
        parts.append((label_by_key.get(key, key), amt))
    mix = " | ".join(
        f"{lbl} {amt:.2f} €".replace(".", ",")
        for lbl, amt in parts
    )
    return mix, per_method, other


@router.get("/transactions/export-detailed.csv", dependencies=[Depends(manager_only)])
async def export_transactions_detailed_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    period_from: str | None = Query(None, alias="from"),
    period_to: str | None = Query(None, alias="to"),
    method: str | None = None,
    transaction_type: str | None = Query(None, alias="type"),
    cashier_id: uuid.UUID | None = None,
    min_amount: float | None = Query(None, ge=0),
    max_amount: float | None = Query(None, ge=0),
    is_invoice: bool | None = None,
):
    """Export CSV détaillé — une ligne par article vendu (avec le ticket
    parent répété). Pour l'analyse fine (catégories, marques, remises,
    ventilation des paiements) côté expert-comptable / tableur.

    La colonne « Paiements » ventile en clair (« Espèces 90,00 € | Bon
    cadeau 10,00 € ») et 7 colonnes par méthode (Espèces / CB / Chèque /
    Chèque CDC / Avoir / Bon cadeau / Virement) donnent le montant en €
    de la transaction par tender. Permet un tableau croisé immédiat.
    """
    from sqlalchemy.orm import selectinload

    from app.models.pos import Transaction

    stmt = _apply_tx_filters(
        select(Transaction).order_by(Transaction.created_at.asc()),
        period_from=period_from, period_to=period_to, transaction_type=transaction_type,
        method=method, cashier_id=cashier_id, min_amount=min_amount,
        max_amount=max_amount, is_invoice=is_invoice,
    ).options(selectinload(Transaction.items))
    txns = (await db.execute(stmt)).scalars().all()
    rows = []
    for t in txns:
        date_str = t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else ""
        ref = _ticket_ref(t)
        ttype = t.transaction_type.value
        mix, per_method, other = _payment_breakdown(t.payments)
        per_method_cols = [
            f"{per_method.get(k, 0.0):.2f}" if k in per_method else ""
            for k, _ in _METHOD_LABELS_FR
        ]
        for it in (t.items or []):
            rows.append([
                date_str, ref, ttype,
                it.product_name or "",
                it.quantity,
                f"{float(it.unit_price):.2f}",
                f"{float(it.discount_percent or 0):.0f}",
                f"{float(it.line_total):.2f}",
                f"{float(it.tva_rate or 0):.1f}",
                mix,
                *per_method_cols,
                f"{other:.2f}" if other else "",
            ])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    header = [
        "Date", "Ticket", "Type", "Article", "Qté", "PU", "Remise %", "Total ligne", "TVA %",
        "Paiements (mix)",
        *(f"Paiement {lbl} (€)" for _, lbl in _METHOD_LABELS_FR),
        "Paiement Autre (€)",
    ]
    return _csv_response(
        rows,
        header,
        f"vintiz_transactions_detail_{stamp}.csv",
    )


@router.get("/payment-attempts", dependencies=[Depends(manager_only)])
async def list_admin_payment_attempts(
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(None, alias="status"),
    method: str | None = None,
    period_from: str | None = Query(None, alias="from"),
    period_to: str | None = Query(None, alias="to"),
    cashier_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
):
    """List payment attempts — defaults to ``status=failed`` so the
    /admin/payment-attempts page is a debug surface for declined CB.

    Tip: aggregate by ``error_detail`` client-side to surface the top-N CB
    failures (terminal offline, card rejected, network…).
    """
    from app.models.payment_attempt import (
        PaymentAttempt,
        PaymentAttemptStatus,
    )
    from app.models.pos import PaymentMethod

    stmt = select(PaymentAttempt).order_by(PaymentAttempt.created_at.desc())
    if status_filter:
        try:
            stmt = stmt.where(
                PaymentAttempt.status == PaymentAttemptStatus(status_filter)
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="status must be pending | succeeded | failed | cancelled",
            )
    if method:
        try:
            stmt = stmt.where(PaymentAttempt.method == PaymentMethod(method))
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid method")
    if period_from:
        stmt = stmt.where(
            PaymentAttempt.created_at >= _parse_iso_date(period_from, "from")
        )
    if period_to:
        stmt = stmt.where(
            PaymentAttempt.created_at <= _parse_iso_date(period_to, "to")
        )
    if cashier_id is not None:
        stmt = stmt.where(PaymentAttempt.cashier_id == cashier_id)

    stmt = stmt.offset(max(skip, 0)).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "attempts": [
            {
                "id": str(a.id),
                "method": a.method.value,
                "amount": float(a.amount),
                "status": a.status.value,
                "transaction_id": (
                    str(a.transaction_id) if a.transaction_id else None
                ),
                "drawer_id": str(a.drawer_id) if a.drawer_id else None,
                "cashier_id": str(a.cashier_id) if a.cashier_id else None,
                "sumup_checkout_id": a.sumup_checkout_id,
                "sumup_transaction_id": a.sumup_transaction_id,
                "sumup_transaction_code": a.sumup_transaction_code,
                "sumup_auth_code": a.sumup_auth_code,
                "sumup_card_brand": a.sumup_card_brand,
                "sumup_card_last4": a.sumup_card_last4,
                "error_detail": a.error_detail,
                "cancelled_reason": a.cancelled_reason,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            }
            for a in rows
        ],
        "count": len(rows),
    }


@router.get("/payment-failures", dependencies=[Depends(manager_only)])
async def analyze_payment_failures(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
):
    """Analyse des échecs de paiement CB sur les ``days`` derniers jours.

    Croise deux sources pour trouver les causes racines de « les paiements ne
    passent plus » :

    - ``payment_attempts`` (status=failed) → l'échec vu côté caisse, agrégé
      par ``error_detail`` pour le top-N des causes.
    - ``sumup_exchanges`` (is_error) → l'échec vu sur le fil HTTP, agrégé par
      ``error_type`` (READER_OFFLINE, http_500, ConnectError…), avec le nombre
      d'appels qui ont dû être rejoués (``retry_count`` cumulé).

    Manager only. Read-only.
    """
    from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus
    from app.models.sumup_exchange import SumUpExchange

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    failed_where = (
        PaymentAttempt.status == PaymentAttemptStatus.failed,
        PaymentAttempt.created_at >= cutoff,
    )

    total_failed = (
        await db.execute(
            select(func.count(PaymentAttempt.id)).where(*failed_where)
        )
    ).scalar_one()

    rows = (
        await db.execute(
            select(PaymentAttempt)
            .where(*failed_where)
            .order_by(PaymentAttempt.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    # Top causes as seen at the till (grouped by the redacted error_detail).
    error_stats = (
        await db.execute(
            select(
                PaymentAttempt.error_detail,
                func.count(PaymentAttempt.id).label("count"),
            )
            .where(*failed_where)
            .group_by(PaymentAttempt.error_detail)
            .order_by(func.count(PaymentAttempt.id).desc())
        )
    ).all()

    # Top causes as seen on the wire (classified error_type + retries).
    exchange_stats = (
        await db.execute(
            select(
                SumUpExchange.error_type,
                func.count(SumUpExchange.id).label("count"),
                func.coalesce(func.sum(SumUpExchange.retry_count), 0).label("retries"),
            )
            .where(
                SumUpExchange.is_error.is_(True),
                SumUpExchange.created_at >= cutoff,
            )
            .group_by(SumUpExchange.error_type)
            .order_by(func.count(SumUpExchange.id).desc())
        )
    ).all()

    return {
        "time_range_days": days,
        "total_failed_attempts": int(total_failed or 0),
        "failures": [
            {
                "id": str(a.id),
                "amount": float(a.amount),
                "method": a.method.value,
                "error_detail": a.error_detail,
                "sumup_checkout_id": a.sumup_checkout_id,
                "cashier_id": str(a.cashier_id) if a.cashier_id else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ],
        "error_stats": [
            {"error": e[0], "count": int(e[1])} for e in error_stats
        ],
        "sumup_error_types": [
            {
                "error_type": e[0],
                "count": int(e[1]),
                "total_retries": int(e[2] or 0),
            }
            for e in exchange_stats
        ],
    }


@router.get("/failed-payments", dependencies=[Depends(manager_only)])
async def list_failed_payments(
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
):
    """File des paiements CB échoués en attente de réessai (offline groundwork).

    ``status`` : pending | succeeded | exhausted | abandoned. Manager only.
    """
    from app.models.failed_payment import FailedPaymentStatus
    from app.services.failed_payment_service import FailedPaymentService

    try:
        status_enum = FailedPaymentStatus(status_filter) if status_filter else None
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="status must be pending | succeeded | exhausted | abandoned",
        )

    rows = await FailedPaymentService().get_failed_payments(
        db, status=status_enum, limit=limit
    )
    return {
        "failed_payments": [
            {
                "id": str(fp.id),
                "amount": float(fp.amount),
                "currency": fp.currency,
                "status": fp.status.value,
                "checkout_reference": fp.checkout_reference,
                "attempt_count": fp.attempt_count,
                "max_attempts": fp.max_attempts,
                "next_retry_at": (
                    fp.next_retry_at.isoformat() if fp.next_retry_at else None
                ),
                "last_attempt_at": (
                    fp.last_attempt_at.isoformat() if fp.last_attempt_at else None
                ),
                "error_detail": fp.error_detail,
                "resolved_checkout_id": fp.resolved_checkout_id,
                "is_recoverable": fp.is_recoverable,
                "created_at": fp.created_at.isoformat() if fp.created_at else None,
            }
            for fp in rows
        ],
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# SumUp exchange log — server-side trace of every HTTP call to SumUp
# ---------------------------------------------------------------------------


@router.get("/sumup-exchanges", dependencies=[Depends(manager_only)])
async def list_sumup_exchanges(
    db: Annotated[AsyncSession, Depends(get_db)],
    only_failed: bool = Query(False),
    operation: str | None = None,
    error_type: str | None = None,
    checkout_id: str | None = None,
    period_from: str | None = Query(None, alias="from"),
    period_to: str | None = Query(None, alias="to"),
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
):
    """Journal des échanges HTTP avec les serveurs SumUp (manager only).

    Source de vérité côté serveur pour diagnostiquer les paiements CB : chaque
    appel à ``api.sumup.com`` (création checkout, push TPE, statut, annulation,
    remboursement, ping) y est tracé — payload **rédigé** (aucun secret, PAN ou
    CVV). Indices : ``only_failed=true`` isole les échecs (via l'index
    ``is_error``) ; ``error_type=READER_OFFLINE`` cible une cause précise ; une
    ligne ``operation=create_checkout`` avec ``mode=checkout`` = paiement créé
    en lien (le TPE Solo n'a PAS sonné), cause typique de « ça ne passe plus ».
    """
    from app.models.sumup_exchange import SumUpExchange

    stmt = select(SumUpExchange).order_by(SumUpExchange.created_at.desc())
    if only_failed:
        stmt = stmt.where(SumUpExchange.is_error.is_(True))
    if operation:
        stmt = stmt.where(SumUpExchange.operation == operation)
    if error_type:
        stmt = stmt.where(SumUpExchange.error_type == error_type)
    if checkout_id:
        stmt = stmt.where(SumUpExchange.checkout_id == checkout_id)
    if period_from:
        stmt = stmt.where(
            SumUpExchange.created_at >= _parse_iso_date(period_from, "from")
        )
    if period_to:
        stmt = stmt.where(
            SumUpExchange.created_at <= _parse_iso_date(period_to, "to")
        )
    stmt = stmt.offset(max(skip, 0)).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    # Headline diagnostic so the UI can flag the problem at a glance: a CB
    # checkout that resolved to a payment LINK never rings the terminal.
    link_checkouts = sum(
        1 for r in rows if r.operation == "create_checkout" and r.mode == "checkout"
    )
    reader_pushes = sum(1 for r in rows if r.operation == "reader_push")
    failures = sum(1 for r in rows if not r.ok)

    return {
        "exchanges": [
            {
                "id": str(r.id),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "operation": r.operation,
                "method": r.method,
                "url": r.url,
                "http_status": r.http_status,
                "ok": bool(r.ok),
                "is_error": bool(r.is_error),
                "error_type": r.error_type,
                "retry_count": r.retry_count,
                "latency_ms": r.latency_ms,
                "mode": r.mode,
                "checkout_id": r.checkout_id,
                "reader_id": r.reader_id,
                "foreign_transaction_id": r.foreign_transaction_id,
                "request_summary": r.request_summary,
                "response_summary": r.response_summary,
                "error": r.error,
                "environment": r.environment,
            }
            for r in rows
        ],
        "count": len(rows),
        "summary": {
            "reader_pushes": reader_pushes,
            "link_checkouts": link_checkouts,
            "failures": failures,
        },
    }


@router.delete("/sumup-exchanges", dependencies=[Depends(manager_only)])
async def clear_sumup_exchanges(db: Annotated[AsyncSession, Depends(get_db)]):
    """Vider le journal des échanges SumUp (debug — pas un registre fiscal)."""
    from sqlalchemy import delete as sa_delete

    from app.models.sumup_exchange import SumUpExchange

    result = await db.execute(sa_delete(SumUpExchange))
    await db.flush()
    return {"cleared": result.rowcount or 0}


# ---------------------------------------------------------------------------
# Cash management config — defaults consumed by POS Open/Close modals
# ---------------------------------------------------------------------------


class CashManagementConfigUpdate(BaseModel):
    allowed_discrepancy_eur: float | None = None
    default_detail_mode: bool | None = None
    comptable_email: str | None = None


@router.get("/cash-management/config", dependencies=[Depends(manager_only)])
async def get_cash_management_config():
    """Read defaults for the POS open/close modals (tolerance, mode, email)."""
    from app.services.app_config import get_section

    return get_section("cash_management")


@router.put("/cash-management/config", dependencies=[Depends(manager_only)])
async def update_cash_management_config(payload: CashManagementConfigUpdate):
    """Update cash management defaults. Empty strings clear the field."""
    from app.services.app_config import get_section, update_section

    values = payload.model_dump(exclude_none=True)
    tol = values.get("allowed_discrepancy_eur")
    if tol is not None and (tol < 0 or tol > 1000):
        raise HTTPException(
            status_code=400,
            detail="allowed_discrepancy_eur doit être entre 0 et 1000 €",
        )
    update_section("cash_management", values)
    return get_section("cash_management")


# ---------------------------------------------------------------------------
# POS quick-add config — default reusable-bag label + price
# ---------------------------------------------------------------------------


class PosBagInput(BaseModel):
    label: str
    price_eur: float


class PosConfigUpdate(BaseModel):
    bag_label: str | None = None
    bag_default_price_eur: float | None = None
    # Multi-bag : remplace le sac unique par une liste (Sac Kraft, Grand Sac
    # Kraft…). ``None`` = ne pas toucher à la liste persistée ; ``[]`` = revenir
    # au mode legacy (mirror unique).
    bags: list[PosBagInput] | None = None


_MAX_BAGS = 10


@router.get("/pos-config")
async def get_pos_config(current_user: Annotated[User, Depends(get_current_user)]):
    """Read POS quick-add defaults (bags + legacy label/price mirror).

    Readable by any authenticated back-office user so the till can pre-fill
    its « Sac » buttons even when the operator is not a manager.
    """
    from app.services.app_config import get_section, resolved_pos_bags

    section = get_section("pos")
    # Always return ``bags`` as the resolved (non-empty when possible) list so
    # the till has a single source of truth — old configs without a list still
    # see a synthesised single bag from the legacy fields.
    section["bags"] = resolved_pos_bags(section)
    return section


@router.put("/pos-config", dependencies=[Depends(manager_only)])
async def update_pos_config(payload: PosConfigUpdate):
    """Update POS quick-add defaults (manager only)."""
    from app.services.app_config import get_section, resolved_pos_bags, update_section

    values: dict = payload.model_dump(exclude_none=True)

    price = values.get("bag_default_price_eur")
    if price is not None and (price < 0 or price > 1000):
        raise HTTPException(
            status_code=400,
            detail="bag_default_price_eur doit être entre 0 et 1000 €",
        )
    if "bag_label" in values and not str(values["bag_label"]).strip():
        values.pop("bag_label")

    if "bags" in values:
        raw_bags = values["bags"]
        if len(raw_bags) > _MAX_BAGS:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {_MAX_BAGS} sacs supportés au POS.",
            )
        cleaned: list[dict] = []
        for idx, entry in enumerate(raw_bags):
            label = str(entry.get("label") or "").strip()
            if not label:
                raise HTTPException(
                    status_code=400,
                    detail=f"Sac #{idx + 1} : libellé requis.",
                )
            try:
                eur = float(entry.get("price_eur") or 0)
            except (TypeError, ValueError):
                eur = -1.0
            if eur < 0 or eur > 1000:
                raise HTTPException(
                    status_code=400,
                    detail=f"Sac « {label} » : prix doit être entre 0 et 1000 €.",
                )
            cleaned.append({"label": label, "price_eur": round(eur, 2)})
        values["bags"] = cleaned
        # Mirror onto the legacy fields so old consumers (POS pre-list, ticket
        # studio sample) still pre-fill with the first bag.
        if cleaned:
            values.setdefault("bag_label", cleaned[0]["label"])
            values.setdefault("bag_default_price_eur", cleaned[0]["price_eur"])

    update_section("pos", values)
    section = get_section("pos")
    section["bags"] = resolved_pos_bags(section)
    return section


# ---------------------------------------------------------------------------
# Cash drawer sessions — admin overview (/admin > Sessions caisses)
# ---------------------------------------------------------------------------


@router.get("/cash-reporting/monthly", dependencies=[Depends(manager_only)])
async def cash_reporting_monthly(
    db: Annotated[AsyncSession, Depends(get_db)],
    year: int = Query(..., ge=2024, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    """Agrégat mensuel des flux espèces — anticipation COSI TRACFIN.

    Retourne sales/refunds/deposits/inflow/net + alerte si dépassement
    du seuil 10 000 € (CMF L.561-15-1, déclaration banque automatique).

    Audit C11 — pré-requis dossier permanent banque + traçabilité Vintiz.
    """
    from app.services.cash_reporting import cash_volume_for_month

    return await cash_volume_for_month(db, year=year, month=month)


@router.get("/cash-reporting/last-12", dependencies=[Depends(manager_only)])
async def cash_reporting_last_12_months(
    db: Annotated[AsyncSession, Depends(get_db)],
    n_months: int = Query(12, ge=1, le=36),
):
    """12 derniers mois (ou n_months) — pour graphique évolution.

    Utile pour repérer la saisonnalité et anticiper les mois à risque
    de dépassement COSI.
    """
    from app.services.cash_reporting import cash_volume_last_n_months

    return await cash_volume_last_n_months(db, n_months=n_months)


@router.get("/embeddings/cleanup/preview", dependencies=[Depends(manager_only)])
async def embeddings_cleanup_preview(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Dry-run cleanup des taste profiles inactifs ≥ 24 mois (audit C12).

    Retourne candidate_count + cutoff sans rien supprimer — permet de
    contrôler avant un trigger manuel hors-cron.
    """
    from app.services.embeddings_cleanup import purge_inactive_taste_profiles

    return await purge_inactive_taste_profiles(db, dry_run=True)


@router.post("/embeddings/cleanup/run", dependencies=[Depends(manager_only)])
async def embeddings_cleanup_run(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Trigger manuel du cron mensuel de purge taste profiles (audit C12).

    Le cron tourne le 2 de chaque mois à 02:30 ; cet endpoint est utile
    pour un cleanup ponctuel après un afflux exceptionnel d'inactifs
    (migration, opération marketing).
    """
    from app.services.embeddings_cleanup import (
        purge_inactive_taste_profiles,
        purge_orphan_taste_profiles,
    )

    inactive = await purge_inactive_taste_profiles(db, dry_run=False)
    orphans = await purge_orphan_taste_profiles(db)
    await db.commit()
    return {**inactive, "orphans_deleted": orphans}


@router.get("/cash-drawers", dependencies=[Depends(manager_only)])
async def list_cash_drawer_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=500),
):
    """List recent cash-drawer sessions (open + closed), most recent first.

    Each row exposes the data needed by the admin dashboard:
    opening / closing amounts, expected total, difference (= closing - expected)
    and an ``is_open`` flag.
    """
    from app.models.pos import CashDrawer

    stmt = (
        select(CashDrawer)
        .order_by(CashDrawer.opened_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    out: list[dict] = []
    for d in rows:
        opening = float(d.opening_amount or 0)
        closing = float(d.closing_amount) if d.closing_amount is not None else None
        expected = float(d.expected_amount) if d.expected_amount is not None else None
        difference = (closing - expected) if (closing is not None and expected is not None) else None
        out.append(
            {
                "id": str(d.id),
                "opened_at": d.opened_at.isoformat() if d.opened_at else None,
                "closed_at": d.closed_at.isoformat() if d.closed_at else None,
                "opening_amount": opening,
                "closing_amount": closing,
                "expected_amount": expected,
                "difference": round(difference, 2) if difference is not None else None,
                "is_open": bool(d.is_open),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Shop info — editable boutique metadata persisted in data/app_config.json
# ---------------------------------------------------------------------------


class ShopInfoUpdate(BaseModel):
    name: str | None = None
    tagline: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    hours: str | None = None
    surface_m2: int | float | None = None
    vat_rate_percent: int | float | None = None
    siret: str | None = None
    rcs: str | None = None
    ape: str | None = None
    legal_form: str | None = None
    capital_social: str | None = None
    tva_intracom: str | None = None
    iban: str | None = None
    bic: str | None = None
    print_logo_on_ticket: bool | None = None


@router.get("/shop-info")
async def get_shop_info(current_user: Annotated[User, Depends(get_current_user)]):
    """Return the editable boutique info (name, address, hours…)."""
    from app.services.app_config import get_section

    return get_section("shop_info")


@router.put("/shop-info", dependencies=[Depends(manager_only)])
async def update_shop_info(payload: ShopInfoUpdate):
    """Persist boutique info changes (manager only)."""
    from app.services.app_config import update_section

    values = payload.model_dump(exclude_none=True)
    return update_section("shop_info", values)


# ---------------------------------------------------------------------------
# Feature toggles — activer/désactiver des modules (zonage…)
# ---------------------------------------------------------------------------


class FeaturesUpdate(BaseModel):
    zoning_enabled: bool | None = None


@router.get("/features")
async def get_features_endpoint(current_user: Annotated[User, Depends(get_current_user)]):
    """Read feature toggles. Readable by any authenticated back-office user so
    the POS / intake screens can react (e.g. hide the zone step) — not just the
    manager."""
    from app.services.feature_flags import get_features

    return get_features()


@router.put("/features", dependencies=[Depends(manager_only)])
async def update_features_endpoint(payload: FeaturesUpdate):
    """Toggle features (manager only). For now: ``zoning_enabled``."""
    from app.services.feature_flags import get_features, set_zoning_enabled

    if payload.zoning_enabled is not None:
        return set_zoning_enabled(payload.zoning_enabled)
    return get_features()


# ---------------------------------------------------------------------------
# Installation / paramétrage boutique (chaîne d'installation — voir
# docs/MULTI_STORE.md). Config-only : pilote l'assistant /setup.
# ---------------------------------------------------------------------------


class InstallationUpdate(BaseModel):
    installed: bool | None = None
    complete_step: str | None = None  # marque une étape comme faite
    reset: bool | None = None         # rouvre l'installation


_SETUP_STEPS = [
    ("identity", "Identité & localisation"),
    ("fiscal", "Fiscalité (TVA)"),
    ("zoning", "Organisation boutique (zonage)"),
    ("hardware", "Matériel (encaissement, imprimantes, étiquettes)"),
    ("users", "Utilisateurs & droits"),
]


def _installation_state() -> dict:
    from app.services.app_config import get_section

    inst = get_section("installation")
    shop = get_section("shop_info")
    completed = set(inst.get("completed_steps") or [])
    identity_done = bool((shop.get("name") or "").strip() and (shop.get("city") or "").strip())
    checklist = []
    for key, label in _SETUP_STEPS:
        done = identity_done if key == "identity" else key in completed
        checklist.append({"key": key, "label": label, "done": done})
    return {
        "installed": bool(inst.get("installed")),
        "installed_at": inst.get("installed_at") or "",
        "completed_steps": sorted(completed | ({"identity"} if identity_done else set())),
        "checklist": checklist,
        "all_done": all(c["done"] for c in checklist),
    }


@router.get("/installation")
async def get_installation(current_user: Annotated[User, Depends(get_current_user)]):
    """Statut d'installation + checklist (lisible par tout back-office pour le
    bandeau « installation à terminer »)."""
    return _installation_state()


@router.put("/installation", dependencies=[Depends(manager_only)])
async def update_installation(payload: InstallationUpdate):
    """Avancer/terminer l'installation (manager only)."""
    from datetime import datetime, timezone

    from app.services.app_config import get_section, update_section

    inst = get_section("installation")
    completed = set(inst.get("completed_steps") or [])
    values: dict = {}

    if payload.reset:
        values = {"installed": False, "installed_at": "", "completed_steps": []}
        update_section("installation", values)
        return _installation_state()

    valid_keys = {k for k, _ in _SETUP_STEPS}
    if payload.complete_step:
        if payload.complete_step not in valid_keys:
            raise HTTPException(status_code=400, detail="Étape inconnue")
        completed.add(payload.complete_step)
        values["completed_steps"] = sorted(completed)

    if payload.installed is not None:
        values["installed"] = payload.installed
        values["installed_at"] = (
            datetime.now(timezone.utc).isoformat() if payload.installed else ""
        )

    if values:
        update_section("installation", values)
    return _installation_state()


# ---------------------------------------------------------------------------
# Company logo — uploaded asset rendered on invoices (and opt-in on tickets)
# ---------------------------------------------------------------------------

_BRANDING_DIR = Path(
    os.getenv(
        "VINTIZ_BRANDING_DIR",
        str(Path(__file__).resolve().parents[3] / "data" / "branding"),
    )
)
_LOGO_FILE = _BRANDING_DIR / "logo.png"


@router.get("/branding/logo")
async def get_branding_logo(current_user: Annotated[User, Depends(get_current_user)]):
    """Serve the current company logo PNG (for the studio preview)."""
    if not _LOGO_FILE.exists():
        raise HTTPException(status_code=404, detail="Aucun logo configuré")
    return Response(content=_LOGO_FILE.read_bytes(), media_type="image/png")


@router.post("/branding/logo", dependencies=[Depends(manager_only)])
async def upload_branding_logo(file: UploadFile = File(...)):
    """Upload the company logo. Normalised to PNG, max 600px wide, and the
    absolute path is persisted in ``shop_info.logo_path``."""
    from app.services.app_config import update_section

    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo trop lourd (max 5 Mo).")
    try:
        from io import BytesIO

        from PIL import Image

        im = Image.open(BytesIO(raw)).convert("RGBA")
        if im.width > 600:
            ratio = 600 / im.width
            im = im.resize((600, int(im.height * ratio)), Image.LANCZOS)
        _BRANDING_DIR.mkdir(parents=True, exist_ok=True)
        im.save(_LOGO_FILE, format="PNG")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Image invalide : {exc}"
        ) from exc

    update_section("shop_info", {"logo_path": str(_LOGO_FILE)})
    return {"ok": True, "logo_path": str(_LOGO_FILE)}


@router.delete("/branding/logo", dependencies=[Depends(manager_only)])
async def delete_branding_logo():
    """Remove the company logo and clear ``shop_info.logo_path``."""
    from app.services.app_config import update_section

    if _LOGO_FILE.exists():
        try:
            _LOGO_FILE.unlink()
        except OSError:
            pass
    update_section("shop_info", {"logo_path": "", "print_logo_on_ticket": False})
    return {"ok": True}


# ---------------------------------------------------------------------------
# SumUp config — editable credentials persisted in data/app_config.json
# Persisted values take precedence over env vars in SumUpService.
# ---------------------------------------------------------------------------


class SumUpConfigUpdate(BaseModel):
    api_key: str | None = None
    merchant_code: str | None = None
    reader_id: str | None = None
    return_url: str | None = None
    # Affiliate (developer) keys — required for the reader push to carry
    # affiliate.foreign_transaction_id (reconciliation / refund lookup).
    # Without them the reader checkout still works but can't be looked up
    # by foreign id. https://developer.sumup.com/affiliate-keys
    affiliate_app_id: str | None = None
    affiliate_key: str | None = None


@router.get("/sumup-config", dependencies=[Depends(manager_only)])
async def get_sumup_config():
    """Return SumUp credentials state (masked) + the live SumUpService snapshot.

    Production-only — le mode sandbox/simulation a été retiré.
    """
    from app.services.app_config import get_section, mask_secret
    from app.services.sumup_service import SumUpService

    persisted = get_section("sumup")
    live = SumUpService().describe()
    return {
        "live": live,
        "persisted": {
            "api_key_masked": mask_secret(persisted.get("api_key", "")),
            "merchant_code_masked": mask_secret(persisted.get("merchant_code", "")),
            "reader_id_masked": mask_secret(persisted.get("reader_id", "")),
            "return_url": persisted.get("return_url", ""),
            "affiliate_app_id_masked": mask_secret(persisted.get("affiliate_app_id", "")),
            "affiliate_key_masked": mask_secret(persisted.get("affiliate_key", "")),
        },
    }


@router.put("/sumup-config", dependencies=[Depends(manager_only)])
async def update_sumup_config(payload: SumUpConfigUpdate):
    """Persist SumUp credentials. Empty strings clear the override (env var fallback).

    Production-only — il n'y a plus de mode sandbox/simulation. Si la clé
    API n'est pas configurée, les checkouts CB retournent FAILED avec un
    message explicite plutôt que de simuler un paiement.
    """
    from app.services.app_config import update_section, get_section

    values = payload.model_dump(exclude_none=True)

    update_section("sumup", values)
    # Re-evaluate the service to reflect the change immediately in the UI.
    from app.services.sumup_service import SumUpService
    live = SumUpService().describe()
    persisted = get_section("sumup")
    from app.services.app_config import mask_secret
    return {
        "live": live,
        "persisted": {
            "api_key_masked": mask_secret(persisted.get("api_key", "")),
            "merchant_code_masked": mask_secret(persisted.get("merchant_code", "")),
            "reader_id_masked": mask_secret(persisted.get("reader_id", "")),
            "return_url": persisted.get("return_url", ""),
            "affiliate_app_id_masked": mask_secret(persisted.get("affiliate_app_id", "")),
            "affiliate_key_masked": mask_secret(persisted.get("affiliate_key", "")),
        },
    }


# ---------------------------------------------------------------------------
# Curation picks — manager-curated selection surfaced on /account/selection
# ---------------------------------------------------------------------------


class CurationPickItem(BaseModel):
    product_id: str
    reason: str | None = None


class CurationPicksUpdate(BaseModel):
    items: list[CurationPickItem]
    curator_note: str | None = None


@router.get("/curation-picks", dependencies=[Depends(manager_only)])
async def get_curation_picks():
    """Return the persisted curator selection (max 12 product IDs + a note)."""
    from app.services.app_config import get_section
    return get_section("curation_picks")


@router.put("/curation-picks", dependencies=[Depends(manager_only)])
async def update_curation_picks(payload: CurationPicksUpdate):
    """Persist the curator selection. Capped at 12 picks."""
    from app.services.app_config import update_section
    from datetime import datetime as _dt, timezone as _tz

    if len(payload.items) > 12:
        raise HTTPException(status_code=400, detail="Maximum 12 sélections")
    items = [{"product_id": i.product_id, "reason": i.reason or ""} for i in payload.items]
    return update_section(
        "curation_picks",
        {
            "items": items,
            "curator_note": payload.curator_note or "",
            "updated_at": _dt.now(_tz.utc).isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Email gateway config — editable Brevo / SMTP / simulation overrides
# Persisted values prevail over environment variables.
# ---------------------------------------------------------------------------


class EmailConfigUpdate(BaseModel):
    provider: str | None = None  # "" | auto | brevo | smtp | simulation
    brevo_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: str | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    from_address: str | None = None
    from_name: str | None = None


@router.get("/email-config", dependencies=[Depends(manager_only)])
async def get_email_config():
    """Return masked email config + the live provider currently in use."""
    from app.services.app_config import get_section, mask_secret
    from app.services.email_gateway import describe_active_provider

    persisted = get_section("email")
    return {
        "live": describe_active_provider(),
        "persisted": {
            "provider": persisted.get("provider", ""),
            "brevo_api_key_masked": mask_secret(persisted.get("brevo_api_key", "")),
            "smtp_host": persisted.get("smtp_host", ""),
            "smtp_port": persisted.get("smtp_port", "587"),
            "smtp_user": persisted.get("smtp_user", ""),
            "smtp_password_masked": mask_secret(persisted.get("smtp_password", "")),
            "smtp_from": persisted.get("smtp_from", ""),
            "from_address": persisted.get("from_address", "noreply@vintiz.fr"),
            "from_name": persisted.get("from_name", "Vintiz Vernon"),
        },
    }


@router.put("/email-config", dependencies=[Depends(manager_only)])
async def update_email_config(payload: EmailConfigUpdate):
    """Persist Brevo/SMTP credentials. Empty strings preserve the current value
    (except `provider`, which is always written).
    """
    from app.services.app_config import update_section, get_section, mask_secret
    from app.services.email_gateway import describe_active_provider

    raw = payload.model_dump(exclude_none=True)
    # Drop empty strings except for "provider" (which can be reset)
    values = {
        k: v for k, v in raw.items() if k == "provider" or v not in (None, "")
    }
    update_section("email", values)
    persisted = get_section("email")
    return {
        "live": describe_active_provider(),
        "persisted": {
            "provider": persisted.get("provider", ""),
            "brevo_api_key_masked": mask_secret(persisted.get("brevo_api_key", "")),
            "smtp_host": persisted.get("smtp_host", ""),
            "smtp_port": persisted.get("smtp_port", "587"),
            "smtp_user": persisted.get("smtp_user", ""),
            "smtp_password_masked": mask_secret(persisted.get("smtp_password", "")),
            "smtp_from": persisted.get("smtp_from", ""),
            "from_address": persisted.get("from_address", "noreply@vintiz.fr"),
            "from_name": persisted.get("from_name", "Vintiz Vernon"),
        },
    }


class EmailTestRequest(BaseModel):
    to: str | None = None  # default = current admin email


@router.post("/email-config/test", dependencies=[Depends(manager_only)])
async def send_email_test(
    payload: EmailTestRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Send a real test email to verify the active provider end-to-end.

    Returns the EmailResult so the UI can display backend, status and detail.
    """
    from app.services.email_gateway import EmailMessage, send_email, EmailDeliveryError

    target = (payload.to or current_user.email or "").strip()
    if not target:
        raise HTTPException(
            status_code=400,
            detail="Adresse email cible manquante (et utilisateur sans email)",
        )

    msg = EmailMessage(
        to=target,
        subject="Test Vintiz — passerelle email",
        html=(
            "<p>Bonjour,</p>"
            "<p>Cet email confirme que la configuration de la passerelle email "
            "Vintiz fonctionne correctement.</p>"
            "<p>Si vous le recevez : Brevo / SMTP est bien câblé.</p>"
            "<p>— Vintiz Vernon</p>"
        ),
        text="Test Vintiz : la passerelle email fonctionne.",
    )
    try:
        result = send_email(msg)
        return {
            "ok": True,
            "status": result.status,
            "backend": result.backend,
            "message_id": result.message_id,
            "sent_at": result.sent_at,
            "to": target,
        }
    except EmailDeliveryError as exc:
        return {
            "ok": False,
            "status": "failed",
            "backend": "error",
            "detail": str(exc),
            "to": target,
        }


# ---------------------------------------------------------------------------
# SMS gateway — status + test endpoint
# ---------------------------------------------------------------------------


@router.get("/sms-config", dependencies=[Depends(manager_only)])
async def get_sms_config():
    """Retourne le provider SMS actif + sender ID + sonde compte Brevo.

    Brevo (recommandé) partage la clé API avec l'email gateway ; aucun
    secret SMS dédié à poser. Twilio reste un fallback legacy.

    ``account`` = sonde GET /v3/account avec la clé configurée : révèle le
    compte réellement ciblé par la clé + son solde de crédits SMS. Permet de
    diagnostiquer le « 402 not_enough_credits alors que j'ai des crédits »
    (= la clé pointe vers un autre compte Brevo que celui visible à l'écran).
    """
    from app.services.sms_gateway import brevo_account_probe, describe_active_provider

    live = describe_active_provider()
    out = {"live": live}
    if live.get("provider") == "brevo":
        out["account"] = brevo_account_probe()
    return out


class SmsTestRequest(BaseModel):
    to: str  # E.164 ou national FR — la passerelle normalise


@router.post("/sms-config/test", dependencies=[Depends(manager_only)])
async def send_sms_test(payload: SmsTestRequest):
    """Envoie un vrai SMS de test pour vérifier la passerelle de bout en bout.

    Surface explicitement le code/détail d'erreur Brevo dans la réponse
    (« Sender not registered », « SMS credit insufficient », « invalid
    recipient »…) pour que le manager puisse réagir directement depuis
    /settings > Communication, sans aller dans les logs.
    """
    from app.services.sms_gateway import (
        SMSDeliveryError,
        SMSMessage,
        normalise_phone_e164,
        send_sms,
    )

    raw_to = (payload.to or "").strip()
    if not raw_to:
        raise HTTPException(status_code=400, detail="Numéro destinataire manquant")
    to = normalise_phone_e164(raw_to)
    if not to or len(to) < 8:
        raise HTTPException(
            status_code=400,
            detail=f"Numéro invalide après normalisation : '{to}' "
            "(format attendu : +33612345678 ou 06 12 34 56 78).",
        )

    msg = SMSMessage(
        to=to,
        body="Vintiz test : la passerelle SMS est OK.",
    )
    try:
        result = send_sms(msg)
        return {
            "ok": result.status == "sent",
            "status": result.status,
            "backend": result.backend,
            "message_id": result.message_id,
            "sent_at": result.sent_at,
            "to": to,
            "simulated": result.status == "simulated",
        }
    except SMSDeliveryError as exc:
        # On surface l'erreur Brevo telle quelle — le manager voit
        # « Brevo 400: Sender is invalid » ou « Brevo 402: not enough
        # credit » et sait quoi faire (enregistrer le sender, recharger…).
        return {
            "ok": False,
            "status": "failed",
            "backend": "error",
            "detail": str(exc),
            "to": to,
        }


# ---------------------------------------------------------------------------
# Magic-link probe (manager-only) — debug "OTP not arriving"
# ---------------------------------------------------------------------------


class MagicLinkProbeRequest(BaseModel):
    target: str  # email or phone — the same field accepted by the public endpoint


@router.post("/magic-link/probe", dependencies=[Depends(manager_only)])
async def magic_link_probe(
    payload: MagicLinkProbeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Manager-only diagnostic: trigger a real OTP send and report back the
    actual delivery channel/backend/mode. Bypasses the public anti-enumeration
    silence so the manager can see *why* a customer is not receiving codes.

    Possible outcomes for ``delivery_mode``:
      - ``sent``       OTP successfully delivered through the live backend
      - ``simulated``  no real backend configured (Brevo/SMTP/Twilio) — the
                        OTP was only logged, the customer will not receive it
      - ``failed``     backend present but the call itself failed
      - ``skipped``    rate-limit hit, malformed input, etc. (see ``reason``)
    """
    from app.services.magic_link import issue

    target = (payload.target or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="target manquant")
    result = await issue(db, target, ip=None)
    await db.commit()
    return {
        "target": target,
        "delivery_mode": result.get("delivery_mode"),
        "backend": result.get("backend"),
        "channel": result.get("channel"),
        "reason": result.get("reason"),
    }


# ---------------------------------------------------------------------------
# Weather endpoint
# ---------------------------------------------------------------------------

@router.get("/weather")
async def get_weather(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get current weather and forecast for Vernon. Saves snapshot to history."""
    from app.services.weather_service import get_current_weather, get_weather_forecast
    from app.models.audit import Settings

    current, forecast = await asyncio.gather(get_current_weather(), get_weather_forecast())

    # Save weather snapshot to history (stored in Settings as JSON array)
    import json as _json
    from datetime import date as _date

    weather_data = {"current": current, "forecast": forecast}

    try:
        # Load existing history
        history_setting = await db.execute(select(Settings).where(Settings.key == "weather_history"))
        setting = history_setting.scalar_one_or_none()

        today_str = str(_date.today())
        snapshot = {
            "date": today_str,
            "temp": current.get("temp", 0),
            "description": current.get("description", ""),
            "icon": current.get("icon", "01d"),
            "temp_min": current.get("temp_min", current.get("temp", 0)),
            "temp_max": current.get("temp_max", current.get("temp", 0)),
            "humidity": current.get("humidity", 0),
            "wind_speed": current.get("wind_speed", 0),
        }

        if setting:
            history = _json.loads(setting.value or "[]")
            # Update today's snapshot or append
            history = [h for h in history if h.get("date") != today_str]
            history.append(snapshot)
            # Keep last 30 days
            history = sorted(history, key=lambda x: x["date"])[-30:]
            setting.value = _json.dumps(history)
        else:
            db.add(Settings(key="weather_history", value=_json.dumps([snapshot])))

        await db.commit()
    except Exception:
        await db.rollback()  # prevent aborted-transaction state on the session

    return weather_data


@router.get("/weather/history")
async def get_weather_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get historical weather snapshots for Vernon (last 30 days)."""
    import json as _json
    from app.models.audit import Settings

    setting_result = await db.execute(select(Settings).where(Settings.key == "weather_history"))
    setting = setting_result.scalar_one_or_none()

    if not setting or not setting.value:
        return {"history": []}

    try:
        history = _json.loads(setting.value)
        return {"history": history}
    except Exception:
        return {"history": []}


# ---------------------------------------------------------------------------
# Weekly scoring (lundi 04:00 cron + manual trigger)
# ---------------------------------------------------------------------------

@router.post("/scoring/weekly-update")
async def weekly_scoring_update(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Manual trigger of the v3 weekly scoring (same effect as Monday 04:00 cron)."""
    from app.services.brand_tiers import get_brand_score
    from app.services.category_trends import refresh_cache as refresh_trends
    from app.services.category_velocity import refresh_cache as refresh_velocity
    from app.services.market_price_estimator import (
        get_or_refresh_estimate,
        refresh_stale_estimates,
    )
    from app.services.scoring_config import get_scoring_config
    from app.services.scoring_service import compute_score

    config = await get_scoring_config(db)
    category_trends = await refresh_trends(db)
    velocity_by_cat = await refresh_velocity(db)
    n_estimates = await refresh_stale_estimates(db, limit=500)

    result = await db.execute(
        select(Product).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display])
        )
    )
    products = result.scalars().all()
    updated = 0
    for product in products:
        trend = float(category_trends.get(str(product.category_id), 50.0))
        velocity = float(velocity_by_cat.get(str(product.category_id), 0.0))
        brand_score = await get_brand_score(db, product.brand)
        market_estimate = await get_or_refresh_estimate(db, product)
        score_data = compute_score(
            shelf_date=product.shelf_date,
            sale_price=float(product.sale_price),
            market_price_estimate=market_estimate,
            category_name=product.category.name if product.category else None,
            category_trend=trend,
            category_avg_velocity=velocity,
            brand_score=brand_score,
            condition=getattr(product, "condition", None),
            config=config,
        )
        product.trend_score = score_data["total_score"]
        updated += 1

    await db.commit()
    return {
        "updated": updated,
        "market_estimates_refreshed": n_estimates,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"Scores recalcules pour {updated} produits actifs",
    }


# ---------------------------------------------------------------------------
# Audit log inspection (P1-013) — manager only
# ---------------------------------------------------------------------------


@router.get(
    "/audit-logs",
    dependencies=[Depends(manager_only)],
)
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    entity: str | None = None,
    action: str | None = None,
    user_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
):
    """Paginated audit log listing, newest first.

    Optional filters: entity (e.g. "transaction"), action (create/update/delete),
    user_id. Limit capped at 500 to keep responses snappy.
    """
    capped_limit = min(max(limit, 1), 500)
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if entity:
        query = query.where(AuditLog.entity == entity)
    if action:
        query = query.where(AuditLog.action == action)
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    query = query.offset(max(skip, 0)).limit(capped_limit)

    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "id": str(row.id),
            "user_id": str(row.user_id) if row.user_id else None,
            "action": row.action,
            "entity": row.entity,
            "entity_id": str(row.entity_id) if row.entity_id else None,
            "data": row.data,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Fiscal export NF525 / DGFiP (P1-015 — closes P1-001)
# ---------------------------------------------------------------------------


def _parse_iso_date(value: str | None, field: str) -> datetime | None:
    if value is None:
        return None
    try:
        # Accept "YYYY-MM-DD" or full ISO 8601.
        if "T" in value:
            return datetime.fromisoformat(value)
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field}: expected ISO date (YYYY-MM-DD or full ISO 8601)",
        ) from exc


@router.get(
    "/fiscal-export",
    dependencies=[Depends(manager_only)],
)
async def fiscal_export(
    db: Annotated[AsyncSession, Depends(get_db)],
    period_from: str | None = Query(None, alias="from"),
    period_to: str | None = Query(None, alias="to"),
    fmt: str = Query("xml", alias="format", pattern="^(xml|json)$"),
    merchant_name: str = Query("Vintiz Vernon"),
    merchant_id: str = Query(""),
):
    """Build a NF525-compliant fiscal export over the given period.

    Always includes the SHA-256 hash chain so a tax auditor can verify
    no transaction has been altered after the fact. Manager only.
    """
    from app.services.fiscal_export import FiscalExportService

    period_from_dt = _parse_iso_date(period_from, "from")
    period_to_dt = _parse_iso_date(period_to, "to")

    svc = FiscalExportService(db)
    snapshot = await svc.build_snapshot(
        period_from=period_from_dt,
        period_to=period_to_dt,
        merchant_name=merchant_name,
        merchant_id=merchant_id,
    )

    suffix = period_from_dt.date().isoformat() if period_from_dt else "all"
    filename = f"vintiz-fiscal-export-{suffix}.{fmt}"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    if fmt == "json":
        return Response(
            content=svc.to_json(snapshot),
            media_type="application/json",
            headers=headers,
        )
    return Response(
        content=svc.to_xml(snapshot),
        media_type="application/xml",
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Data quality / event store observability (P1-003)
# ---------------------------------------------------------------------------


@router.get(
    "/data-quality",
    dependencies=[Depends(manager_only)],
)
async def data_quality(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 7,
):
    """Surface event-store coverage so silent instrumentation regressions
    (e.g. zero ``product.viewed`` events for a day = JS broke) are spotted.

    Returns counts by event_type over the last ``days`` (default 7) plus
    a daily total. Manager only.
    """
    from app.services.events import EventService

    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    svc = EventService(db)
    by_type = await svc.counts_by_type(since=since)
    daily = await svc.daily_volume(since=since)
    return {
        "since": since.isoformat(),
        "window_days": days,
        "by_event_type": by_type,
        "daily_total": daily,
    }


# ---------------------------------------------------------------------------
# Embeddings recompute (P1-004) — admin trigger, mirrors the daily cron
# ---------------------------------------------------------------------------


class RecomputeRequest(BaseModel):
    only_missing: bool = False


@router.post(
    "/embeddings/recompute",
    dependencies=[Depends(manager_only)],
)
async def recompute_embeddings(
    request: RecomputeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Recompute product embeddings for the catalogue.

    ``only_missing=True`` skips products whose embeddings already match
    the current encoder version — useful for incremental backfill.
    Manager only.
    """
    from app.services.embeddings import EmbeddingService

    summary = await EmbeddingService(db).recompute_all_products(
        only_missing=request.only_missing
    )
    await db.commit()
    return summary


# ---------------------------------------------------------------------------
# Brand tiers (P2-012) — manager-curated DB replacing the hardcoded sets
# ---------------------------------------------------------------------------


class BrandTierRequest(BaseModel):
    name: str
    tier: str  # luxury / premium / mid / basic
    score_override: float | None = None


@router.get("/brand-tiers", dependencies=[Depends(manager_only)])
async def list_brand_tiers(db: Annotated[AsyncSession, Depends(get_db)]):
    from app.models.brand_tier import BRAND_TIER_SCORE, BrandTier

    result = await db.execute(select(BrandTier).order_by(BrandTier.name))
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "tier": r.tier.value,
            "score_override": r.score_override,
            "effective_score": (
                r.score_override
                if r.score_override is not None
                else BRAND_TIER_SCORE[r.tier]
            ),
        }
        for r in result.scalars().all()
    ]


@router.post(
    "/brand-tiers",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(manager_only)],
)
async def create_brand_tier(
    request: BrandTierRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.brand_tier import BrandTier, BrandTierLevel
    from app.services.brand_tiers import invalidate_cache

    try:
        tier = BrandTierLevel(request.tier)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                "tier must be one of: "
                + ", ".join(t.value for t in BrandTierLevel)
            ),
        )
    row = BrandTier(
        name=request.name.strip().lower(),
        tier=tier,
        score_override=request.score_override,
    )
    db.add(row)
    try:
        await db.flush()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail=f"Brand already exists or invalid: {exc}"
        )
    await db.commit()
    invalidate_cache()
    return {"id": str(row.id), "name": row.name}


@router.put(
    "/brand-tiers/{tier_id}",
    dependencies=[Depends(manager_only)],
)
async def update_brand_tier(
    tier_id: uuid.UUID,
    request: BrandTierRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.brand_tier import BrandTier, BrandTierLevel
    from app.services.brand_tiers import invalidate_cache

    result = await db.execute(select(BrandTier).where(BrandTier.id == tier_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Brand tier not found")
    try:
        tier = BrandTierLevel(request.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tier")
    row.name = request.name.strip().lower()
    row.tier = tier
    row.score_override = request.score_override
    await db.flush()
    await db.commit()
    invalidate_cache()
    return {"id": str(row.id), "name": row.name}


@router.delete(
    "/brand-tiers/{tier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(manager_only)],
)
async def delete_brand_tier(
    tier_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.brand_tier import BrandTier
    from app.services.brand_tiers import invalidate_cache

    result = await db.execute(select(BrandTier).where(BrandTier.id == tier_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Brand tier not found")
    await db.delete(row)
    await db.commit()
    invalidate_cache()
    return None


# ---------------------------------------------------------------------------
# Return-to-sorting (P3-007)
# ---------------------------------------------------------------------------


@router.get(
    "/return-to-sorting/preview",
    dependencies=[Depends(manager_only)],
)
async def preview_return_to_sorting(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Dry-run of the return-to-sorting policy — what would be moved if the
    cron ran right now. Useful for reviewing the threshold before flipping
    auto-mode in production."""
    from app.services.return_to_sorting import ReturnToSortingService

    svc = ReturnToSortingService(db)
    candidates = await svc.find_eligible()
    return {
        "policy": svc._policy_dict(),
        "candidate_count": len(candidates),
        "candidates": [
            {
                "id": str(p.id),
                "name": p.name,
                "barcode": p.barcode,
                "status": p.status.value,
                "trend_score": p.trend_score,
                "displayed_at": p.displayed_at.isoformat() if p.displayed_at else None,
                "intake_batch_id": str(p.intake_batch_id) if p.intake_batch_id else None,
            }
            for p in candidates
        ],
    }


# ---------------------------------------------------------------------------
# Store plan + window display (P2-005 + P2-007)
# ---------------------------------------------------------------------------


@router.get(
    "/store-plan",
    dependencies=[Depends(manager_only)],
)
async def store_plan(db: Annotated[AsyncSession, Depends(get_db)]):
    """Return all zones with their canvas coordinates, current occupancy
    and the score-bucket colour code so the front can render the SVG
    plan directly (P2-005). Empty + ``zoning_enabled: false`` when zoning is
    turned off."""
    from app.services.feature_flags import zoning_enabled
    from app.services.merchandising import MerchandisingService

    if not zoning_enabled():
        return {"zoning_enabled": False, "zones": []}

    return {"zoning_enabled": True, "zones": await MerchandisingService(db).zone_occupancy()}


@router.get(
    "/window-display/current",
    dependencies=[Depends(manager_only)],
)
async def get_current_window_display(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return the current ISO week's window-display proposal, or 404 if
    the cron hasn't run yet."""
    from app.services.merchandising import MerchandisingService

    proposal = await MerchandisingService(db).get_current_window_proposal()
    if proposal is None:
        raise HTTPException(
            status_code=404,
            detail="Aucune proposition vitrine pour la semaine en cours.",
        )
    return {
        "id": str(proposal.id),
        "iso_week": proposal.iso_week,
        "proposal": proposal.proposal,
        "used_llm": proposal.used_llm,
        "accepted_at": proposal.accepted_at.isoformat() if proposal.accepted_at else None,
        "accepted_by_user_id": str(proposal.accepted_by_user_id) if proposal.accepted_by_user_id else None,
    }


@router.post(
    "/window-display/regenerate",
    dependencies=[Depends(manager_only)],
)
async def regenerate_window_display(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Force a fresh window-display proposal for the current ISO week.
    Same effect as waiting for the Monday 06:00 cron."""
    from app.services.merchandising import MerchandisingService

    proposal = await MerchandisingService(db).propose_weekly_window()
    await db.commit()
    return {
        "id": str(proposal.id),
        "iso_week": proposal.iso_week,
        "proposal": proposal.proposal,
    }


@router.post(
    "/window-display/{proposal_id}/accept",
    dependencies=[Depends(manager_only)],
)
async def accept_window_display(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    from app.services.merchandising import MerchandisingService

    proposal = await MerchandisingService(db).accept_window_proposal(
        proposal_id, current_user.id
    )
    await db.commit()
    return {
        "id": str(proposal.id),
        "iso_week": proposal.iso_week,
        "accepted_at": proposal.accepted_at.isoformat() if proposal.accepted_at else None,
    }


@router.post(
    "/return-to-sorting/run",
    dependencies=[Depends(manager_only)],
)
async def run_return_to_sorting(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Manually trigger the return-to-sorting cron pass. Same effect as
    waiting for the 02:00 daily run."""
    from app.services.return_to_sorting import ReturnToSortingService

    summary = await ReturnToSortingService(db).run()
    await db.commit()
    return summary


@router.post(
    "/embeddings/customer/{client_id}",
    dependencies=[Depends(manager_only)],
)
async def recompute_taste_profile(
    client_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Refresh one customer's taste centroid (admin tool / debugging)."""
    from app.services.embeddings import EmbeddingService

    profile = await EmbeddingService(db).recompute_taste_profile(client_id)
    if profile is None:
        return {
            "client_id": str(client_id),
            "computed": False,
            "reason": "No analyzable purchases",
        }
    await db.commit()
    return {
        "client_id": str(client_id),
        "computed": True,
        "n_purchases_analyzed": profile.n_purchases_analyzed,
        "algo_version": profile.algo_version,
    }


# ---------------------------------------------------------------------------
# RFM segmentation (P4-007) + retail-KPIs config (P4-001 / P4-002)
# ---------------------------------------------------------------------------


@router.post("/rfm/run", dependencies=[Depends(manager_only)])
async def run_rfm_segmentation(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Manually trigger the RFM scoring + persistence pass. Same effect as
    waiting for the monthly cron (1st of the month at 04:00)."""
    from app.services.rfm import run_segmentation

    summary = await run_segmentation(db)
    await db.commit()
    return summary


@router.post("/qualification/run", dependencies=[Depends(manager_only)])
async def run_customer_qualification(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Manually trigger the customer qualification pass (PS 360 V2).

    Recomputes season_bias / price_ceiling / price_sensitivity / trend_affinity
    for every consenting member with a purchase history. Same effect as the
    nightly pass folded into the 04:00 embedding refresh. Manager only."""
    from app.services.customer_qualification import recompute_all_qualifications

    summary = await recompute_all_qualifications(db)
    await db.commit()
    return summary


# ---------------------------------------------------------------------------
# Message templates (emails / SMS automatiques) — éditables par le manager
# ---------------------------------------------------------------------------


class MessageTemplatePayload(BaseModel):
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    is_active: bool = True


def _template_to_dict(t) -> dict:
    return {
        "id": str(t.id),
        "key": t.key,
        "channel": t.channel.value if hasattr(t.channel, "value") else t.channel,
        "label": t.label,
        "description": t.description,
        "subject": t.subject,
        "body_html": t.body_html,
        "body_text": t.body_text,
        "is_active": bool(t.is_active),
    }


@router.get("/message-templates", dependencies=[Depends(manager_only)])
async def list_message_templates(db: Annotated[AsyncSession, Depends(get_db)]):
    """List the editable automatic-message templates (seeds defaults if empty)."""
    from app.models.communications import MessageTemplate
    from app.services.communications import seed_default_templates

    added = await seed_default_templates(db)
    if added:
        await db.commit()
    rows = await db.execute(select(MessageTemplate).order_by(MessageTemplate.key))
    return [_template_to_dict(t) for t in rows.scalars().all()]


@router.put("/message-templates/{template_id}", dependencies=[Depends(manager_only)])
async def update_message_template(
    template_id: uuid.UUID,
    payload: MessageTemplatePayload,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Edit an automatic-message template (subject / body / active)."""
    from app.models.communications import MessageTemplate

    row = await db.execute(
        select(MessageTemplate).where(MessageTemplate.id == template_id)
    )
    tpl = row.scalar_one_or_none()
    if tpl is None:
        raise HTTPException(status_code=404, detail="Template introuvable")
    tpl.subject = payload.subject
    tpl.body_html = payload.body_html
    tpl.body_text = payload.body_text
    tpl.is_active = payload.is_active
    await db.commit()
    return _template_to_dict(tpl)


class KpiConfigPayload(BaseModel):
    store_surface_m2: float | None = None
    avg_piece_weight_kg: float | None = None
    ess_reversed_pct: float | None = None


@router.get("/kpis-config", dependencies=[Depends(manager_only)])
async def get_kpis_config(db: Annotated[AsyncSession, Depends(get_db)]):
    """Read the retail-KPIs / ESS config (surface, weight, %CA reversé)."""
    from app.services.retail_kpis import _load_config

    return await _load_config(db)


@router.put("/kpis-config", dependencies=[Depends(manager_only)])
async def update_kpis_config(
    payload: KpiConfigPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update one or several retail-KPIs / ESS config knobs."""
    from app.services.retail_kpis import update_config

    overrides = {k: v for k, v in payload.model_dump().items() if v is not None}
    merged = await update_config(db, **overrides)
    await db.commit()
    return merged


# ---------------------------------------------------------------------------
# P4 communication: manual triggers + coupon listing
# ---------------------------------------------------------------------------


@router.post("/anniversary/run", dependencies=[Depends(manager_only)])
async def run_anniversary_now(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Manually trigger the daily anniversary pass (P4-008). Same effect
    as waiting for the 09:00 cron — useful when adding a forgotten DOB
    on a client whose birthday is today."""
    from app.services.anniversary import run_anniversary_pass

    summary = await run_anniversary_pass(db)
    await db.commit()
    return summary


@router.post("/new-arrivals/run", dependencies=[Depends(manager_only)])
async def run_new_arrivals_now(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Manually trigger the weekly new-arrivals digest (P4-009)."""
    from app.services.new_arrivals import run_new_arrivals_pass

    summary = await run_new_arrivals_pass(db)
    await db.commit()
    return summary


@router.get("/coupons", dependencies=[Depends(manager_only)])
async def list_coupons(
    db: Annotated[AsyncSession, Depends(get_db)],
    only_active: bool = Query(default=True),
):
    """List recent coupons with their redemption status."""
    from app.models.coupon import Coupon

    stmt = select(Coupon).order_by(Coupon.created_at.desc()).limit(200)
    if only_active:
        stmt = stmt.where(Coupon.is_active.is_(True), Coupon.redeemed_at.is_(None))
    rows = await db.execute(stmt)
    coupons = rows.scalars().all()
    return [
        {
            "id": str(c.id),
            "code": c.code,
            "client_id": str(c.client_id) if c.client_id else None,
            "discount_type": c.discount_type.value,
            "discount_value": float(c.discount_value),
            "source": c.source.value,
            "valid_from": c.valid_from.isoformat() if c.valid_from else None,
            "valid_until": c.valid_until.isoformat() if c.valid_until else None,
            "redeemed_at": c.redeemed_at.isoformat() if c.redeemed_at else None,
            "is_active": c.is_active,
        }
        for c in coupons
    ]



# ---------------------------------------------------------------------------
# L2.4 — Local calendar (Vernon + Giverny + school holidays) + operations
# ---------------------------------------------------------------------------


class LocalEventPayload(BaseModel):
    title: str
    date_start: str  # ISO date
    date_end: str
    location: str = "Vernon"
    expected_traffic_boost_pct: int = 0
    description: str | None = None
    source_url: str | None = None
    is_school_holiday: bool = False


@router.get("/local-events", dependencies=[Depends(manager_only)])
async def list_local_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
):
    """List LocalEvent entries, optionally filtered by date range."""
    from app.models.local_calendar import LocalEvent
    from datetime import date as _date

    stmt = select(LocalEvent).order_by(LocalEvent.date_start)
    if date_from:
        stmt = stmt.where(LocalEvent.date_end >= _date.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(LocalEvent.date_start <= _date.fromisoformat(date_to))
    rows = await db.execute(stmt)
    return [
        {
            "id": str(e.id),
            "title": e.title,
            "date_start": e.date_start.isoformat(),
            "date_end": e.date_end.isoformat(),
            "location": e.location,
            "expected_traffic_boost_pct": e.expected_traffic_boost_pct,
            "description": e.description,
            "is_school_holiday": e.is_school_holiday,
        }
        for e in rows.scalars().all()
    ]


@router.post("/local-events", dependencies=[Depends(manager_only)])
async def create_local_event(
    payload: LocalEventPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a LocalEvent."""
    from app.models.local_calendar import LocalEvent
    from datetime import date as _date

    ev = LocalEvent(
        title=payload.title,
        date_start=_date.fromisoformat(payload.date_start),
        date_end=_date.fromisoformat(payload.date_end),
        location=payload.location,
        expected_traffic_boost_pct=payload.expected_traffic_boost_pct,
        description=payload.description,
        source_url=payload.source_url,
        is_school_holiday=payload.is_school_holiday,
    )
    db.add(ev)
    await db.flush()
    await db.refresh(ev)
    return {"id": str(ev.id)}


class CommercialOperationPayload(BaseModel):
    name: str
    date_start: str
    date_end: str
    status: str = "draft"
    description: str | None = None
    op_type: str = "soldes"
    discount_pct: int = 0
    applicable_categories: list[str] | None = None
    applicable_zones: list[str] | None = None
    visible_pos: bool = True
    visible_site: bool = False


@router.get("/operations", dependencies=[Depends(manager_only)])
async def list_operations(
    db: Annotated[AsyncSession, Depends(get_db)],
    only_active: bool = Query(default=False),
):
    from app.models.local_calendar import CommercialOperation
    from datetime import date as _date

    stmt = select(CommercialOperation).order_by(CommercialOperation.date_start.desc())
    if only_active:
        today = _date.today()
        stmt = stmt.where(
            CommercialOperation.status == "active",
            CommercialOperation.date_start <= today,
            CommercialOperation.date_end >= today,
        )
    rows = await db.execute(stmt)
    return [
        {
            "id": str(o.id),
            "name": o.name,
            "date_start": o.date_start.isoformat(),
            "date_end": o.date_end.isoformat(),
            "status": o.status,
            "op_type": o.op_type,
            "discount_pct": o.discount_pct,
            "applicable_categories": o.applicable_categories,
            "applicable_zones": o.applicable_zones,
            "visible_pos": o.visible_pos,
            "visible_site": o.visible_site,
        }
        for o in rows.scalars().all()
    ]


@router.post("/operations", dependencies=[Depends(manager_only)])
async def create_operation(
    payload: CommercialOperationPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.local_calendar import CommercialOperation
    from datetime import date as _date

    op = CommercialOperation(
        name=payload.name,
        date_start=_date.fromisoformat(payload.date_start),
        date_end=_date.fromisoformat(payload.date_end),
        status=payload.status,
        description=payload.description,
        op_type=payload.op_type,
        discount_pct=payload.discount_pct,
        applicable_categories=payload.applicable_categories,
        applicable_zones=payload.applicable_zones,
        visible_pos=payload.visible_pos,
        visible_site=payload.visible_site,
    )
    db.add(op)
    await db.flush()
    await db.refresh(op)
    return {"id": str(op.id)}


# ---------------------------------------------------------------------------
# L5 — AI routing (multi-provider abstraction)
# ---------------------------------------------------------------------------


@router.get("/ai-routing", dependencies=[Depends(manager_only)])
async def get_ai_routing(db: Annotated[AsyncSession, Depends(get_db)]):
    """Return the current AI routing table (prompt → provider/model)."""
    from app.services.ai_router import get_routing

    return await get_routing(db)


@router.put("/ai-routing", dependencies=[Depends(manager_only)])
async def update_ai_routing(
    payload: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Replace the AI routing table.

    Body must be a dict prompt_name → { provider, model }.
    Provider must be in {anthropic, mistral, openai, gemini}.
    """
    from app.services.ai_router import update_routing

    try:
        return await update_routing(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# L4 — Scoring config (DB-backed weights with hot reload)
# ---------------------------------------------------------------------------


@router.get("/scoring-config", dependencies=[Depends(manager_only)])
async def get_scoring_config_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return the current scoring config (v3, 5 criteria) or the defaults."""
    from app.services.scoring_config import get_scoring_config

    return await get_scoring_config(db)


@router.put("/scoring-config", dependencies=[Depends(manager_only)])
async def update_scoring_config_endpoint(
    payload: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Validate & persist a new scoring config (manager only).

    The body must contain ``weights`` with the 5 v3 keys
    (attractivity / season / age / trend / price) summing to 1.0.
    Optional : ``age_weeks_table``, ``season_calendar``, ``price_thresholds``,
    ``price_points``, ``max_weeks_on_shelf``.
    """
    from app.services.scoring_config import update_scoring_config

    return await update_scoring_config(
        db, payload, user_email=current_user.email
    )


@router.post("/scoring-config/reset", dependencies=[Depends(manager_only)])
async def reset_scoring_config_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Restore the v3 default config."""
    from app.services.scoring_config import reset_scoring_config

    return await reset_scoring_config(db, user_email=current_user.email)


@router.post("/scoring-config/preview", dependencies=[Depends(manager_only)])
async def preview_scoring_config(
    payload: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Dry-run a scoring config against the live catalog (max 10 samples)."""
    from app.services.brand_tiers import get_brand_score
    from app.services.category_trends import get_category_trend
    from app.services.category_velocity import get_velocity_for_category
    from app.services.market_price_estimator import get_or_refresh_estimate
    from app.services.scoring_config import _validate_payload, get_scoring_config
    from app.services.scoring_service import compute_score

    _validate_payload(payload)
    current = await get_scoring_config(db)

    result = await db.execute(
        select(Product).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
        ).limit(10)
    )
    products = result.scalars().all()

    samples = []
    for p in products:
        trend = await get_category_trend(db, p.category_id)
        velocity = await get_velocity_for_category(db, p.category_id)
        brand_score = await get_brand_score(db, p.brand)
        market_estimate = await get_or_refresh_estimate(db, p)

        common = dict(
            shelf_date=p.shelf_date,
            sale_price=float(p.sale_price),
            market_price_estimate=market_estimate,
            category_name=p.category.name if p.category else None,
            category_trend=trend,
            category_avg_velocity=velocity,
            brand_score=brand_score,
            condition=getattr(p, "condition", None),
        )
        before = compute_score(**common, config=current)
        after = compute_score(**common, config=payload)

        samples.append({
            "product_id": str(p.id),
            "name": p.name,
            "score_before": before["total_score"],
            "score_after": after["total_score"],
            "delta": round(after["total_score"] - before["total_score"], 1),
            "action_before": before["action"],
            "action_after": after["action"],
        })

    return {
        "config_proposed": payload,
        "samples": samples,
        "n_sampled": len(samples),
    }


@router.get("/scoring-config/breakdown-stats", dependencies=[Depends(manager_only)])
async def scoring_breakdown_stats(db: Annotated[AsyncSession, Depends(get_db)]):
    """Stats used by the admin scoring page to render the per-criterion detail.

    Returns:
      - top_categories_velocity : 90j sales / week
      - top_brands              : count of sales by brand 90j (top 10)
      - category_trends_snapshot: live category_trends cache
      - shelf_distribution      : how many products per week-on-shelf bucket
    """
    from datetime import timedelta
    from app.models.pos import Transaction, TransactionItem, TransactionType
    from app.services.category_trends import refresh_cache as refresh_trends
    from app.services.category_velocity import top_categories

    velocity_top = await top_categories(db, limit=10)

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    brand_q = await db.execute(
        select(Product.brand, func.count(TransactionItem.id))
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= cutoff,
            Product.brand.is_not(None),
        )
        .group_by(Product.brand)
        .order_by(func.count(TransactionItem.id).desc())
        .limit(10)
    )
    top_brands = [
        {"brand": row[0], "sales_90d": int(row[1])} for row in brand_q.all()
    ]

    trends_snapshot = await refresh_trends(db)

    shelf_buckets = {f"week_{i+1}": 0 for i in range(6)}
    shelf_buckets["week_6_plus"] = 0
    pq = await db.execute(
        select(Product).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
        )
    )
    now = datetime.now(timezone.utc)
    for p in pq.scalars().all():
        if p.shelf_date is None:
            continue
        sd = p.shelf_date
        if sd.tzinfo is None:
            sd = sd.replace(tzinfo=timezone.utc)
        weeks = (now - sd).days // 7
        if weeks >= 6:
            shelf_buckets["week_6_plus"] += 1
        else:
            shelf_buckets[f"week_{weeks + 1}"] += 1

    return {
        "top_categories_velocity": velocity_top,
        "top_brands_90d": top_brands,
        "category_trends_snapshot": trends_snapshot,
        "shelf_distribution": shelf_buckets,
    }


# ---------------------------------------------------------------------------
# Loyalty subscription config (PR1)
# ---------------------------------------------------------------------------


class LoyaltyConfigRequest(BaseModel):
    mode: str
    price_cents: int = 0
    first_purchase_threshold_cents: int = 0
    window_start: str | None = None  # ISO YYYY-MM-DD inclusive
    window_end: str | None = None    # ISO YYYY-MM-DD inclusive


@router.get("/loyalty/config", dependencies=[Depends(manager_only)])
async def get_loyalty_config(db: Annotated[AsyncSession, Depends(get_db)]):
    """Read the active loyalty subscription mode + thresholds."""
    from app.services.loyalty_config import get_subscription_config

    cfg = await get_subscription_config(db)
    return cfg.to_dict()


@router.put("/loyalty/config", dependencies=[Depends(manager_only)])
async def update_loyalty_config(
    request: LoyaltyConfigRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Switch between free / paid / first_purchase enrollment modes."""
    from app.services.loyalty_config import set_subscription_config

    try:
        cfg = await set_subscription_config(
            db,
            mode=request.mode,
            price_cents=request.price_cents,
            first_purchase_threshold_cents=request.first_purchase_threshold_cents,
            window_start=request.window_start,
            window_end=request.window_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return cfg.to_dict()


class EventVoucherCatalogRequest(BaseModel):
    vouchers: list[dict]


@router.get("/event-vouchers/catalog", dependencies=[Depends(manager_only)])
async def get_event_voucher_catalog(db: Annotated[AsyncSession, Depends(get_db)]):
    """Catalogue des bons cadeau d'ouverture (montants / pourcentages / validité)."""
    from app.services.event_vouchers import get_catalog

    return {"vouchers": await get_catalog(db)}


@router.put("/event-vouchers/catalog", dependencies=[Depends(manager_only)])
async def update_event_voucher_catalog(
    request: EventVoucherCatalogRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Éditer le catalogue des bons cadeau (valeurs + validité + activation)."""
    from app.services.event_vouchers import update_catalog

    saved = await update_catalog(db, request.vouchers)
    await db.commit()
    return {"vouchers": saved}


class LoyaltyEarningRequest(BaseModel):
    # Defaults mirror app.services.loyalty_config (source of truth) : 5 € tous
    # les 100 pts, sans expiration (0 jour).
    euro_per_point: int = 1
    voucher_value_cents: int = 500
    voucher_threshold: int = 100
    voucher_valid_days: int = 0
    points_expiry_days: int = 730


@router.get("/loyalty/earning-config", dependencies=[Depends(manager_only)])
async def get_loyalty_earning_config(db: Annotated[AsyncSession, Depends(get_db)]):
    """Read the loyalty earning rules (points/€, voucher value+threshold,
    validity). Editable from admin/operations (#1)."""
    from app.services.loyalty_config import get_earning_config

    cfg = await get_earning_config(db)
    return cfg.to_dict()


@router.put("/loyalty/earning-config", dependencies=[Depends(manager_only)])
async def update_loyalty_earning_config(
    request: LoyaltyEarningRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Set the loyalty earning rules: 1 point per X €, voucher of X € every X
    points, voucher + points validity (days). Manager only (#1)."""
    from app.services.loyalty_config import set_earning_config

    try:
        cfg = await set_earning_config(
            db,
            euro_per_point=request.euro_per_point,
            voucher_value_cents=request.voucher_value_cents,
            voucher_threshold=request.voucher_threshold,
            voucher_valid_days=request.voucher_valid_days,
            points_expiry_days=request.points_expiry_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return cfg.to_dict()


# ---------------------------------------------------------------------------
# Trend alerts manual trigger (PR2)
# ---------------------------------------------------------------------------


@router.post("/trend-alerts/run", dependencies=[Depends(manager_only)])
async def trigger_trend_alerts(db: Annotated[AsyncSession, Depends(get_db)]):
    """Run the trend-alerts cron once on demand. Returns a per-step summary."""
    from app.services.trend_alerts import run_trend_alerts

    summary = await run_trend_alerts(db)
    await db.commit()
    return summary


# ---------------------------------------------------------------------------
# Predictive targeting (PR4)
# ---------------------------------------------------------------------------


@router.get("/predictive/audience", dependencies=[Depends(manager_only)])
async def predictive_audience_debug(
    period_days: int = 90,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Snapshot of dominant tastes among the loyalty-active cohort.

    Used as a debug + diagnostic for the scoring engine: if this list
    looks "off", the ``audience=loyal_active`` weighting will too.
    """
    from app.services.predictive_targeting import (
        dominant_tastes_loyal_active,
        serialize_dominant,
    )

    result = await dominant_tastes_loyal_active(db, period_days=max(7, min(period_days, 365)))
    return serialize_dominant(result)


@router.get("/appro-brief", dependencies=[Depends(manager_only)])
async def get_appro_brief(
    period_days: int = 90,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Brief d'appro hebdo (PS 360 V5) : demande vs stock → recommandations
    niveau carton (catégorie × genre × qualité).

    Le service ``build_appro_brief`` dégrade proprement au cold-start (renvoie
    les catégories les moins stockées quand il n'y a pas encore de signal de
    demande), donc l'endpoint répond toujours un brief exploitable. Il n'était
    simplement jamais monté au router → le front affichait « Brief
    indisponible ».
    """
    from app.services.appro_brief import build_appro_brief

    return await build_appro_brief(db, period_days=max(7, min(period_days, 365)))




# ───────────────────────────────────────────────────────────────────────────
# Brevo Contacts — synchronisation des coordonnées client + opt-in/out
# ───────────────────────────────────────────────────────────────────────────

@router.get("/brevo/status", dependencies=[Depends(manager_only)])
async def brevo_status():
    """Diagnostic rapide : clé configurée ? listes définies ? compte joignable ?"""
    import os
    from app.services.brevo_contacts import _api_key, _call, _email_list_ids, _sms_list_ids

    api_key = _api_key()
    out = {
        "configured": api_key is not None,
        "email_list_ids": _email_list_ids(),
        "sms_list_ids": _sms_list_ids(),
        "account": None,
    }
    if api_key:
        try:
            status, body = _call("GET", "/account")
            if 200 <= status < 300:
                out["account"] = {
                    "email": body.get("email"),
                    "plan_type": (body.get("plan") or [{}])[0].get("type"),
                }
            else:
                out["account"] = {"error": f"HTTP {status}: {str(body)[:120]}"}
        except Exception as exc:  # noqa: BLE001
            out["account"] = {"error": str(exc)[:120]}
    return out


class BrevoSyncRequest(BaseModel):
    only_optin: bool = False


@router.post("/brevo/sync-all", dependencies=[Depends(manager_only)])
async def brevo_sync_all(
    payload: BrevoSyncRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Pousse en bloc tous les clients vers Brevo (upsert).

    À déclencher en one-shot après config de ``BREVO_API_KEY``, ou pour
    rattraper un drift (ex. campagnes déclenchées hors Vintiz). Best-effort :
    chaque échec est compté mais n'interrompt pas la boucle.
    """
    from app.services.brevo_contacts import push_all_clients

    return await push_all_clients(db, only_optin=payload.only_optin)


@router.post("/brevo/sync-client/{client_id}", dependencies=[Depends(manager_only)])
async def brevo_sync_client(
    client_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Pousse un client précis vers Brevo (debug / réparation ponctuelle)."""
    from app.models.client import Client
    from app.services.brevo_contacts import push_client

    row = await db.execute(select(Client).where(Client.id == client_id))
    client = row.scalar_one_or_none()
    if client is None:
        raise HTTPException(404, "Client introuvable")
    res = push_client(client)
    return {
        "ok": res.ok,
        "status_code": res.status_code,
        "detail": res.detail,
    }


# ---------------------------------------------------------------------------
# Capsule du mois — page éditoriale dynamique
# ---------------------------------------------------------------------------


@router.get("/capsule/current", dependencies=[Depends(manager_only)])
async def get_current_capsule(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Capsule éditoriale du mois en cours (créée à la demande si absente).

    Le contenu (audience, produits tendance, produits événement, pastilles
    couleurs/types/idées cadeaux) ne contient que des pièces actuellement
    actives à l'inventaire — un produit vendu disparaît au prochain regen.
    """
    from app.services.capsule import get_or_create_current_capsule, serialize_capsule

    row = await get_or_create_current_capsule(db)
    await db.commit()
    return serialize_capsule(row)


@router.post("/capsule/regenerate", dependencies=[Depends(manager_only)])
async def regenerate_current_capsule(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Force un nouveau regen de la capsule du mois courant.

    Utile quand le manager vient de saisir une vague de produits ou veut
    rafraîchir les pastilles IA après changement d'audience.
    """
    from app.services.capsule import regenerate_capsule, serialize_capsule

    row = await regenerate_capsule(db)
    await db.commit()
    return serialize_capsule(row)
