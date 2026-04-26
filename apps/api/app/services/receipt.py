from datetime import datetime, timezone

from app.models.pos import Transaction, TransactionType


class ReceiptService:
    """Generate formatted receipt text for transactions."""

    STORE_NAME = "VINTIZ"
    STORE_ADDRESS = "6 rue Saint-Jacques, 27200 Vernon"

    def generate_receipt_text(self, transaction: Transaction) -> str:
        """Dispatch to the sale or refund template based on transaction type."""
        if transaction.transaction_type == TransactionType.refund:
            return self._generate_refund_text(transaction)
        return self._generate_sale_text(transaction)

    def _generate_sale_text(self, transaction: Transaction) -> str:
        """Create a formatted plain-text sale receipt.

        Includes store info, item list, totals, payment methods,
        and the NF525 fiscal hash for compliance.
        """
        lines: list[str] = []
        width = 42

        # Header
        lines.append(self.STORE_NAME.center(width))
        lines.append(self.STORE_ADDRESS.center(width))
        lines.append("=" * width)

        # Transaction info
        dt = transaction.created_at or datetime.now(timezone.utc)
        lines.append(f"Ticket #{transaction.transaction_number}")
        lines.append(f"Date: {dt.strftime('%d/%m/%Y %H:%M')}")
        lines.append("-" * width)

        # Items
        for item in (transaction.items or []):
            # Use the linked product's name when available, otherwise fall back
            # to a generic label (e.g. for free-form quick-sale lines).
            name = "Article"
            product = getattr(item, "product", None)
            if product and getattr(product, "name", None):
                name = product.name
            # Truncate long names so the line stays within the receipt width
            if len(name) > 28:
                name = name[:27] + "…"
            lines.append(f"{name:<28}{'':>14}")
            qty_price = f"  {item.quantity} x {float(item.unit_price):.2f}"
            total = f"{float(item.line_total):.2f} EUR"
            lines.append(f"{qty_price:<28}{total:>14}")

        lines.append("-" * width)

        # Totals
        total_ht = float(transaction.total_ht)
        total_tva = float(transaction.total_tva)
        total_ttc = float(transaction.total_ttc)

        lines.append(f"{'Total HT:':<28}{total_ht:>13.2f} EUR")
        lines.append(f"{'TVA 20%:':<28}{total_tva:>13.2f} EUR")
        lines.append(f"{'Total TTC:':<28}{total_ttc:>13.2f} EUR")
        lines.append("-" * width)

        # Payments
        for payment in (transaction.payments or []):
            method_label = payment.method.value.upper()
            amount = float(payment.amount)
            lines.append(f"{method_label:<28}{amount:>13.2f} EUR")

        # Change
        total_paid = sum(float(p.amount) for p in (transaction.payments or []))
        change = total_paid - total_ttc
        if change > 0:
            lines.append(f"{'RENDU:':<28}{change:>13.2f} EUR")

        lines.append("=" * width)

        # Fiscal hash (NF525 compliance)
        hash_display = transaction.hash_chain[:16] if transaction.hash_chain else ""
        lines.append(f"Hash: {hash_display}")
        lines.append("")
        lines.append("Merci de votre visite !".center(width))
        lines.append("")

        return "\n".join(lines)

    def _generate_refund_text(self, transaction: Transaction) -> str:
        """Refund receipt — visually distinct, references the original sale."""
        lines: list[str] = []
        width = 42

        lines.append(self.STORE_NAME.center(width))
        lines.append(self.STORE_ADDRESS.center(width))
        lines.append("=" * width)
        lines.append("** TICKET DE RETOUR **".center(width))
        lines.append("=" * width)

        dt = transaction.created_at or datetime.now(timezone.utc)
        lines.append(f"Retour #{transaction.transaction_number}")
        lines.append(f"Date: {dt.strftime('%d/%m/%Y %H:%M')}")
        if transaction.original_transaction_id:
            lines.append(
                f"Ref. vente d'origine: {str(transaction.original_transaction_id)[:8]}"
            )
        if transaction.refund_reason:
            reason = transaction.refund_reason
            if len(reason) > width - 8:
                reason = reason[: width - 9] + "…"
            lines.append(f"Motif: {reason}")
        lines.append("-" * width)

        for item in (transaction.items or []):
            name = "Article"
            product = getattr(item, "product", None)
            if product and getattr(product, "name", None):
                name = product.name
            if len(name) > 28:
                name = name[:27] + "…"
            lines.append(f"{name:<28}{'':>14}")
            qty_price = f"  {item.quantity} x {float(item.unit_price):.2f}"
            total = f"-{float(item.line_total):.2f} EUR"
            lines.append(f"{qty_price:<28}{total:>14}")

        lines.append("-" * width)

        total_ht = float(transaction.total_ht)
        total_tva = float(transaction.total_tva)
        total_ttc = float(transaction.total_ttc)
        lines.append(f"{'Total HT:':<28}{-total_ht:>13.2f} EUR")
        lines.append(f"{'TVA 20%:':<28}{-total_tva:>13.2f} EUR")
        lines.append(f"{'TOTAL REMBOURSE:':<28}{-total_ttc:>13.2f} EUR")
        lines.append("-" * width)

        for payment in (transaction.payments or []):
            method_label = payment.method.value.upper()
            amount = float(payment.amount)
            lines.append(f"{method_label + ' (rendu)':<28}{amount:>13.2f} EUR")

        # Note for avoir: settled via store credit, no Payment row.
        if not transaction.payments:
            lines.append(
                f"{'AVOIR (credit)':<28}{total_ttc:>13.2f} EUR".replace(
                    "AVOIR", "AVOIR client"
                )
            )

        lines.append("=" * width)

        hash_display = transaction.hash_chain[:16] if transaction.hash_chain else ""
        lines.append(f"Hash: {hash_display}")
        lines.append("")
        lines.append("Conservez ce ticket".center(width))
        lines.append("")

        return "\n".join(lines)
