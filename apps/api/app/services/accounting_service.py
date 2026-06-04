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

from sqlalchemy import delete, select, update
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


class FECImbalanceError(RuntimeError):
    """Levée quand l'écriture comptable ne s'équilibre pas (Σdébit ≠ Σcrédit)
    après l'application de la ligne d'ajustement. NF525 + obligations DGFiP :
    un FEC déséquilibré ne doit JAMAIS être produit. Plutôt que d'écrire un
    fichier illégal sur disque, on lève cette exception. Le caller (cron de
    clôture ou endpoint de régénération) la propage avec le contexte."""


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
        # Migration v1 → v2 : l'API v1 de Pennylane a été supprimée (2026) et
        # ``POST /journal_entries`` renvoie 404 (la ressource s'appelle
        # désormais ``ledger_entries`` côté v2). On bascule silencieusement
        # toute URL v1 résiduelle vers v2, sans intervention manuelle. Les URL
        # custom (autre domaine) sont laissées intactes.
        if cfg.pennylane_api_url and cfg.pennylane_api_url.rstrip("/").endswith("/external/v1"):
            cfg.pennylane_api_url = cfg.pennylane_api_url.rstrip("/")[:-1] + "2"
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

        # 6. Alerte écart de caisse
        if (
            acct_exp.cash_discrepancy is not None
            and abs(acct_exp.cash_discrepancy) > float(cfg.discrepancy_alert_threshold)
        ):
            await self._send_discrepancy_alert(acct_exp, cfg)
            acct_exp.discrepancy_alert_sent = True

        # 7. Générer le FEC quotidien
        fec = self._generate_fec(lines, z_report, export_date, cfg)
        acct_exp.fec_content = fec
        acct_exp.fec_filename = f"FEC_Vintiz_{export_date.strftime('%Y%m%d')}_Z{z_report.report_number:04d}.txt"
        acct_exp.fec_generated_at = datetime.now(timezone.utc)

        # 8. Verrouiller les transactions
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

        # 9. Export Pennylane (async best-effort)
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

    # ── Régénération du FEC (rejouer la ventilation comptable) ───────────────

    async def regenerate_export(
        self, export: AccountingExport, *, triggered_by_user_id=None
    ) -> AccountingExport:
        """Recalcule l'export à partir des transactions liées.

        Use case : un FEC a été généré avec une version buguée du moteur
        (ex. méthode de paiement voucher non mappée → débit < crédit). La
        chaîne fiscale NF525 (hash_chain des Tx) reste intacte : on ne
        rejoue PAS la clôture, on ne change PAS les transactions ; on
        recalcule juste la ventilation comptable (totaux par méthode +
        lignes d'écriture + fichier FEC) à partir des Tx déjà liées à cet
        export via ``Transaction.accounting_export_id``.

        Le ``hash_chain`` des Tx, les paiements, les items, le Z-report
        et la cash_drawer ne sont pas touchés. Seuls changent :
        - les colonnes de totaux sur ``AccountingExport``,
        - les lignes ``AccountingExportLine`` (anciennes supprimées),
        - ``fec_content`` / ``fec_generated_at``,
        - un audit log dédié.

        Refuse si les Tx liées ont disparu (intégrité). Refuse aussi si
        le résultat est déséquilibré (cf. _build_journal_lines → assert).
        """
        cfg = await self.get_config()

        # Récupérer les transactions liées à cet export.
        tx_result = await self.db.execute(
            select(Transaction)
            .where(Transaction.accounting_export_id == export.id)
            .order_by(Transaction.created_at.asc())
        )
        transactions = list(tx_result.scalars().all())
        if not transactions:
            raise ValueError(
                f"Impossible de régénérer l'export {export.id} : aucune "
                "transaction liée trouvée. Vérifier accounting_export_id."
            )

        # Charger le Z-report associé (pour le numéro + référence pièce).
        z_result = await self.db.execute(
            select(ZReport).where(ZReport.id == export.z_report_id)
        )
        z_report = z_result.scalar_one_or_none()
        if z_report is None:
            raise ValueError(
                f"Z-report {export.z_report_id} introuvable pour l'export {export.id}."
            )

        # Recalcul des totaux + lignes (utilise le moteur courant, donc avec
        # le mapping voucher et la balance refunds HT/TVA).
        totals = self._compute_totals(transactions)
        # _build_journal_lines lève FECImbalanceError si l'écriture reste
        # déséquilibrée après ajustement → on ne rentre PAS dans la base.
        new_lines = self._build_journal_lines(totals, cfg, z_report, export.export_date)

        # Mise à jour des totaux sur l'export (en place — pas de nouvelle ligne
        # AccountingExport pour préserver l'unicité par z_report_id).
        export.total_sales_ht = totals["sales_ht"]
        export.total_tva = totals["sales_tva"]
        export.total_sales_ttc = totals["sales_ttc"]
        export.total_refunds_ttc = totals["refunds_ttc"]
        export.net_ttc = totals["sales_ttc"] - totals["refunds_ttc"]
        export.transaction_count = totals["sale_count"]
        export.refund_count = totals["refund_count"]
        export.cash_total = totals["by_method"].get("cash", 0)
        export.card_total = totals["by_method"].get("card", 0)
        export.cheque_total = totals["by_method"].get("cheque", 0)
        export.cheque_cdc_total = totals["by_method"].get("cheque_cdc", 0)
        export.avoir_total = totals["by_method"].get("avoir", 0)
        export.transfer_total = totals["by_method"].get("transfer", 0)
        # Note : voucher_total n'a pas de colonne dédiée sur AccountingExport
        # — la ventilation est visible dans la ligne 4198 du FEC et dans le
        # détail AccountingExportLine. Pas de migration pour ce sprint.

        # Reset des lignes d'écriture : on supprime les anciennes (qui
        # correspondent à la ventilation buguée) et on ré-insère les neuves.
        await self.db.execute(
            delete(AccountingExportLine).where(AccountingExportLine.export_id == export.id)
        )
        for i, ln in enumerate(new_lines, start=1):
            self.db.add(
                AccountingExportLine(
                    export_id=export.id,
                    line_number=i,
                    account_number=ln.account_number,
                    account_label=ln.account_label,
                    debit=ln.debit,
                    credit=ln.credit,
                    label=ln.label,
                    piece_reference=f"Z{z_report.report_number:04d}",
                    piece_date=export.export_date,
                )
            )

        # Nouveau fichier FEC.
        fec = self._generate_fec(new_lines, z_report, export.export_date, cfg)
        export.fec_content = fec
        export.fec_filename = (
            f"FEC_Vintiz_{export.export_date.strftime('%Y%m%d')}_Z{z_report.report_number:04d}.txt"
        )
        export.fec_generated_at = datetime.now(timezone.utc)

        # Audit log de la régénération.
        from app.models.audit import AuditLog
        self.db.add(
            AuditLog(
                user_id=triggered_by_user_id,
                action="accounting.export.regenerate",
                entity="accounting_export",
                entity_id=export.id,
                data={
                    "z_report_id": str(export.z_report_id),
                    "tx_count": len(transactions),
                    "new_total_ttc": float(export.total_sales_ttc),
                    "new_cash_total": float(export.cash_total),
                    "new_card_total": float(export.card_total),
                    "lines": len(new_lines),
                },
            )
        )

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
        refunds_ht = 0.0
        refunds_tva = 0.0
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
                # On capte HT/TVA des remboursements pour pouvoir NETTER le
                # crédit (707/44571), sinon le débit (encaissements, qui
                # soustrait déjà les remboursements ligne 269) et le crédit
                # divergent du montant remboursé → écriture déséquilibrée.
                refunds_ht += float(txn.total_ht)
                refunds_tva += float(txn.total_tva)
                refunds_ttc += float(txn.total_ttc)
                refund_count += 1
                for p in (txn.payments or []):
                    by_method[p.method.value] = by_method.get(p.method.value, 0) - float(p.amount)

        return {
            "sales_ht": round(sales_ht, 2),
            "sales_tva": round(sales_tva, 2),
            "sales_ttc": round(sales_ttc, 2),
            "refunds_ht": round(refunds_ht, 2),
            "refunds_tva": round(refunds_tva, 2),
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
        # ``voucher`` (bons cadeaux) est une VRAIE ligne de paiement au POS
        # (la vente est encaissée à 100 % du TTC, le bon couvrant une part).
        # S'il manque ici, le débit perd le montant du bon alors que le crédit
        # (ventes HT+TVA = TTC) le contient → écriture déséquilibrée. On le
        # mappe sur un compte dédié (4198 « Bons cadeaux à honorer » par
        # défaut), surchargeable via la config si la colonne existe.
        method_map = {
            "cash": (cfg.account_cash, cfg.label_cash),
            "card": (cfg.account_card, cfg.label_card),
            "cheque": (cfg.account_cheque, cfg.label_cheque),
            "cheque_cdc": (cfg.account_cheque_cdc, cfg.label_cheque_cdc),
            "avoir": (cfg.account_avoir, cfg.label_avoir),
            "transfer": (cfg.account_transfer, cfg.label_transfer),
            "voucher": (
                getattr(cfg, "account_voucher", None) or "4198",
                getattr(cfg, "label_voucher", None) or "Bons cadeaux a honorer",
            ),
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

        # ── Crédit : ventes HT (707) NETTES des remboursements ───────────────
        # net_ht / net_tva soustraient le HT/TVA remboursé : le débit
        # d'encaissement nette déjà les remboursements (cf. _compute_totals),
        # donc le crédit doit en faire autant pour rester équilibré.
        net_ht = round(totals["sales_ht"] - totals.get("refunds_ht", 0.0), 2)
        net_tva = round(totals["sales_tva"] - totals.get("refunds_tva", 0.0), 2)

        if abs(net_ht) >= 0.005:
            lines.append(JournalEntryLine(
                account_number=cfg.account_sales,
                account_label=cfg.label_sales,
                debit=0 if net_ht > 0 else abs(net_ht),
                credit=net_ht if net_ht > 0 else 0,
                label=f"{cfg.label_sales} — {z_ref}",
            ))

        # ── Crédit : TVA collectée (44571) nette ──────────────────────────────
        if abs(net_tva) >= 0.005:
            lines.append(JournalEntryLine(
                account_number=cfg.account_tva,
                account_label=cfg.label_tva,
                debit=0 if net_tva > 0 else abs(net_tva),
                credit=net_tva if net_tva > 0 else 0,
                label=f"{cfg.label_tva} — {z_ref}",
            ))

        # ── Garde-fou d'équilibre : ligne d'ajustement d'arrondi ─────────────
        # Le FEC DOIT être équilibré (Σdébit == Σcrédit) sinon l'import
        # comptable (Pennylane / expert-comptable) refuse l'écriture. Après
        # construction, on mesure l'écart résiduel (typiquement quelques
        # centimes d'arrondi TVA cumulés) et on le résorbe sur un compte
        # 658/758 (charges/produits divers de gestion). Si l'écart dépasse
        # 1 €, c'est un bug de ventilation → on logge une erreur explicite
        # mais on équilibre quand même pour produire un FEC valide.
        total_debit = round(sum(ln.debit for ln in lines), 2)
        total_credit = round(sum(ln.credit for ln in lines), 2)
        diff = round(total_debit - total_credit, 2)
        if abs(diff) >= 0.01:
            if abs(diff) > 1.0:
                _log.error(
                    "FEC %s déséquilibre anormal: débit=%.2f crédit=%.2f écart=%.2f "
                    "(ventilation à revoir, ligne d'ajustement appliquée)",
                    z_ref, total_debit, total_credit, diff,
                )
            if diff > 0:
                # Débit > crédit → on crédite un produit divers (758)
                lines.append(JournalEntryLine(
                    account_number="758000",
                    account_label="Produits divers de gestion (arrondi)",
                    debit=0,
                    credit=abs(diff),
                    label=f"Ajustement equilibre — {z_ref}",
                ))
            else:
                # Crédit > débit → on débite une charge diverse (658)
                lines.append(JournalEntryLine(
                    account_number="658000",
                    account_label="Charges diverses de gestion (arrondi)",
                    debit=abs(diff),
                    credit=0,
                    label=f"Ajustement equilibre — {z_ref}",
                ))

        # Assert final : un FEC déséquilibré est REFUSÉ. La ligne d'ajustement
        # ci-dessus DOIT avoir résorbé l'écart ; si malgré tout on tombe sur
        # > 0,01 € résiduel (bug de calcul, ligne en NaN…), on lève une
        # exception explicite plutôt que de produire un fichier illégal.
        # NF525 + obligations DGFiP : pas de débit/crédit divergent toléré.
        post_debit = round(sum(ln.debit for ln in lines), 2)
        post_credit = round(sum(ln.credit for ln in lines), 2)
        if abs(post_debit - post_credit) >= 0.01:
            raise FECImbalanceError(
                f"FEC {z_ref} déséquilibré après ajustement : "
                f"débit={post_debit:.2f} crédit={post_credit:.2f} "
                f"écart={post_debit - post_credit:.2f}. Lignes : "
                + " | ".join(
                    f"{ln.account_number} D={ln.debit:.2f} C={ln.credit:.2f}"
                    for ln in lines
                )
            )

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
