import hashlib
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import (
    CashDrawer,
    Transaction,
    TransactionType,
    ZReport,
)


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
    ) -> ZReport:
        """Generate an end-of-day Z report for a closed cash drawer.

        Computes daily totals and creates an immutable hash-chain entry.
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

        # Compute Z report hash
        hash_data = (
            f"{next_number}|"
            f"{float(total_sales):.2f}|"
            f"{float(total_refunds):.2f}|"
            f"{float(total_net):.2f}|"
            f"{sale_count}|"
            f"{previous_hash}"
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
        )
        self.db.add(z_report)
        await self.db.flush()
        await self.db.refresh(z_report)
        return z_report

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
                "total_sales": float(r.total_sales),
                "total_refunds": float(r.total_refunds),
                "total_net": float(r.total_net),
                "transaction_count": r.transaction_count,
                "hash": r.hash,
                "previous_hash": r.previous_hash,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ]
