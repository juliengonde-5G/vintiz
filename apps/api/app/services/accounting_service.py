"""Accounting service — orchestrateur clôture quotidienne.

Workflow déclenché par POST /api/pos/drawer/close :
1. Contrôle de caisse (écart attendu vs compté)
2. Génération des lignes d'écriture PCG (agrégé par Z-report)
3. Génération du fichier FEC quotidien
4. Verrouillage comptable des transactions
5. Export vers Pennylane (si configuré et connecté)
6. Email rapport à vernon@vintiz.fr
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting import (
    AccountingConfig,
    AccountingExport,
    AccountingExportLine,
    ExportStatus,
)
from app.models.pos import (
    CashDrawer,
    Payment,
    PaymentMethod,
    Transaction,
    TransactionType,
    ZReport,
)
from app.services.pennylane_client import JournalEntry, JournalEntryLine, PennylaneClient, PennylaneError

_log = logging.getLogger("vintiz.accounting")


def _fmt(value) -> str:
    return f"{float(value):.2f}"


# ---------------------------------------------------------------------------
# FEC (Format d'Échange Comptable) — colonnes obligatoires DGFiP
# ---------------------------------------------------------------------------

_FEC_COLUMNS = [
    "JournalCode", "JournalLib", "EcritureNum", "EcritureDate",
    "CompteNum", "CompteLib", "CompAuxNum", "CompAuxLib",
    "PieceRef", "PieceDate", "EcritureLib",
    "Debit", "Credit", "EcritureLet", "DateLet",
    "ValidDate", "Montantdevise", "Idevise",
]


def _fec_row(**kwargs) -> str:
    return "\t".join(str(kwargs.get(col, "")) for col in _FEC_COLUMNS)


def _fec_date(d: date | datetime | None) -> str:
    if d is None:
        return ""
    if isinstance(d, datetime):
        return d.strftime("%Y%m%d")
    return d.strftime("%Y%m%d")


class AccountingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Config ───────────────────────────────────────────────────────────────

    async def get_config(self) -> AccountingConfig:
        result = await self.db.execute(select(AccountingConfig).limit(1))
        cfg = result.scalar_one_or_none()
        if cfg is None:
            cfg = AccountingConfig()
            self.db.add(cfg)
            await self.db.flush()
        return cfg

    async def upsert_config(self, data: dict) -> AccountingConfig:
        cfg = await self.get_config()
        for key, value in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        await self.db.flush()
        return cfg

    # ── Clôture quotidienne (point d'entrée principal) ───────────────────────

    async def run_daily_close(
        self,
        z_report: ZReport,
        drawer: CashDrawer,
        triggered_by_user_id=None,
    ) -> AccountingExport:
        cfg = await self.get_config()

        export_date = (drawer.closed_at or datetime.now(timezone.utc)).date()

        # Idempotence — si déjà exporté pour ce Z-report, on renvoie l'existant
        existing = await self.db.execute(
            select(AccountingExport).where(
                AccountingExport.z_report_id == z_report.id
            )
        )
        if ex := existing.scalar_one_or_none():
            return ex

        # 1. Récupérer les transactions de la session caisse
        transactions = await self._load_transactions(drawer)

        # 2. Calculer les totaux par méthode de paiement
        totals = self._compute_totals(transactions)

        # 3. Générer les lignes d'écriture
        lines = self._build_journal_lines(totals, cfg, z_report, export_date)

        # 4. Créer l'AccountingExport
        acct_exp = AccountingExport(
            z_report_id=z_report.id,
            export_date=export_date,
            status=ExportStatus.pending,
            total_sales_ht=totals["sales_ht"],
            total_tva=totals["sales_tva"],
            total_sales_ttc=totals["sales_ttc"],
            total_refunds_ttc=totals["refunds_ttc"],
            net_ttc=totals["sales_ttc"] - totals["refunds_ttc"],
            transaction_count=totals["sale_count"],
            refund_count=totals["refund_count"],
            cash_total=totals["by_method"].get("cash", 0),
            card_total=totals["by_method"].get("card", 0),
            cheque_total=totals["by_method"].get("cheque", 0),
            cheque_cdc_total=totals["by_method"].get("cheque_cdc", 0),
            avoir_total=totals["by_method"].get("avoir", 0),
            transfer_total=totals["by_method"].get("transfer", 0),
            cash_expected=float(drawer.expected_amount) if drawer.expected_amount else None,
            cash_counted=float(drawer.closing_amount) if drawer.closing_amount else None,
            cash_discrepancy=(
                round(float(drawer.closing_amount) - float(drawer.expected_amount), 2)
                if drawer.closing_amount and drawer.expected_amount
                else None
            ),
            exported_by_user_id=triggered_by_user_id,
        )
        self.db.add(acct_exp)
        await self.db.flush()

        # 5. Persister les lignes
        for i, ln in enumerate(lines, start=1):
            self.db.add(
                AccountingExportLine(
                    export_id=acct_exp.id,
                    line_number=i,
                    account_number=ln.account_number,
                    account_label=ln.account_label,
                    debit=ln.debit,
                    credit=ln.credit,
                    label=ln.label,
                    piece_reference=f"Z{z_report.report_number:04d}",
                    piece_date=export_date,
                )
            )
        await self.db.flush()

        # 6. Réconciliation SumUp (best-effort, informatif)
        try:
            from app.services.sumup_reconciliation import SumUpReconciliationService
            recon_svc = SumUpReconciliationService(self.db)
            recon = await recon_svc.reconcile(export_date)
            acct_exp.reconciliation_ran = True
            acct_exp.reconciliation_delta = round(recon.delta, 2)
            acct_exp.reconciliation_matched = recon.matched_count
            acct_exp.reconciliation_unmatched_vintiz = recon.unmatched_vintiz
            acct_exp.reconciliation_unmatched_sumup = recon.unmatched_sumup
        except Exception as _recon_exc:
            _log.warning("SumUp reconciliation skipped: %s", _recon_exc)

        # 7. Alerte écart de caisse
        if (
            acct_exp.cash_discrepancy is not None
            and abs(acct_exp.cash_discrepancy) > float(cfg.discrepancy_alert_threshold)
        ):
            await self._send_discrepancy_alert(acct_exp, cfg)
            acct_exp.discrepancy_alert_sent = True

        # 8. Générer le FEC quotidien
        fec = self._generate_fec(lines, z_report, export_date, cfg)
        acct_exp.fec_content = fec
        acct_exp.fec_filename = f"FEC_Vintiz_{export_date.strftime('%Y%m%d')}_Z{z_report.report_number:04d}.txt"
        acct_exp.fec_generated_at = datetime.now(timezone.utc)

        # 9. Verrouiller les transactions
        tx_ids = [t.id for t in transactions]
        if tx_ids:
            await self.db.execute(
                update(Transaction)
                .where(Transaction.id.in_(tx_ids))
                .values(
                    accounting_locked=True,
                    accounting_export_id=acct_exp.id,
                )
            )
        acct_exp.locked_at = datetime.now(timezone.utc)

        # 10. Export Pennylane (async best-effort)
        if cfg.pennylane_enabled and cfg.pennylane_api_key:
            await self._export_to_pennylane(acct_exp, lines, cfg, z_report, export_date)
        else:
            acct_exp.status = ExportStatus.manual

        await self.db.flush()

        # 10. Email rapport quotidien
        if cfg.daily_report_enabled and cfg.daily_report_email:
            await self._send_daily_email(acct_exp, z_report, drawer, cfg)

        await self.db.commit()
        return acct_exp

    # ── Re-export Pennylane (feature B) ─────────────────────────────────────

    async def retry_pennylane_export(self, export: AccountingExport) -> AccountingExport:
        cfg = await self.get_config()
        if not cfg.pennylane_enabled or not cfg.pennylane_api_key:
            raise ValueError("Pennylane non configuré")

        lines = list(export.lines)
        journal_lines = [
            JournalEntryLine(
                account_number=ln.account_number,
                account_label=ln.account_label,
                debit=float(ln.debit),
                credit=float(ln.credit),
                label=ln.label,
            )
            for ln in sorted(lines, key=lambda l: l.line_number)
        ]
        await self._export_to_pennylane(export, journal_lines, cfg, None, export.export_date)
        await self.db.commit()
        return export

    # ── Chargement transactions ──────────────────────────────────────────────

    async def _load_transactions(self, drawer: CashDrawer) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(Transaction.created_at >= drawer.opened_at)
            .where(Transaction.transaction_type.in_([TransactionType.sale, TransactionType.refund]))
            .order_by(Transaction.created_at.asc())
        )
        if drawer.closed_at:
            stmt = stmt.where(Transaction.created_at <= drawer.closed_at)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Calcul des totaux ────────────────────────────────────────────────────

    def _compute_totals(self, transactions: list[Transaction]) -> dict:
        sales_ht = 0.0
        sales_tva = 0.0
        sales_ttc = 0.0
        refunds_ttc = 0.0
        sale_count = 0
        refund_count = 0
        by_method: dict[str, float] = {m.value: 0.0 for m in PaymentMethod}

        for txn in transactions:
            if txn.transaction_type == TransactionType.sale:
                sales_ht += float(txn.total_ht)
                sales_tva += float(txn.total_tva)
                sales_ttc += float(txn.total_ttc)
                sale_count += 1
                for p in (txn.payments or []):
                    by_method[p.method.value] = by_method.get(p.method.value, 0) + float(p.amount)
            elif txn.transaction_type == TransactionType.refund:
                refunds_ttc += float(txn.total_ttc)
                refund_count += 1
                for p in (txn.payments or []):
                    by_method[p.method.value] = by_method.get(p.method.value, 0) - float(p.amount)

        return {
            "sales_ht": round(sales_ht, 2),
            "sales_tva": round(sales_tva, 2),
            "sales_ttc": round(sales_ttc, 2),
            "refunds_ttc": round(refunds_ttc, 2),
            "sale_count": sale_count,
            "refund_count": refund_count,
            "by_method": {k: round(v, 2) for k, v in by_method.items()},
        }

    # ── Construction des lignes d'écriture ───────────────────────────────────

    def _build_journal_lines(
        self,
        totals: dict,
        cfg: AccountingConfig,
        z_report: ZReport,
        export_date: date,
    ) -> list[JournalEntryLine]:
        lines: list[JournalEntryLine] = []
        z_ref = f"Z{z_report.report_number:04d}"

        # ── Débit : comptes d'encaissement (une ligne par méthode) ──────────
        method_map = {
            "cash": (cfg.account_cash, cfg.label_cash),
            "card": (cfg.account_card, cfg.label_card),
            "cheque": (cfg.account_cheque, cfg.label_cheque),
            "cheque_cdc": (cfg.account_cheque_cdc, cfg.label_cheque_cdc),
            "avoir": (cfg.account_avoir, cfg.label_avoir),
            "transfer": (cfg.account_transfer, cfg.label_transfer),
        }
        for method, (account, label) in method_map.items():
            amount = totals["by_method"].get(method, 0)
            if abs(amount) < 0.005:
                continue
            if amount > 0:
                lines.append(JournalEntryLine(
                    account_number=account,
                    account_label=label,
                    debit=amount,
                    credit=0,
                    label=f"{label} — {z_ref}",
                ))
            else:
                # Remboursement net supérieur aux ventes (cas rare)
                lines.append(JournalEntryLine(
                    account_number=account,
                    account_label=label,
                    debit=0,
                    credit=abs(amount),
                    label=f"Remboursement {label} — {z_ref}",
                ))

        # ── Crédit : ventes HT (707) ─────────────────────────────────────────
        net_ht = totals["sales_ht"]
        net_ttc = totals["sales_ttc"] - totals["refunds_ttc"]
        tva = totals["sales_tva"]

        if net_ht > 0:
            lines.append(JournalEntryLine(
                account_number=cfg.account_sales,
                account_label=cfg.label_sales,
                debit=0,
                credit=net_ht,
                label=f"{cfg.label_sales} — {z_ref}",
            ))

        # ── Crédit : TVA collectée (44571) ────────────────────────────────────
        if tva > 0:
            lines.append(JournalEntryLine(
                account_number=cfg.account_tva,
                account_label=cfg.label_tva,
                debit=0,
                credit=tva,
                label=f"{cfg.label_tva} — {z_ref}",
            ))

        return lines

    # ── FEC Format d'Échange Comptable ───────────────────────────────────────

    def _generate_fec(
        self,
        lines: list[JournalEntryLine],
        z_report: ZReport,
        export_date: date,
        cfg: AccountingConfig,
    ) -> str:
        rows = ["\t".join(_FEC_COLUMNS)]
        ecriture_date = _fec_date(export_date)
        piece_ref = f"Z{z_report.report_number:04d}"
        valid_date = _fec_date(datetime.now(timezone.utc))

        for i, ln in enumerate(lines, start=1):
            rows.append(
                _fec_row(
                    JournalCode=cfg.pennylane_journal_code,
                    JournalLib="Ventes",
                    EcritureNum=f"{z_report.report_number:04d}-{i:03d}",
                    EcritureDate=ecriture_date,
                    CompteNum=ln.account_number,
                    CompteLib=ln.account_label,
                    CompAuxNum="",
                    CompAuxLib="",
                    PieceRef=piece_ref,
                    PieceDate=ecriture_date,
                    EcritureLib=ln.label,
                    Debit=f"{ln.debit:.2f}".replace(".", ",") if ln.debit else "0,00",
                    Credit=f"{ln.credit:.2f}".replace(".", ",") if ln.credit else "0,00",
                    EcritureLet="",
                    DateLet="",
                    ValidDate=valid_date,
                    Montantdevise="",
                    Idevise="EUR",
                )
            )
        return "\n".join(rows)

    # ── Export Pennylane ─────────────────────────────────────────────────────

    async def _export_to_pennylane(
        self,
        export: AccountingExport,
        lines,
        cfg: AccountingConfig,
        z_report,
        export_date: date,
    ) -> None:
        export.pennylane_attempts = (export.pennylane_attempts or 0) + 1
        try:
            client = PennylaneClient(cfg.pennylane_api_key, cfg.pennylane_api_url)
            z_num = z_report.report_number if z_report else "?"
            entry = JournalEntry(
                date=export_date,
                label=f"Ventes Vintiz Vernon — Z-Report N°{z_num} — {export_date.strftime('%d/%m/%Y')}",
                journal_code=cfg.pennylane_journal_code,
                lines=[
                    JournalEntryLine(
                        account_number=ln.account_number if hasattr(ln, "account_number") else ln.account_number,
                        account_label=ln.account_label,
                        debit=float(ln.debit),
                        credit=float(ln.credit),
                        label=ln.label,
                    )
                    for ln in (sorted(lines, key=lambda l: l.line_number) if hasattr(lines[0], "line_number") else lines)
                ] if lines else [],
            )
            ledger_id = client.create_journal_entry(entry)
            export.pennylane_ledger_event_id = ledger_id
            export.pennylane_exported_at = datetime.now(timezone.utc)
            export.pennylane_error = None
            export.status = ExportStatus.exported
            _log.info("Pennylane export OK — id=%s", ledger_id)
        except (PennylaneError, Exception) as exc:
            export.pennylane_error = str(exc)[:500]
            export.status = ExportStatus.failed
            _log.error("Pennylane export failed: %s", exc)

    # ── Alerte écart de caisse ───────────────────────────────────────────────

    async def _send_discrepancy_alert(
        self, export: AccountingExport, cfg: AccountingConfig
    ) -> None:
        email_to = cfg.discrepancy_alert_email or cfg.daily_report_email
        if not email_to:
            return
        try:
            from app.services.email_gateway import EmailMessage, send_email
            delta = export.cash_discrepancy or 0
            sign = "+" if delta >= 0 else ""
            html = f"""
<p><strong>⚠️ Alerte écart de caisse — {export.export_date}</strong></p>
<p>Écart détecté : <strong>{sign}{delta:.2f} €</strong></p>
<ul>
  <li>Montant attendu : {export.cash_expected:.2f} € </li>
  <li>Montant compté : {export.cash_counted:.2f} €</li>
  <li>Seuil configuré : ±{float(cfg.discrepancy_alert_threshold):.2f} €</li>
</ul>
<p>Veuillez vérifier la caisse avant de valider la clôture.</p>
"""
            send_email(
                EmailMessage(
                    to=email_to,
                    subject=f"⚠️ Vintiz — Écart de caisse {sign}{delta:.2f}€ ({export.export_date})",
                    html=html,
                    tags=["accounting", "discrepancy-alert"],
                )
            )
        except Exception as exc:
            _log.warning("Discrepancy alert email failed: %s", exc)

    # ── Email rapport quotidien ───────────────────────────────────────────────

    async def _send_daily_email(
        self,
        export: AccountingExport,
        z_report: ZReport,
        drawer: CashDrawer,
        cfg: AccountingConfig,
    ) -> None:
        try:
            from app.services.email_gateway import EmailMessage, send_email

            date_str = export.export_date.strftime("%d/%m/%Y")
            pennylane_status = (
                "✅ Exporté vers Pennylane"
                if export.status == ExportStatus.exported
                else ("❌ Échec Pennylane — à re-exporter" if export.status == ExportStatus.failed else "📄 Fichier FEC généré")
            )
            discrepancy_html = ""
            if export.cash_discrepancy is not None:
                delta = export.cash_discrepancy
                sign = "+" if delta >= 0 else ""
                color = "#16a34a" if abs(delta) <= float(cfg.discrepancy_alert_threshold) else "#dc2626"
                discrepancy_html = f"""
<tr>
  <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">Écart de caisse</td>
  <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;font-weight:bold;color:{color};">{sign}{delta:.2f} €</td>
</tr>"""

            html = f"""
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><title>Rapport Vintiz</title></head>
<body style="font-family:Manrope,sans-serif;background:#F6F5F1;padding:24px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;">
  <div style="text-align:center;margin-bottom:24px;">
    <img src="https://vintiz.fr/logo-teal.png" alt="Vintiz" style="height:40px;" />
    <h1 style="font-size:20px;color:#0E0E0C;margin:12px 0 4px;">Rapport de clôture</h1>
    <p style="color:#8B8B86;margin:0;">{date_str} — Z-Report N°{z_report.report_number:04d}</p>
  </div>

  <table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
    <tr style="background:#F6F5F1;">
      <td colspan="2" style="padding:8px 12px;font-weight:bold;color:#4A4A47;">Activité du jour</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">CA net TTC</td>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;font-weight:bold;color:#0B7A6A;">{export.net_ttc:.2f} €</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">Ventes brutes TTC</td>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">{export.total_sales_ttc:.2f} €</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">Remboursements</td>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;color:#dc2626;">−{export.total_refunds_ttc:.2f} €</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">Transactions</td>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">{export.transaction_count} ventes · {export.refund_count} remboursements</td>
    </tr>
    {discrepancy_html}
  </table>

  <table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
    <tr style="background:#F6F5F1;">
      <td colspan="2" style="padding:8px 12px;font-weight:bold;color:#4A4A47;">Répartition encaissements</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">Espèces</td>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">{export.cash_total:.2f} €</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">CB SumUp</td>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">{export.card_total:.2f} €</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">Chèques</td>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">{export.cheque_total + export.cheque_cdc_total:.2f} €</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">Avoirs</td>
      <td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;">{export.avoir_total:.2f} €</td>
    </tr>
  </table>

  <div style="background:#F6F5F1;border-radius:8px;padding:16px;margin-bottom:24px;">
    <p style="margin:0;font-weight:bold;color:#0E0E0C;">Comptabilité</p>
    <p style="margin:4px 0 0;color:#4A4A47;">{pennylane_status}</p>
    <p style="margin:4px 0 0;color:#8B8B86;font-size:13px;">FEC : {export.fec_filename or "non généré"}</p>
  </div>

  {f'''<div style="background:#F0F9FF;border-radius:8px;padding:16px;margin-bottom:24px;">
    <p style="margin:0;font-weight:bold;color:#0E0E0C;">Réconciliation SumUp</p>
    <p style="margin:4px 0 0;color:{"#16a34a" if abs(export.reconciliation_delta or 0) < 0.01 else "#dc2626"};">
      Écart CB : {"✓ 0,00 €" if abs(export.reconciliation_delta or 0) < 0.01 else f"{("+") if (export.reconciliation_delta or 0) >= 0 else ""}{export.reconciliation_delta:.2f} €"}
      · {export.reconciliation_matched or 0} rapprochés
      {f"· ⚠️ {export.reconciliation_unmatched_vintiz} Vintiz sans contrepartie" if export.reconciliation_unmatched_vintiz else ""}
      {f"· ⚠️ {export.reconciliation_unmatched_sumup} SumUp sans contrepartie" if export.reconciliation_unmatched_sumup else ""}
    </p>
  </div>''' if export.reconciliation_ran else ""}

  <p style="font-size:12px;color:#8B8B86;text-align:center;margin:0;">
    Vintiz Vernon · Boutique de seconde main premium<br>
    Ce rapport est généré automatiquement à chaque clôture de caisse.
  </p>
</div>
</body>
</html>"""

            send_email(
                EmailMessage(
                    to=cfg.daily_report_email,
                    subject=f"Vintiz — Clôture {date_str} · {export.net_ttc:.2f} € net · Z{z_report.report_number:04d}",
                    html=html,
                    tags=["accounting", "daily-report"],
                    idempotency_key=f"daily-report-{export.id}",
                )
            )
            export.email_sent_at = datetime.now(timezone.utc)
            export.email_sent_to = cfg.daily_report_email
        except Exception as exc:
            _log.warning("Daily accounting email failed: %s", exc)

    # ── FEC mensuel (feature A) ──────────────────────────────────────────────

    async def generate_monthly_fec(self, year: int, month: int) -> str:
        """Génère un FEC mensuel agrégé de tous les exports du mois."""
        from calendar import monthrange
        cfg = await self.get_config()

        last_day = monthrange(year, month)[1]
        date_from = date(year, month, 1)
        date_to = date(year, month, last_day)

        stmt = (
            select(AccountingExport)
            .where(AccountingExport.export_date >= date_from)
            .where(AccountingExport.export_date <= date_to)
            .order_by(AccountingExport.export_date.asc())
        )
        result = await self.db.execute(stmt)
        exports = list(result.scalars().all())

        if not exports:
            return "\t".join(_FEC_COLUMNS) + "\n"

        rows = ["\t".join(_FEC_COLUMNS)]
        ecriture_num = 1
        for exp in exports:
            if not exp.fec_content:
                continue
            for line in exp.fec_content.splitlines()[1:]:  # skip header
                rows.append(line)
                ecriture_num += 1

        return "\n".join(rows)
