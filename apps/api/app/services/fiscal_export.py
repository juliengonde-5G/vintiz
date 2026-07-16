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
    Transaction,
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
        merchant_name: str = "Vintiz Vernon",
        merchant_id: str = "",
    ) -> dict:
        """Return a Python dict describing the period — feeds both encoders."""
        # Load transactions in the window, sorted by created_at ascending
        # (chain order). Pre-load items + payments via selectin relations.
        tx_query = select(Transaction)
        if period_from is not None:
            tx_query = tx_query.where(Transaction.created_at >= period_from)
        if period_to is not None:
            tx_query = tx_query.where(Transaction.created_at < period_to)
        tx_query = tx_query.order_by(Transaction.transaction_number.asc())
        tx_result = await self.db.execute(tx_query)
        transactions = tx_result.scalars().all()

        # Same window for Z reports.
        z_query = select(ZReport)
        if period_from is not None:
            z_query = z_query.where(ZReport.created_at >= period_from)
        if period_to is not None:
            z_query = z_query.where(ZReport.created_at < period_to)
        z_query = z_query.order_by(ZReport.report_number.asc())
        z_result = await self.db.execute(z_query)
        z_reports = z_result.scalars().all()

        snapshot = {
            "version": "2.0",
            "format": "vintiz-nf525-export",
            "merchant_name": merchant_name,
            "merchant_id": merchant_id,
            "period_from": _iso(period_from),
            "period_to": _iso(period_to),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "notice_fr": (
                "Archive fiscale Vintiz en JSON ouvert. Les transactions et "
                "clôtures Z sont ordonnées par numéro. Les champs hash_chain, "
                "previous_hash et signature_version permettent de contrôler "
                "le chaînage; les lignes et paiements constituent les données "
                "élémentaires. Les montants sont exprimés en euros TTC."
            ),
            "totals": {
                "sales_count": sum(
                    1 for t in transactions if t.transaction_type == TransactionType.sale
                ),
                "refunds_count": sum(
                    1 for t in transactions if t.transaction_type == TransactionType.refund
                ),
                "transactions_count": len(transactions),
                "z_reports_count": len(z_reports),
                "sales_ttc": _fmt(sum(
                    float(t.total_ttc) for t in transactions
                    if t.transaction_type == TransactionType.sale
                )),
                "refunds_ttc": _fmt(sum(
                    float(t.total_ttc) for t in transactions
                    if t.transaction_type == TransactionType.refund
                )),
                "net_ttc": _fmt(
                    sum(
                        float(t.total_ttc) for t in transactions
                        if t.transaction_type == TransactionType.sale
                    )
                    - sum(
                        float(t.total_ttc) for t in transactions
                        if t.transaction_type == TransactionType.refund
                    )
                ),
            },
            "transactions": [self._tx_dict(t) for t in transactions],
            "z_reports": [self._z_dict(z) for z in z_reports],
        }
        return snapshot

    def _tx_dict(self, t: Transaction) -> dict:
        return {
            "id": str(t.id),
            "number": t.transaction_number,
            "type": t.transaction_type.value,
            "created_at": _iso(t.created_at),
            "user_id": str(t.user_id) if t.user_id else None,
            "cashier_id": str(t.cashier_id) if t.cashier_id else None,
            "client_id": str(t.client_id) if t.client_id else None,
            "client_uuid": str(t.client_uuid) if t.client_uuid else None,
            "original_transaction_id": str(t.original_transaction_id)
            if t.original_transaction_id
            else None,
            "refund_reason": t.refund_reason,
            "is_invoice": bool(t.is_invoice),
            "invoice_number": t.invoice_number,
            "client_siret": t.client_siret,
            "client_company_name": t.client_company_name,
            "client_billing_address": t.client_billing_address,
            "template_id": str(t.template_id) if t.template_id else None,
            "total_ht": _fmt(t.total_ht),
            "total_tva": _fmt(t.total_tva),
            "total_ttc": _fmt(t.total_ttc),
            "signature_version": int(t.fiscal_signature_version or 1),
            "previous_hash": t.previous_hash,
            "hash_chain": t.hash_chain,
            "items": [
                {
                    "product_id": str(it.product_id) if it.product_id else None,
                    "permanent_item_id": (
                        str(it.permanent_item_id) if it.permanent_item_id else None
                    ),
                    "original_transaction_item_id": (
                        str(it.original_transaction_item_id)
                        if it.original_transaction_item_id else None
                    ),
                    "product_name": it.product_name,
                    "quantity": it.quantity,
                    "unit_price": _fmt(it.unit_price),
                    "discount_percent": _fmt(it.discount_percent or 0),
                    "line_total": _fmt(it.line_total),
                    "promotional": bool(it.promotional),
                    "tva_rate": _fmt(it.tva_rate),
                }
                for it in (t.items or [])
            ],
            "payments": [
                {
                    "method": p.method.value,
                    "amount": _fmt(p.amount),
                    "tendered_amount": (
                        _fmt(p.tendered_amount)
                        if p.tendered_amount is not None else None
                    ),
                    "sumup_checkout_id": p.sumup_checkout_id,
                    "sumup_transaction_id": p.sumup_transaction_id,
                    "sumup_transaction_code": p.sumup_transaction_code,
                    "sumup_auth_code": p.sumup_auth_code,
                    "sumup_card_brand": p.sumup_card_brand,
                    "sumup_card_last4": p.sumup_card_last4,
                    "sumup_environment": p.sumup_environment,
                }
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
            "first_transaction_number": z.first_transaction_number,
            "last_transaction_number": z.last_transaction_number,
            "last_transaction_hash": z.last_transaction_hash,
            "payment_totals": z.payment_totals or {},
            "signature_version": int(z.fiscal_signature_version or 1),
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
                "id": tx["id"],
                "type": tx["type"],
                "created_at": tx["created_at"],
                "total_ht": tx["total_ht"],
                "total_tva": tx["total_tva"],
                "total_ttc": tx["total_ttc"],
                "hash_chain": tx["hash_chain"] or "",
                "previous_hash": tx["previous_hash"] or "",
                "signature_version": str(tx["signature_version"]),
                "is_invoice": str(tx["is_invoice"]).lower(),
            })
            if tx["cashier_id"]:
                tx_el.set("cashier_id", tx["cashier_id"])
            if tx["user_id"]:
                tx_el.set("user_id", tx["user_id"])
            if tx["client_id"]:
                tx_el.set("client_id", tx["client_id"])
            if tx["client_uuid"]:
                tx_el.set("client_uuid", tx["client_uuid"])
            if tx["original_transaction_id"]:
                tx_el.set(
                    "original_transaction_id", tx["original_transaction_id"]
                )
            if tx["refund_reason"]:
                tx_el.set("refund_reason", tx["refund_reason"])
            if tx["invoice_number"] is not None:
                tx_el.set("invoice_number", str(tx["invoice_number"]))
            if tx["client_siret"]:
                tx_el.set("client_siret", tx["client_siret"])
            if tx["client_company_name"]:
                tx_el.set("client_company_name", tx["client_company_name"])
            if tx["client_billing_address"]:
                tx_el.set("client_billing_address", tx["client_billing_address"])
            if tx["template_id"]:
                tx_el.set("template_id", tx["template_id"])

            items_el = SubElement(
                tx_el, "Items", {"count": str(len(tx["items"]))}
            )
            for it in tx["items"]:
                SubElement(items_el, "Item", {
                    "product_id": it["product_id"] or "",
                    "permanent_item_id": it["permanent_item_id"] or "",
                    "original_transaction_item_id": it["original_transaction_item_id"] or "",
                    "product_name": it["product_name"] or "",
                    "quantity": str(it["quantity"]),
                    "unit_price": it["unit_price"],
                    "discount_percent": it["discount_percent"],
                    "line_total": it["line_total"],
                    "promotional": str(it["promotional"]).lower(),
                    "tva_rate": it["tva_rate"],
                })

            pays_el = SubElement(
                tx_el, "Payments", {"count": str(len(tx["payments"]))}
            )
            for p in tx["payments"]:
                payment_attrs = {
                    "method": p["method"],
                    "amount": p["amount"],
                    "tendered_amount": p["tendered_amount"] or "",
                    "sumup_checkout_id": p["sumup_checkout_id"] or "",
                    "sumup_transaction_id": p["sumup_transaction_id"] or "",
                    "sumup_transaction_code": p["sumup_transaction_code"] or "",
                    "sumup_auth_code": p["sumup_auth_code"] or "",
                    "sumup_card_brand": p["sumup_card_brand"] or "",
                    "sumup_card_last4": p["sumup_card_last4"] or "",
                    "sumup_environment": p["sumup_environment"] or "",
                }
                SubElement(pays_el, "Payment", payment_attrs)

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
                "first_transaction_number": str(z["first_transaction_number"] or ""),
                "last_transaction_number": str(z["last_transaction_number"] or ""),
                "last_transaction_hash": z["last_transaction_hash"] or "",
                "signature_version": str(z["signature_version"]),
                "hash": z["hash"],
                "previous_hash": z["previous_hash"] or "",
            }
            if z["cashier_id"]:
                attrs["cashier_id"] = z["cashier_id"]
            if z["user_id"]:
                attrs["user_id"] = z["user_id"]
            z_el = SubElement(z_root, "ZReport", attrs)
            payments_el = SubElement(z_el, "PaymentTotals")
            for method, totals in z["payment_totals"].items():
                if isinstance(totals, dict):
                    SubElement(
                        payments_el,
                        "PaymentMethod",
                        {
                            "method": str(method),
                            "sales": str(totals.get("sales", "0.00")),
                            "refunds": str(totals.get("refunds", "0.00")),
                            "net": str(totals.get("net", "0.00")),
                        },
                    )
                else:  # legacy v1 Z reports
                    SubElement(
                        payments_el,
                        "PaymentMethod",
                        {"method": str(method), "net": str(totals)},
                    )

        # Pretty-print with a leading XML declaration for archive friendliness.
        xml_bytes = tostring(root, encoding="utf-8", xml_declaration=True)
        return xml_bytes.decode("utf-8")
