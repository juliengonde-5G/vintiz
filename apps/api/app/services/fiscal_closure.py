"""Periodic closure and self-contained fiscal archive generation."""

from __future__ import annotations

import gzip
import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fiscal_closure import FiscalClosure
from app.models.pos import CashDrawer, Transaction, TransactionType, ZReport
from app.services.fiscal import FiscalService
from app.services.fiscal_export import FiscalExportService
from app.version import APP_VERSION

SOFTWARE_VERSION = APP_VERSION
VALID_CLOSURE_TYPES = {"monthly", "annual", "perpetual"}


class FiscalClosureService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def close_period(
        self,
        *,
        closure_type: str,
        period_start: datetime,
        period_end: datetime,
        user_id: uuid.UUID | None,
    ) -> FiscalClosure:
        if closure_type not in VALID_CLOSURE_TYPES:
            raise HTTPException(status_code=400, detail="Type de clôture invalide")
        if period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=timezone.utc)
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=timezone.utc)
        if period_start >= period_end:
            raise HTTPException(status_code=400, detail="Période de clôture invalide")
        if period_end > datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Clôture future interdite")

        dialect = self.db.bind.dialect.name if self.db.bind else "postgresql"
        if dialect == "postgresql":
            await self.db.execute(text("SELECT pg_advisory_xact_lock(5252028)"))

        if closure_type == "perpetual":
            first_created = (
                await self.db.execute(select(func.min(Transaction.created_at)))
            ).scalar_one_or_none()
            if first_created is not None:
                period_start = first_created

        existing = (
            await self.db.execute(
                select(FiscalClosure).where(
                    FiscalClosure.closure_type == closure_type,
                    FiscalClosure.period_start == period_start,
                    FiscalClosure.period_end == period_end,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        open_drawer = (
            await self.db.execute(
                select(CashDrawer.id).where(CashDrawer.is_open.is_(True)).limit(1)
            )
        ).scalar_one_or_none()
        if open_drawer is not None:
            raise HTTPException(
                status_code=409,
                detail="Fermez la caisse avant de produire une clôture fiscale.",
            )

        fiscal = FiscalService(self.db)
        tx_integrity = await fiscal.verify_chain_integrity()
        z_integrity = await fiscal.verify_z_chain_integrity()
        if not tx_integrity["valid"] or not z_integrity["valid"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "fiscal_chain_invalid",
                    "transactions": tx_integrity,
                    "z_reports": z_integrity,
                },
            )

        txs = (
            await self.db.execute(
                select(Transaction)
                .where(
                    Transaction.created_at >= period_start,
                    Transaction.created_at < period_end,
                )
                .order_by(Transaction.transaction_number.asc())
            )
        ).scalars().all()
        z_reports = (
            await self.db.execute(
                select(ZReport)
                .where(
                    ZReport.created_at >= period_start,
                    ZReport.created_at < period_end,
                )
                .order_by(ZReport.report_number.asc())
            )
        ).scalars().all()

        snapshot = await FiscalExportService(self.db).build_snapshot(
            period_from=period_start,
            period_to=period_end,
        )
        snapshot["software_version"] = SOFTWARE_VERSION
        snapshot["integrity"] = {
            "transactions": tx_integrity,
            "z_reports": z_integrity,
        }
        raw_archive = FiscalService._canonical(snapshot)
        archive = gzip.compress(raw_archive, compresslevel=9, mtime=0)
        archive_sha = hashlib.sha256(archive).hexdigest()

        def _money(value: Decimal) -> str:
            return f"{value.quantize(Decimal('0.01')):.2f}"

        period_sales = sum(
            (Decimal(str(t.total_ttc)) for t in txs
             if t.transaction_type == TransactionType.sale),
            Decimal("0"),
        )
        period_refunds = sum(
            (Decimal(str(t.total_ttc)) for t in txs
             if t.transaction_type == TransactionType.refund),
            Decimal("0"),
        )
        perpetual_rows = (
            await self.db.execute(
                select(Transaction).where(Transaction.created_at < period_end)
            )
        ).scalars().all()
        perpetual_sales = sum(
            (Decimal(str(t.total_ttc)) for t in perpetual_rows
             if t.transaction_type == TransactionType.sale),
            Decimal("0"),
        )
        perpetual_refunds = sum(
            (Decimal(str(t.total_ttc)) for t in perpetual_rows
             if t.transaction_type == TransactionType.refund),
            Decimal("0"),
        )

        previous = (
            await self.db.execute(
                select(FiscalClosure)
                .order_by(FiscalClosure.sequence_number.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        previous_hash = previous.hash if previous else "0"
        sequence_number = (previous.sequence_number + 1) if previous else 1
        manifest = {
            "closure_type": closure_type,
            "sequence_number": sequence_number,
            "period_start": period_start.astimezone(timezone.utc).isoformat(),
            "period_end": period_end.astimezone(timezone.utc).isoformat(),
            "software_version": SOFTWARE_VERSION,
            "transaction_count": len(txs),
            "first_transaction_number": txs[0].transaction_number if txs else None,
            "last_transaction_number": txs[-1].transaction_number if txs else None,
            "last_transaction_hash": txs[-1].hash_chain if txs else None,
            "z_report_count": len(z_reports),
            "last_z_hash": z_reports[-1].hash if z_reports else None,
            "grand_total_period": {
                "sales_ttc": _money(period_sales),
                "refunds_ttc": _money(period_refunds),
                "net_ttc": _money(period_sales - period_refunds),
            },
            "total_perpetual": {
                "transactions_count": len(perpetual_rows),
                "sales_ttc": _money(perpetual_sales),
                "refunds_ttc": _money(perpetual_refunds),
                "net_ttc": _money(perpetual_sales - perpetual_refunds),
            },
            "archive_sha256": archive_sha,
            "previous_hash": previous_hash,
        }
        closure = FiscalClosure(
            sequence_number=sequence_number,
            closure_type=closure_type,
            period_start=period_start,
            period_end=period_end,
            software_version=SOFTWARE_VERSION,
            transaction_count=len(txs),
            first_transaction_number=manifest["first_transaction_number"],
            last_transaction_number=manifest["last_transaction_number"],
            last_transaction_hash=manifest["last_transaction_hash"],
            last_z_hash=manifest["last_z_hash"],
            previous_hash=previous_hash,
            hash=FiscalService._hmac(manifest),
            signature_version=1,
            archive_sha256=archive_sha,
            archive_content=archive,
            manifest=manifest,
            closed_by_user_id=user_id,
        )
        self.db.add(closure)
        await self.db.flush()
        await self.db.refresh(closure)
        return closure

    async def verify_chain(self) -> dict:
        rows = (
            await self.db.execute(
                select(FiscalClosure).order_by(FiscalClosure.sequence_number.asc())
            )
        ).scalars().all()
        previous_hash = "0"
        for closure in rows:
            if closure.previous_hash != previous_hash:
                return {
                    "valid": False,
                    "broken_at": closure.sequence_number,
                    "reason": "previous_hash_mismatch",
                }
            if hashlib.sha256(closure.archive_content).hexdigest() != closure.archive_sha256:
                return {
                    "valid": False,
                    "broken_at": closure.sequence_number,
                    "reason": "archive_sha256_mismatch",
                }
            if FiscalService._hmac(closure.manifest) != closure.hash:
                return {
                    "valid": False,
                    "broken_at": closure.sequence_number,
                    "reason": "signature_mismatch",
                }
            previous_hash = closure.hash
        return {"valid": True, "checked": len(rows)}

    @staticmethod
    def serialize(closure: FiscalClosure) -> dict:
        return {
            "id": str(closure.id),
            "sequence_number": closure.sequence_number,
            "closure_type": closure.closure_type,
            "period_start": closure.period_start.isoformat(),
            "period_end": closure.period_end.isoformat(),
            "software_version": closure.software_version,
            "transaction_count": closure.transaction_count,
            "first_transaction_number": closure.first_transaction_number,
            "last_transaction_number": closure.last_transaction_number,
            "last_transaction_hash": closure.last_transaction_hash,
            "last_z_hash": closure.last_z_hash,
            "previous_hash": closure.previous_hash,
            "hash": closure.hash,
            "archive_sha256": closure.archive_sha256,
            "manifest": closure.manifest,
            "created_at": closure.created_at.isoformat() if closure.created_at else None,
        }
