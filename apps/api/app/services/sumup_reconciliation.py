"""SumUp ↔ Vintiz reconciliation service (feature C).

Fetches SumUp transactions for a given date and compares them with the
Vintiz Payment rows (method=card) so the accountant can spot discrepancies
before sending the FEC.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

_log = logging.getLogger("vintiz.reconciliation")

SUMUP_API_BASE = "https://api.sumup.com/v0.1"


@dataclass
class SumUpTx:
    transaction_id: str
    transaction_code: str
    amount: float
    currency: str
    status: str
    timestamp: str
    card_brand: str = ""
    card_last4: str = ""


@dataclass
class ReconciliationLine:
    vintiz_payment_id: str
    vintiz_transaction_number: int
    vintiz_amount: float
    sumup_transaction_id: str | None
    sumup_transaction_code: str | None
    sumup_amount: float | None
    status: str   # "matched" | "vintiz_only" | "sumup_only" | "amount_mismatch"
    delta: float = 0.0


@dataclass
class ReconciliationReport:
    reconciliation_date: str
    total_vintiz_card: float
    total_sumup: float
    delta: float
    matched_count: int
    unmatched_vintiz: int
    unmatched_sumup: int
    lines: list[ReconciliationLine] = field(default_factory=list)


class SumUpReconciliationService:
    def __init__(self, db) -> None:
        self.db = db

    def _get_sumup_api_key(self) -> str | None:
        try:
            from app.services.app_config import get_section
            s = get_section("sumup")
            key = (s.get("api_key") or "").strip()
            if key:
                return key
        except Exception:
            pass
        import os
        return os.getenv("SUMUP_API_KEY") or None

    def _fetch_sumup_transactions(
        self, api_key: str, target_date: date
    ) -> list[SumUpTx]:
        """Pull card transactions from SumUp for target_date."""
        import json
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError, URLError

        date_from = f"{target_date.isoformat()}T00:00:00Z"
        date_to = f"{target_date.isoformat()}T23:59:59Z"
        url = (
            f"{SUMUP_API_BASE}/me/transactions/history"
            f"?statuses=SUCCESSFUL&oldest_time={date_from}&newest_time={date_to}"
            f"&limit=100"
        )
        req = Request(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError) as exc:
            _log.warning("SumUp reconciliation fetch failed: %s", exc)
            return []

        items = data.get("items", [])
        result = []
        for item in items:
            result.append(
                SumUpTx(
                    transaction_id=item.get("id", ""),
                    transaction_code=item.get("transaction_code", ""),
                    amount=float(item.get("amount", 0)),
                    currency=item.get("currency", "EUR"),
                    status=item.get("status", ""),
                    timestamp=item.get("timestamp", ""),
                    card_brand=item.get("card", {}).get("brand", ""),
                    card_last4=item.get("card", {}).get("last_4_digits", ""),
                )
            )
        return result

    async def reconcile(self, target_date: date) -> ReconciliationReport:
        """Build a reconciliation report comparing Vintiz card payments vs SumUp."""
        from sqlalchemy import select
        from app.models.pos import Payment, PaymentMethod, Transaction, TransactionType

        api_key = self._get_sumup_api_key()

        # Load Vintiz card payments for target_date
        start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)
        stmt = (
            select(Payment, Transaction)
            .join(Transaction, Payment.transaction_id == Transaction.id)
            .where(Payment.method == PaymentMethod.card)
            .where(Transaction.transaction_type == TransactionType.sale)
            .where(Transaction.created_at >= start)
            .where(Transaction.created_at <= end)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        vintiz_payments = {
            p.sumup_transaction_id: (p, t)
            for p, t in rows
            if p.sumup_transaction_id
        }
        total_vintiz = sum(float(p.amount) for p, _ in rows)

        sumup_txs: list[SumUpTx] = []
        if api_key:
            sumup_txs = self._fetch_sumup_transactions(api_key, target_date)
        total_sumup = sum(tx.amount for tx in sumup_txs)
        sumup_by_id = {tx.transaction_id: tx for tx in sumup_txs}

        lines: list[ReconciliationLine] = []
        matched = 0
        unmatched_sumup = 0

        for payment, txn in rows:
            sumup_tx = sumup_by_id.get(payment.sumup_transaction_id or "")
            if sumup_tx:
                delta = round(float(payment.amount) - sumup_tx.amount, 2)
                status = "matched" if abs(delta) < 0.01 else "amount_mismatch"
                if status == "matched":
                    matched += 1
            else:
                delta = float(payment.amount)
                status = "vintiz_only"
            lines.append(
                ReconciliationLine(
                    vintiz_payment_id=str(payment.id),
                    vintiz_transaction_number=txn.transaction_number,
                    vintiz_amount=float(payment.amount),
                    sumup_transaction_id=payment.sumup_transaction_id,
                    sumup_transaction_code=payment.sumup_transaction_code,
                    sumup_amount=sumup_tx.amount if sumup_tx else None,
                    status=status,
                    delta=delta,
                )
            )

        matched_ids = {p.sumup_transaction_id for p, _ in rows if p.sumup_transaction_id}
        for tx in sumup_txs:
            if tx.transaction_id not in matched_ids:
                unmatched_sumup += 1
                lines.append(
                    ReconciliationLine(
                        vintiz_payment_id="",
                        vintiz_transaction_number=0,
                        vintiz_amount=0.0,
                        sumup_transaction_id=tx.transaction_id,
                        sumup_transaction_code=tx.transaction_code,
                        sumup_amount=tx.amount,
                        status="sumup_only",
                        delta=-tx.amount,
                    )
                )

        unmatched_vintiz = sum(1 for ln in lines if ln.status == "vintiz_only")

        return ReconciliationReport(
            reconciliation_date=target_date.isoformat(),
            total_vintiz_card=round(total_vintiz, 2),
            total_sumup=round(total_sumup, 2),
            delta=round(total_vintiz - total_sumup, 2),
            matched_count=matched,
            unmatched_vintiz=unmatched_vintiz,
            unmatched_sumup=unmatched_sumup,
            lines=lines,
        )
