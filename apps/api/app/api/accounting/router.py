"""API Comptabilité — paramétrage, exports, journal, réconciliation."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker, get_current_user
from app.models.accounting import AccountingConfig, AccountingExport, AccountingExportLine, ExportStatus
from app.models.user import User
from app.services.accounting_service import AccountingService
from app.services.pennylane_client import PennylaneClient

router = APIRouter(prefix="/accounting", tags=["accounting"])
manager_only = RoleChecker(["manager"])


# ── Schémas ──────────────────────────────────────────────────────────────────

class AccountingConfigIn(BaseModel):
    account_sales: str | None = None
    account_tva: str | None = None
    tva_rate: float | None = None
    account_cash: str | None = None
    account_card: str | None = None
    account_cheque: str | None = None
    account_cheque_cdc: str | None = None
    account_avoir: str | None = None
    account_transfer: str | None = None
    label_sales: str | None = None
    label_tva: str | None = None
    label_cash: str | None = None
    label_card: str | None = None
    label_cheque: str | None = None
    label_cheque_cdc: str | None = None
    label_avoir: str | None = None
    label_transfer: str | None = None
    pennylane_enabled: bool | None = None
    pennylane_api_key: str | None = None
    pennylane_journal_code: str | None = None
    pennylane_api_url: str | None = None
    discrepancy_alert_threshold: float | None = None
    discrepancy_alert_email: str | None = None
    daily_report_email: str | None = None
    daily_report_enabled: bool | None = None
    fec_monthly_enabled: bool | None = None


def _mask_key(key: str | None) -> str | None:
    if not key or len(key) < 8:
        return None
    return key[:6] + "…" + key[-4:]


def _config_out(cfg: AccountingConfig) -> dict:
    return {
        "id": str(cfg.id),
        "account_sales": cfg.account_sales,
        "account_tva": cfg.account_tva,
        "tva_rate": float(cfg.tva_rate),
        "account_cash": cfg.account_cash,
        "account_card": cfg.account_card,
        "account_cheque": cfg.account_cheque,
        "account_cheque_cdc": cfg.account_cheque_cdc,
        "account_avoir": cfg.account_avoir,
        "account_transfer": cfg.account_transfer,
        "label_sales": cfg.label_sales,
        "label_tva": cfg.label_tva,
        "label_cash": cfg.label_cash,
        "label_card": cfg.label_card,
        "label_cheque": cfg.label_cheque,
        "label_cheque_cdc": cfg.label_cheque_cdc,
        "label_avoir": cfg.label_avoir,
        "label_transfer": cfg.label_transfer,
        "pennylane_enabled": cfg.pennylane_enabled,
        "pennylane_api_key_hint": _mask_key(cfg.pennylane_api_key),
        "pennylane_api_key_set": bool(cfg.pennylane_api_key),
        "pennylane_journal_code": cfg.pennylane_journal_code,
        "pennylane_api_url": cfg.pennylane_api_url,
        "discrepancy_alert_threshold": float(cfg.discrepancy_alert_threshold),
        "discrepancy_alert_email": cfg.discrepancy_alert_email,
        "daily_report_email": cfg.daily_report_email,
        "daily_report_enabled": cfg.daily_report_enabled,
        "fec_monthly_enabled": cfg.fec_monthly_enabled,
    }


def _export_out(exp: AccountingExport, with_lines: bool = False) -> dict:
    base = {
        "id": str(exp.id),
        "z_report_id": str(exp.z_report_id),
        "export_date": exp.export_date.isoformat(),
        "status": exp.status.value,
        "total_sales_ht": float(exp.total_sales_ht),
        "total_tva": float(exp.total_tva),
        "total_sales_ttc": float(exp.total_sales_ttc),
        "total_refunds_ttc": float(exp.total_refunds_ttc),
        "net_ttc": float(exp.net_ttc),
        "transaction_count": exp.transaction_count,
        "refund_count": exp.refund_count,
        "cash_total": float(exp.cash_total),
        "card_total": float(exp.card_total),
        "cheque_total": float(exp.cheque_total),
        "cheque_cdc_total": float(exp.cheque_cdc_total),
        "avoir_total": float(exp.avoir_total),
        "transfer_total": float(exp.transfer_total),
        "cash_expected": float(exp.cash_expected) if exp.cash_expected else None,
        "cash_counted": float(exp.cash_counted) if exp.cash_counted else None,
        "cash_discrepancy": float(exp.cash_discrepancy) if exp.cash_discrepancy is not None else None,
        "discrepancy_alert_sent": exp.discrepancy_alert_sent,
        "pennylane_ledger_event_id": exp.pennylane_ledger_event_id,
        "pennylane_exported_at": exp.pennylane_exported_at.isoformat() if exp.pennylane_exported_at else None,
        "pennylane_error": exp.pennylane_error,
        "pennylane_attempts": exp.pennylane_attempts,
        "fec_filename": exp.fec_filename,
        "fec_generated_at": exp.fec_generated_at.isoformat() if exp.fec_generated_at else None,
        "email_sent_at": exp.email_sent_at.isoformat() if exp.email_sent_at else None,
        "email_sent_to": exp.email_sent_to,
        "locked_at": exp.locked_at.isoformat() if exp.locked_at else None,
        "created_at": exp.created_at.isoformat(),
    }
    if with_lines:
        base["lines"] = [
            {
                "line_number": ln.line_number,
                "account_number": ln.account_number,
                "account_label": ln.account_label,
                "debit": float(ln.debit),
                "credit": float(ln.credit),
                "label": ln.label,
                "piece_reference": ln.piece_reference,
                "piece_date": ln.piece_date.isoformat() if ln.piece_date else None,
            }
            for ln in sorted(exp.lines or [], key=lambda line: line.line_number)
        ]
    return base


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/config", dependencies=[Depends(manager_only)])
async def get_accounting_config(db: Annotated[AsyncSession, Depends(get_db)]):
    svc = AccountingService(db)
    cfg = await svc.get_config()
    return _config_out(cfg)


@router.put("/config", dependencies=[Depends(manager_only)])
async def update_accounting_config(
    body: AccountingConfigIn,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = AccountingService(db)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    cfg = await svc.upsert_config(data)
    await db.commit()
    return _config_out(cfg)


@router.post("/pennylane/test", dependencies=[Depends(manager_only)])
async def test_pennylane(db: Annotated[AsyncSession, Depends(get_db)]):
    """Teste la connexion à Pennylane et remonte la cause exacte en cas d'échec
    (clé invalide, scope manquant, réseau…) au lieu d'un simple « non connecté »."""
    from app.services.pennylane_client import PennylaneError

    svc = AccountingService(db)
    cfg = await svc.get_config()
    if not cfg.pennylane_api_key:
        raise HTTPException(400, detail="Clé API Pennylane non configurée")
    client = PennylaneClient(cfg.pennylane_api_key, cfg.pennylane_api_url)
    try:
        # Appel réel (GET /journals) — l'exception porte le code HTTP + le corps.
        client._call("GET", "/journals")
        return {"connected": True, "api_url": cfg.pennylane_api_url}
    except PennylaneError as exc:
        code = getattr(exc, "status_code", None)
        hint = ""
        if code == 401:
            hint = " — clé API invalide ou révoquée (vérifiez le token collé)."
        elif code == 403:
            hint = " — scope manquant : cochez « Journaux » (lecture) sur le token Pennylane."
        elif code == 404:
            hint = " — URL d'API incorrecte (attendu …/api/external/v2)."
        return {
            "connected": False,
            "api_url": cfg.pennylane_api_url,
            "status_code": code,
            "detail": f"{exc}{hint}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "connected": False,
            "api_url": cfg.pennylane_api_url,
            "detail": f"Erreur inattendue : {exc}",
        }


@router.get("/exports", dependencies=[Depends(manager_only)])
async def list_exports(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = Query(30, ge=1, le=200),
    status: str | None = None,
):
    stmt = select(AccountingExport).order_by(AccountingExport.export_date.desc())
    if status:
        try:
            stmt = stmt.where(AccountingExport.status == ExportStatus(status))
        except ValueError:
            raise HTTPException(400, detail=f"Statut invalide : {status}")
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    exports = result.scalars().all()
    return [_export_out(exp) for exp in exports]


@router.get("/exports/{export_id}", dependencies=[Depends(manager_only)])
async def get_export(
    export_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(AccountingExport).where(AccountingExport.id == export_id)
    )
    exp = result.scalar_one_or_none()
    if not exp:
        raise HTTPException(404, detail="Export introuvable")
    return _export_out(exp, with_lines=True)


@router.post("/exports/{export_id}/retry", dependencies=[Depends(manager_only)])
async def retry_export(
    export_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Re-tente l'export Pennylane pour un export en échec (feature B)."""
    result = await db.execute(
        select(AccountingExport).where(AccountingExport.id == export_id)
    )
    exp = result.scalar_one_or_none()
    if not exp:
        raise HTTPException(404, detail="Export introuvable")
    if exp.status == ExportStatus.exported:
        return {"message": "Déjà exporté", "status": "exported"}
    svc = AccountingService(db)
    updated = await svc.retry_pennylane_export(exp)
    return _export_out(updated)


@router.post("/exports/{export_id}/regenerate", dependencies=[Depends(manager_only)])
async def regenerate_export(
    export_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Régénère un export FEC à partir des transactions liées.

    Use case : un FEC a été produit avec une version buguée du moteur
    (ex. méthode voucher non mappée → débit < crédit). On rejoue la
    ventilation comptable avec le moteur courant sans toucher à la
    chaîne fiscale NF525 (hash_chain des Tx intact).

    Refuse si la nouvelle écriture reste déséquilibrée (FECImbalanceError
    → 422). C'est un garde-fou : impossible de produire un FEC illégal.
    """
    from app.services.accounting_service import FECImbalanceError

    result = await db.execute(
        select(AccountingExport).where(AccountingExport.id == export_id)
    )
    exp = result.scalar_one_or_none()
    if not exp:
        raise HTTPException(404, detail="Export introuvable")

    svc = AccountingService(db)
    try:
        updated = await svc.regenerate_export(exp, triggered_by_user_id=current_user.id)
    except FECImbalanceError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Régénération refusée — écriture toujours déséquilibrée : {exc}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _export_out(updated)


@router.get("/exports/{export_id}/fec", dependencies=[Depends(manager_only)])
async def download_fec(
    export_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Télécharge le fichier FEC quotidien."""
    result = await db.execute(
        select(AccountingExport).where(AccountingExport.id == export_id)
    )
    exp = result.scalar_one_or_none()
    if not exp:
        raise HTTPException(404, detail="Export introuvable")
    if not exp.fec_content:
        raise HTTPException(404, detail="FEC non généré pour cet export")
    filename = exp.fec_filename or f"FEC_Vintiz_{exp.export_date}.txt"
    return Response(
        content=exp.fec_content.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/journal", dependencies=[Depends(manager_only)])
async def get_journal(
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
):
    """Journal comptable interne — toutes les lignes d'écriture sur une période (feature E)."""

    stmt = (
        select(AccountingExportLine, AccountingExport)
        .join(AccountingExport, AccountingExportLine.export_id == AccountingExport.id)
        .order_by(AccountingExport.export_date.desc(), AccountingExportLine.line_number.asc())
    )
    if date_from:
        try:
            df = date.fromisoformat(date_from)
            stmt = stmt.where(AccountingExport.export_date >= df)
        except ValueError:
            raise HTTPException(400, detail="Paramètre 'from' invalide (YYYY-MM-DD)")
    if date_to:
        try:
            dt = date.fromisoformat(date_to)
            stmt = stmt.where(AccountingExport.export_date <= dt)
        except ValueError:
            raise HTTPException(400, detail="Paramètre 'to' invalide (YYYY-MM-DD)")
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "export_id": str(ln.export_id),
            "export_date": exp.export_date.isoformat(),
            "line_number": ln.line_number,
            "account_number": ln.account_number,
            "account_label": ln.account_label,
            "debit": float(ln.debit),
            "credit": float(ln.credit),
            "label": ln.label,
            "piece_reference": ln.piece_reference,
        }
        for ln, exp in rows
    ]


@router.get("/reconciliation/{target_date}", dependencies=[Depends(manager_only)])
async def reconcile_sumup(
    target_date: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Réconciliation SumUp vs Vintiz pour une date (feature C)."""
    from app.services.sumup_reconciliation import SumUpReconciliationService
    try:
        d = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(400, detail="Date invalide (YYYY-MM-DD)")
    svc = SumUpReconciliationService(db)
    report = await svc.reconcile(d)
    return {
        "reconciliation_date": report.reconciliation_date,
        "total_vintiz_card": report.total_vintiz_card,
        "total_sumup": report.total_sumup,
        "delta": report.delta,
        "matched_count": report.matched_count,
        "matched_by_amount": report.matched_by_amount,
        "unmatched_vintiz": report.unmatched_vintiz,
        "unmatched_sumup": report.unmatched_sumup,
        "api_key_present": report.api_key_present,
        "api_error": report.api_error,
        "api_pages_fetched": report.api_pages_fetched,
        "api_raw_tx_count": report.api_raw_tx_count,
        "lines": [
            {
                "vintiz_payment_id": ln.vintiz_payment_id,
                "vintiz_transaction_number": ln.vintiz_transaction_number,
                "vintiz_amount": ln.vintiz_amount,
                "vintiz_timestamp": ln.vintiz_timestamp,
                "sumup_transaction_id": ln.sumup_transaction_id,
                "sumup_transaction_code": ln.sumup_transaction_code,
                "sumup_amount": ln.sumup_amount,
                "sumup_timestamp": ln.sumup_timestamp,
                "status": ln.status,
                "delta": ln.delta,
            }
            for ln in report.lines
        ],
    }


@router.get("/monthly-close/{year}/{month}", dependencies=[Depends(manager_only)])
async def get_monthly_csv(
    year: int,
    month: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Télécharge l'export CSV mensuel des écritures — importable dans Pennylane.

    Remplace le FEC .txt mensuel par un CSV NF525/DGFiP-fidèle (écritures des
    clôtures Z, séquentielles, équilibrées) au format Pennylane : séparateur
    « ; », décimales à la virgule, UTF-8 BOM, dates JJ/MM/AAAA. Le FEC .txt
    quotidien par Z reste disponible (trace fiscale légale, endpoints /fec).
    """
    if not (1 <= month <= 12):
        raise HTTPException(400, detail="Mois invalide")
    svc = AccountingService(db)
    csv_content = await svc.generate_monthly_csv(year, month)
    filename = f"Ecritures_Vintiz_{year}{month:02d}.csv"
    return Response(
        # UTF-8 BOM (utf-8-sig) pour qu'Excel ouvre les accents correctement.
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/monthly-close", dependencies=[Depends(manager_only)])
async def list_monthly_closes(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Liste des mois avec exports disponibles."""
    from sqlalchemy import func, extract
    stmt = (
        select(
            extract("year", AccountingExport.export_date).label("year"),
            extract("month", AccountingExport.export_date).label("month"),
            func.count(AccountingExport.id).label("count"),
            func.sum(AccountingExport.net_ttc).label("net_ttc"),
        )
        .group_by("year", "month")
        .order_by("year", "month")
    )
    result = await db.execute(stmt)
    return [
        {
            "year": int(row.year),
            "month": int(row.month),
            "count": row.count,
            "net_ttc": round(float(row.net_ttc or 0), 2),
        }
        for row in result.all()
    ]


# ---------------------------------------------------------------------------
# Export / FEC par journée — à la demande (toute journée, y c. régularisations)
# ---------------------------------------------------------------------------


@router.post("/exports/day/{target_date}", dependencies=[Depends(manager_only)])
async def generate_day_export(
    target_date: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Génère l'export comptable d'une journée : régularise les ventes
    orphelines (crée le Z) et produit l'export + FEC de chaque Z du jour. La
    journée apparaît alors dans la liste des exports. Idempotent."""
    try:
        d = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(400, detail="Date invalide (YYYY-MM-DD)")
    result = await AccountingService(db).ensure_day_exported(d, current_user.id)
    await db.commit()
    return result


@router.get("/fec/day/{target_date}", dependencies=[Depends(manager_only)])
async def download_day_fec(
    target_date: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Télécharge le FEC agrégé d'une journée (toutes ses clôtures)."""
    try:
        d = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(400, detail="Date invalide (YYYY-MM-DD)")
    fec = await AccountingService(db).generate_daily_fec(d)
    filename = f"FEC_Vintiz_{d.strftime('%Y%m%d')}.txt"
    return Response(
        content=fec.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
