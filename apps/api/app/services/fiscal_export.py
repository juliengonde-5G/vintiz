"""DGFiP-friendly fiscal data export (P1-015 / closes P1-001).

Builds a self-contained snapshot of all transactions, payments, items and
Z reports over a period — including the SHA-256 hash chain — so a tax
inspector or accountant can verify the data wasn't tampered with.

Output formats:
- ``xml`` (default): structured tree, easy to read and to feed into FEC-style
  audit pipelines.
- ``json``: same structure, for programmatic consumers.

The export is *read-only*: it never mutates the chain or the underlying rows,
and re-runs over the same period produce byte-identical output (modulo the
``generated_at`` attribute, which is stripped in the test fixtures).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import (
    Payment,
    Transaction,
    TransactionItem,
    TransactionType,
    ZReport,
)


def _fmt(value) -> str:
    """Format a Decimal/float with 2 decimals, locale-neutral."""
    return f"{float(value):.2f}"


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


class FiscalExportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build_snapshot(
        self,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        merchant_name: str = "Frip & Co Vernon",
        merchant_id: str = "",
    ) -> dict:
        """Return a Python dict describing the period — feeds both encoders."""
        # Load transactions in the window, sorted by created_at ascending
        # (chain order). Pre-load items + payments via selectin relations.
        tx_query = select(Transaction)
        if period_from is not None:
            tx_query = tx_query.where(Transaction.created_at >= period_from)
        if period_to is not None:
            tx_query = tx_query.where(Transaction.created_at <= period_to)
        tx_query = tx_query.order_by(Transaction.created_at.asc())
        tx_result = await self.db.execute(tx_query)
        transactions = tx_result.scalars().all()

        # Same window for Z reports.
        z_query = select(ZReport)
        if period_from is not None:
            z_query = z_query.where(ZReport.created_at >= period_from)
        if period_to is not None:
            z_query = z_query.where(ZReport.created_at <= period_to)
        z_query = z_query.order_by(ZReport.created_at.asc())
        z_result = await self.db.execute(z_query)
        z_reports = z_result.scalars().all()

        snapshot = {
            "version": "1.0",
            "format": "vintiz-nf525-export",
            "merchant_name": merchant_name,
            "merchant_id": merchant_id,
            "period_from": _iso(period_from),
            "period_to": _iso(period_to),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "totals": {
                "sales_count": sum(
                    1 for t in transactions if t.transaction_type == TransactionType.sale
                ),
                "refunds_count": sum(
                    1 for t in transactions if t.transaction_type == TransactionType.refund
                ),
                "transactions_count": len(transactions),
                "z_reports_count": len(z_reports),
            },
            "transactions": [self._tx_dict(t) for t in transactions],
            "z_reports": [self._z_dict(z) for z in z_reports],
        }
        return snapshot

    def _tx_dict(self, t: Transaction) -> dict:
        return {
            "number": t.transaction_number,
            "type": t.transaction_type.value,
            "created_at": _iso(t.created_at),
            "user_id": str(t.user_id) if t.user_id else None,
            "cashier_id": str(t.cashier_id) if t.cashier_id else None,
            "client_id": str(t.client_id) if t.client_id else None,
            "original_transaction_id": str(t.original_transaction_id)
            if t.original_transaction_id
            else None,
            "refund_reason": t.refund_reason,
            "total_ht": _fmt(t.total_ht),
            "total_tva": _fmt(t.total_tva),
            "total_ttc": _fmt(t.total_ttc),
            "hash_chain": t.hash_chain,
            "items": [
                {
                    "product_id": str(it.product_id) if it.product_id else None,
                    "quantity": it.quantity,
                    "unit_price": _fmt(it.unit_price),
                    "discount_percent": _fmt(it.discount_percent or 0),
                    "line_total": _fmt(it.line_total),
                }
                for it in (t.items or [])
            ],
            "payments": [
                {"method": p.method.value, "amount": _fmt(p.amount)}
                for p in (t.payments or [])
            ],
        }

    def _z_dict(self, z: ZReport) -> dict:
        return {
            "number": z.report_number,
            "created_at": _iso(z.created_at),
            "user_id": str(z.user_id) if z.user_id else None,
            "cashier_id": str(z.cashier_id) if z.cashier_id else None,
            "cash_drawer_id": str(z.cash_drawer_id),
            "total_sales": _fmt(z.total_sales),
            "total_refunds": _fmt(z.total_refunds),
            "total_net": _fmt(z.total_net),
            "transaction_count": z.transaction_count,
            "hash": z.hash,
            "previous_hash": z.previous_hash,
        }

    # ------------------------------------------------------------------
    # Encoders
    # ------------------------------------------------------------------

    def to_json(self, snapshot: dict) -> str:
        return json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=False)

    def to_xml(self, snapshot: dict) -> str:
        root = Element("FiscalExport", attrib={
            "version": snapshot["version"],
            "format": snapshot["format"],
            "merchant_name": snapshot["merchant_name"],
            "merchant_id": snapshot["merchant_id"],
            "period_from": snapshot["period_from"],
            "period_to": snapshot["period_to"],
            "generated_at": snapshot["generated_at"],
        })

        totals = snapshot["totals"]
        SubElement(root, "Totals", {k: str(v) for k, v in totals.items()})

        tx_root = SubElement(
            root,
            "Transactions",
            {"count": str(len(snapshot["transactions"]))},
        )
        for tx in snapshot["transactions"]:
            tx_el = SubElement(tx_root, "Transaction", {
                "number": str(tx["number"]),
                "type": tx["type"],
                "created_at": tx["created_at"],
                "total_ht": tx["total_ht"],
                "total_tva": tx["total_tva"],
                "total_ttc": tx["total_ttc"],
                "hash_chain": tx["hash_chain"] or "",
            })
            if tx["cashier_id"]:
                tx_el.set("cashier_id", tx["cashier_id"])
            if tx["user_id"]:
                tx_el.set("user_id", tx["user_id"])
            if tx["client_id"]:
                tx_el.set("client_id", tx["client_id"])
            if tx["original_transaction_id"]:
                tx_el.set(
                    "original_transaction_id", tx["original_transaction_id"]
                )
            if tx["refund_reason"]:
                tx_el.set("refund_reason", tx["refund_reason"])

            items_el = SubElement(
                tx_el, "Items", {"count": str(len(tx["items"]))}
            )
            for it in tx["items"]:
                SubElement(items_el, "Item", {
                    "product_id": it["product_id"] or "",
                    "quantity": str(it["quantity"]),
                    "unit_price": it["unit_price"],
                    "discount_percent": it["discount_percent"],
                    "line_total": it["line_total"],
                })

            pays_el = SubElement(
                tx_el, "Payments", {"count": str(len(tx["payments"]))}
            )
            for p in tx["payments"]:
                SubElement(pays_el, "Payment", {
                    "method": p["method"],
                    "amount": p["amount"],
                })

        z_root = SubElement(
            root, "ZReports", {"count": str(len(snapshot["z_reports"]))}
        )
        for z in snapshot["z_reports"]:
            attrs = {
                "number": str(z["number"]),
                "created_at": z["created_at"],
                "cash_drawer_id": z["cash_drawer_id"],
                "total_sales": z["total_sales"],
                "total_refunds": z["total_refunds"],
                "total_net": z["total_net"],
                "transaction_count": str(z["transaction_count"]),
                "hash": z["hash"],
                "previous_hash": z["previous_hash"] or "",
            }
            if z["cashier_id"]:
                attrs["cashier_id"] = z["cashier_id"]
            if z["user_id"]:
                attrs["user_id"] = z["user_id"]
            SubElement(z_root, "ZReport", attrs)

        # Pretty-print with a leading XML declaration for archive friendliness.
        xml_bytes = tostring(root, encoding="utf-8", xml_declaration=True)
        return xml_bytes.decode("utf-8")
