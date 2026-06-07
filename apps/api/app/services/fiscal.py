import hashlib
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import (
    CashDrawer,
    Payment,
    PaymentMethod,
    Transaction,
    TransactionType,
    ZReport,
)

_log = logging.getLogger("vintiz")


class FiscalService:
    """NF525-compliant fiscal service.

    Maintains an unbroken SHA-256 hash chain across transactions and
    Z reports to guarantee data integrity and non-repudiation.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Transaction hash chain
    # ------------------------------------------------------------------

    async def sign_transaction(self, transaction: Transaction) -> None:
        """Compute and store the SHA-256 hash-chain entry for a transaction.

        hash = SHA256(transaction_number | total_ttc | created_at | previous_hash)
        """
        previous_hash = await self._get_previous_transaction_hash()
        data_string = (
            f"{transaction.transaction_number}|"
            f"{float(transaction.total_ttc):.2f}|"
            f"{transaction.created_at.isoformat() if transaction.created_at else ''}|"
            f"{previous_hash}"
        )
        transaction.hash_chain = hashlib.sha256(data_string.encode("utf-8")).hexdigest()
        await self.db.flush()

    async def _get_previous_transaction_hash(self) -> str:
        """Return the hash of the most recent transaction, or '0' if none."""
        result = await self.db.execute(
            select(Transaction.hash_chain)
            .where(Transaction.hash_chain != "")
            .order_by(Transaction.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row if row else "0"

    async def verify_chain_integrity(self) -> dict:
        """Verify the entire transaction hash chain is unbroken.

        Returns a dict with ``valid`` (bool) and ``checked`` (int) keys.
        If invalid, also returns ``broken_at`` with the transaction number.
        """
        result = await self.db.execute(
            select(Transaction).order_by(Transaction.created_at.asc())
        )
        transactions = result.scalars().all()

        previous_hash = "0"
        for t in transactions:
            data_string = (
                f"{t.transaction_number}|"
                f"{float(t.total_ttc):.2f}|"
                f"{t.created_at.isoformat() if t.created_at else ''}|"
                f"{previous_hash}"
            )
            expected = hashlib.sha256(data_string.encode("utf-8")).hexdigest()
            if t.hash_chain != expected:
                return {
                    "valid": False,
                    "checked": t.transaction_number,
                    "broken_at": t.transaction_number,
                }
            previous_hash = t.hash_chain

        return {"valid": True, "checked": len(transactions)}

    # ------------------------------------------------------------------
    # Z Reports
    # ------------------------------------------------------------------

    async def generate_z_report(
        self,
        drawer: CashDrawer,
        user_id: uuid.UUID,
        cashier_id: uuid.UUID | None = None,
        *,
        is_regularization: bool = False,
        regularization_reason: str | None = None,
    ) -> ZReport:
        """Generate an end-of-day Z report for a closed cash drawer.

        Computes daily totals and creates an immutable hash-chain entry.

        When ``is_regularization`` is set, the report is flagged as an
        a-posteriori regularization (a missed cash-drawer day). The flag is
        folded into the signed hash so the regularization scope is part of the
        non-repudiable record. The chain is built normally (real creation
        time, next number, off the latest Z hash) — nothing is antedated.
        """
        # Totals for transactions created during the drawer period
        sales_result = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.total_ttc), 0),
                func.count(Transaction.id),
            ).where(
                Transaction.transaction_type == TransactionType.sale,
                Transaction.created_at >= drawer.opened_at,
                Transaction.created_at <= (drawer.closed_at or func.now()),
            )
        )
        sales_row = sales_result.one()
        total_sales = Decimal(str(sales_row[0]))
        sale_count = sales_row[1]

        refunds_result = await self.db.execute(
            select(func.coalesce(func.sum(Transaction.total_ttc), 0)).where(
                Transaction.transaction_type == TransactionType.refund,
                Transaction.created_at >= drawer.opened_at,
                Transaction.created_at <= (drawer.closed_at or func.now()),
            )
        )
        total_refunds = Decimal(str(refunds_result.scalar_one()))
        total_net = total_sales - total_refunds

        # Report number
        max_num_result = await self.db.execute(
            select(func.coalesce(func.max(ZReport.report_number), 0))
        )
        next_number = max_num_result.scalar_one() + 1

        # Previous Z report hash
        prev_result = await self.db.execute(
            select(ZReport.hash)
            .order_by(ZReport.created_at.desc())
            .limit(1)
        )
        previous_hash = prev_result.scalar_one_or_none() or "0"

        # Compute Z report hash. Normal Z keep the historical format intact;
        # a regularization appends a signed marker so it can't be silently
        # reclassified as an ordinary daily close.
        hash_data = (
            f"{next_number}|"
            f"{float(total_sales):.2f}|"
            f"{float(total_refunds):.2f}|"
            f"{float(total_net):.2f}|"
            f"{sale_count}|"
            f"{previous_hash}"
        )
        if is_regularization:
            hash_data += (
                f"|REG|{drawer.opened_at.isoformat() if drawer.opened_at else ''}"
                f"|{drawer.closed_at.isoformat() if drawer.closed_at else ''}"
            )
        report_hash = hashlib.sha256(hash_data.encode("utf-8")).hexdigest()

        z_report = ZReport(
            report_number=next_number,
            user_id=user_id,
            cashier_id=cashier_id if cashier_id is not None else drawer.cashier_id,
            cash_drawer_id=drawer.id,
            total_sales=float(total_sales),
            total_refunds=float(total_refunds),
            total_net=float(total_net),
            transaction_count=sale_count,
            hash=report_hash,
            previous_hash=previous_hash,
            is_regularization=is_regularization,
            regularization_reason=regularization_reason,
        )
        self.db.add(z_report)
        await self.db.flush()
        await self.db.refresh(z_report)
        return z_report

    # ------------------------------------------------------------------
    # Régularisation a posteriori (jour de caisse oublié)
    # ------------------------------------------------------------------

    async def _classify_window(
        self, period_from: datetime, period_to: datetime
    ) -> dict:
        """Split the transactions of ``[period_from, period_to]`` into the ones
        already covered by an existing cash-drawer session and the *orphans*
        (covered by none). The orphans are what a regularization Z would book.
        """
        tx_rows = (
            await self.db.execute(
                select(Transaction).where(
                    Transaction.created_at >= period_from,
                    Transaction.created_at <= period_to,
                )
            )
        ).scalars().all()

        drawers = (
            await self.db.execute(
                select(CashDrawer).where(CashDrawer.opened_at <= period_to)
            )
        ).scalars().all()

        now = datetime.now(timezone.utc)

        def _aware(dt: datetime | None) -> datetime | None:
            # SQLite renvoie des datetimes naïfs même pour DateTime(timezone=True) ;
            # on les traite comme UTC pour des comparaisons homogènes.
            if dt is None:
                return None
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

        def _covered(created_at: datetime) -> bool:
            created_at = _aware(created_at)
            if created_at is None:
                return False
            for d in drawers:
                start = _aware(d.opened_at)
                end = _aware(d.closed_at) or now
                if start is not None and start <= created_at <= end:
                    return True
            return False

        orphans = [t for t in tx_rows if not _covered(t.created_at)]
        covered = [t for t in tx_rows if _covered(t.created_at)]
        return {"orphans": orphans, "covered": covered, "all": tx_rows}

    async def preview_regularization(
        self, period_from: datetime, period_to: datetime
    ) -> dict:
        """Dry-run a regularization over a date window. Returns the orphan
        transactions (uncovered by any session), their totals + payment-method
        breakdown, and flags any overlap with an existing session (which would
        cause double counting and therefore blocks the regularization)."""
        split = await self._classify_window(period_from, period_to)
        orphans = split["orphans"]
        orphan_ids = [t.id for t in orphans]

        open_drawers = (
            await self.db.execute(
                select(func.count()).select_from(
                    select(CashDrawer).where(CashDrawer.is_open.is_(True)).subquery()
                )
            )
        ).scalar_one()

        total_sales = sum(
            float(t.total_ttc) for t in orphans
            if t.transaction_type == TransactionType.sale
        )
        total_refunds = sum(
            float(t.total_ttc) for t in orphans
            if t.transaction_type == TransactionType.refund
        )
        sale_count = sum(
            1 for t in orphans if t.transaction_type == TransactionType.sale
        )

        by_method: dict[str, float] = {}
        if orphan_ids:
            rows = (
                await self.db.execute(
                    select(Payment.method, func.coalesce(func.sum(Payment.amount), 0))
                    .where(Payment.transaction_id.in_(orphan_ids))
                    .group_by(Payment.method)
                )
            ).all()
            for method, amount in rows:
                key = method.value if isinstance(method, PaymentMethod) else str(method)
                by_method[key] = float(amount)

        return {
            "period_from": period_from.isoformat(),
            "period_to": period_to.isoformat(),
            "orphan_count": len(orphans),
            "sale_count": sale_count,
            "covered_count": len(split["covered"]),
            "has_overlap": len(split["covered"]) > 0,
            "open_drawers_count": int(open_drawers),
            "can_regularize": len(orphans) > 0 and len(split["covered"]) == 0,
            "total_sales": round(total_sales, 2),
            "total_refunds": round(total_refunds, 2),
            "total_net": round(total_sales - total_refunds, 2),
            "by_method": by_method,
            "transaction_numbers": sorted(
                t.transaction_number for t in orphans
            )[:100],
        }

    async def close_open_drawers(
        self,
        user_id: uuid.UUID,
        cashier_id: uuid.UUID | None = None,
    ) -> list[ZReport]:
        """Clôture toute caisse restée ouverte et génère son Z (fiscal seul).

        Une session non clôturée bloque l'ouverture de la caisse du jour ET
        fausse la détection des ventes orphelines (sa fenêtre court jusqu'à
        maintenant, couvrant les journées suivantes). On la ferme à l'instant
        présent — comptage espèces non rejoué, écart non calculé — pour repartir
        sur une base saine avant une régularisation.
        """
        open_rows = (
            await self.db.execute(
                select(CashDrawer).where(CashDrawer.is_open.is_(True))
            )
        ).scalars().all()
        if not open_rows:
            return []

        now = datetime.now(timezone.utc)
        reports: list[ZReport] = []
        for drawer in open_rows:
            cash_sales = Decimal(str((await self.db.execute(
                select(func.coalesce(func.sum(Payment.amount), 0))
                .join(Transaction, Payment.transaction_id == Transaction.id)
                .where(
                    Payment.method == PaymentMethod.cash,
                    Transaction.created_at >= drawer.opened_at,
                    Transaction.transaction_type != TransactionType.refund,
                )
            )).scalar_one()))
            cash_refunds = Decimal(str((await self.db.execute(
                select(func.coalesce(func.sum(Payment.amount), 0))
                .join(Transaction, Payment.transaction_id == Transaction.id)
                .where(
                    Payment.method == PaymentMethod.cash,
                    Transaction.created_at >= drawer.opened_at,
                    Transaction.transaction_type == TransactionType.refund,
                )
            )).scalar_one()))
            expected = Decimal(str(drawer.opening_amount)) + cash_sales - cash_refunds

            drawer.closed_at = now
            drawer.is_open = False
            drawer.closing_amount = None  # fiscal seul — pas de recomptage
            drawer.expected_amount = float(expected)
            drawer.closing_note = (
                (drawer.closing_note + " | " if drawer.closing_note else "")
                + f"Clôturée automatiquement le {now.strftime('%d/%m/%Y %H:%M')} "
                "(UTC) lors d'une régularisation."
            )
            await self.db.flush()
            reports.append(
                await self.generate_z_report(drawer, user_id, cashier_id=cashier_id)
            )
        return reports

    async def create_regularization_z(
        self,
        period_from: datetime,
        period_to: datetime,
        reason: str,
        user_id: uuid.UUID,
        cashier_id: uuid.UUID | None = None,
    ) -> ZReport:
        """Establish an a-posteriori regularization Z for a missed cash day.

        Guards:
        - the motif is mandatory;
        - the window must contain at least one orphan transaction;
        - the window must NOT overlap an existing session (else booking it
          would double-count) → 409, narrow the window.

        A technical (regularization) cash-drawer carries the covered period;
        the Z is then produced via the standard signed pipeline.
        """
        reason = (reason or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="Motif de régularisation obligatoire")

        split = await self._classify_window(period_from, period_to)
        if split["covered"]:
            raise HTTPException(
                status_code=409,
                detail=(
                    "La période chevauche une session de caisse existante "
                    f"({len(split['covered'])} transaction(s) déjà couverte(s)). "
                    "Restreignez la plage pour ne viser que les ventes orphelines."
                ),
            )
        if not split["orphans"]:
            raise HTTPException(
                status_code=400,
                detail="Aucune transaction orpheline à régulariser sur cette période.",
            )

        # Espèces attendues sur la période (fond initial = 0 par construction).
        cash_expected = (
            await self.db.execute(
                select(func.coalesce(func.sum(Payment.amount), 0))
                .join(Transaction, Payment.transaction_id == Transaction.id)
                .where(
                    Payment.method == PaymentMethod.cash,
                    Transaction.created_at >= period_from,
                    Transaction.created_at <= period_to,
                )
            )
        ).scalar_one()

        now = datetime.now(timezone.utc)
        note = (
            f"Régularisation a posteriori — établie le {now.strftime('%d/%m/%Y %H:%M')} "
            f"(UTC). Comptage espèces non effectué (fiscal seul). Motif : {reason}"
        )
        drawer = CashDrawer(
            user_id=user_id,
            cashier_id=cashier_id,
            opened_at=period_from,
            closed_at=period_to,
            opening_amount=0,
            closing_amount=None,          # fiscal seul : pas de recomptage
            expected_amount=float(cash_expected),
            is_open=False,
            closing_note=note,
        )
        self.db.add(drawer)
        await self.db.flush()

        return await self.generate_z_report(
            drawer,
            user_id,
            cashier_id=cashier_id,
            is_regularization=True,
            regularization_reason=reason,
        )

    async def list_z_reports(
        self, skip: int = 0, limit: int = 30
    ) -> list[dict]:
        """Return a paginated list of Z reports."""
        result = await self.db.execute(
            select(ZReport)
            .order_by(ZReport.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        reports = result.scalars().all()
        return [
            {
                "id": str(r.id),
                "report_number": r.report_number,
                "cashier_id": str(r.cashier_id) if r.cashier_id else None,
                "is_regularization": bool(r.is_regularization),
                "regularization_reason": r.regularization_reason,
                "total_sales": float(r.total_sales),
                "total_refunds": float(r.total_refunds),
                "total_net": float(r.total_net),
                "transaction_count": r.transaction_count,
                "hash": r.hash,
                "previous_hash": r.previous_hash,
                "is_locked": bool(r.is_locked),
                "locked_at": r.locked_at.isoformat() if r.locked_at else None,
                "emailed_at": r.emailed_at.isoformat() if r.emailed_at else None,
                "emailed_to": r.emailed_to,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ]

    # ------------------------------------------------------------------
    # NF525 intangibility — lock + email
    # ------------------------------------------------------------------

    async def lock_z_report(
        self,
        z_report_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None,
    ) -> dict:
        """Lock a Z report intangibly (NF525 article 88 CGI).

        Idempotent — calling ``lock_z_report`` twice is safe and returns the
        same payload. Once locked:

        - ``is_locked = True`` + ``locked_at`` + ``locked_by_user_id``
        - the rendered PDF is persisted (``pdf_content``) along with its
          SHA-256 (``pdf_sha256``); any later regeneration produces the same
          bytes (the function is deterministic w.r.t. the immutable rows it
          aggregates)
        - the hash chain is captured in the PDF footer; further UPDATEs to
          totals are forbidden by the verify_chain_integrity check

        Raises ``HTTPException(404)`` if the report doesn't exist.
        """
        from app.services.z_report_pdf import generate_z_report_pdf

        z = (
            await self.db.execute(
                select(ZReport).where(ZReport.id == z_report_id)
            )
        ).scalar_one_or_none()
        if z is None:
            raise HTTPException(status_code=404, detail="Z report introuvable")

        if z.is_locked and z.pdf_content and z.pdf_sha256:
            return {
                "id": str(z.id),
                "report_number": z.report_number,
                "is_locked": True,
                "locked_at": z.locked_at.isoformat() if z.locked_at else None,
                "locked_by_user_id": (
                    str(z.locked_by_user_id) if z.locked_by_user_id else None
                ),
                "pdf_sha256": z.pdf_sha256,
                "already_locked": True,
            }

        pdf_bytes = await generate_z_report_pdf(self.db, z)
        sha = hashlib.sha256(pdf_bytes).hexdigest()

        z.is_locked = True
        z.locked_at = datetime.now(timezone.utc)
        z.locked_by_user_id = user_id
        z.pdf_content = pdf_bytes
        z.pdf_sha256 = sha
        await self.db.flush()

        return {
            "id": str(z.id),
            "report_number": z.report_number,
            "is_locked": True,
            "locked_at": z.locked_at.isoformat(),
            "locked_by_user_id": str(user_id) if user_id else None,
            "pdf_sha256": sha,
            "already_locked": False,
        }

    async def email_z_report(
        self,
        z_report_id: uuid.UUID,
        *,
        to: str | None,
        sender_user_id: uuid.UUID | None = None,
    ) -> dict:
        """Email the Z-report PDF (locked snapshot or live render) to a
        recipient. Defaults to the configured ``email.from_address`` when
        ``to`` is omitted so a forgotten address falls back to "self-email"
        rather than crash.
        """
        from app.services.app_config import get_section
        from app.services.email_gateway import (
            EmailDeliveryError,
            EmailMessage,
            send_email,
        )
        from app.services.z_report_pdf import generate_z_report_pdf

        z = (
            await self.db.execute(
                select(ZReport).where(ZReport.id == z_report_id)
            )
        ).scalar_one_or_none()
        if z is None:
            raise HTTPException(status_code=404, detail="Z report introuvable")

        target = (to or "").strip()
        if not target:
            target = (
                (get_section("email") or {}).get("from_address")
                or "noreply@vintiz.fr"
            )

        if z.is_locked and z.pdf_content:
            pdf_bytes = z.pdf_content
            sha = z.pdf_sha256 or hashlib.sha256(pdf_bytes).hexdigest()
        else:
            pdf_bytes = await generate_z_report_pdf(self.db, z)
            sha = hashlib.sha256(pdf_bytes).hexdigest()

        subject = f"Z report Vintiz #{z.report_number:04d}"
        text = (
            f"Bonjour,\n\n"
            f"Vous trouverez en pièce jointe le rapport Z #{z.report_number:04d} "
            f"du {(z.created_at or datetime.utcnow()).strftime('%d/%m/%Y')}.\n\n"
            f"Total ventes : {float(z.total_sales):.2f} EUR\n"
            f"Total remboursements : {float(z.total_refunds):.2f} EUR\n"
            f"Net : {float(z.total_net):.2f} EUR\n"
            f"Empreinte SHA-256 : {sha}\n\n"
            f"Vintiz — Conforme NF525 / article 88 CGI."
        )
        html = (
            f"<p>Bonjour,</p>"
            f"<p>Le rapport Z <b>#{z.report_number:04d}</b> est en pièce jointe.</p>"
            f"<ul>"
            f"<li>Ventes : {float(z.total_sales):.2f} EUR</li>"
            f"<li>Remboursements : {float(z.total_refunds):.2f} EUR</li>"
            f"<li>Net : {float(z.total_net):.2f} EUR</li>"
            f"<li>SHA-256 : <code>{sha}</code></li>"
            f"</ul>"
            f"<p>Vintiz — Conforme NF525.</p>"
        )
        message = EmailMessage(
            to=target,
            subject=subject,
            text=text,
            html=html,
            attachments=[
                {
                    "filename": f"Z-{z.report_number:04d}.pdf",
                    "content": pdf_bytes,
                    "mime": "application/pdf",
                }
            ],
        )
        try:
            outcome = send_email(message)
        except EmailDeliveryError as exc:
            _log.error("Z report %s email failed: %s", z.report_number, exc)
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        z.emailed_at = datetime.now(timezone.utc)
        z.emailed_to = target
        await self.db.flush()

        return {
            "id": str(z.id),
            "report_number": z.report_number,
            "emailed_to": target,
            "emailed_at": z.emailed_at.isoformat(),
            "backend": outcome.backend,
            "status": outcome.status,
            "pdf_sha256": sha,
        }
