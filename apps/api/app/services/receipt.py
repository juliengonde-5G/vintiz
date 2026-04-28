from datetime import datetime, timezone

from app.models.client import Client, LoyaltyAccount
from app.models.pos import Transaction, TransactionType
from app.services.offers_engine import points_to_credit


class ReceiptService:
    """Generate formatted receipt text for transactions."""

    STORE_NAME = "VINTIZ"
    STORE_ADDRESS = "6 rue Saint-Jacques, 27200 Vernon"

    def generate_receipt_text(
        self,
        transaction: Transaction,
        *,
        client: Client | None = None,
        loyalty_account: LoyaltyAccount | None = None,
        points_earned_on_sale: int | None = None,
    ) -> str:
        """Dispatch to the sale or refund template based on transaction type.

        Optional ``client``/``loyalty_account``/``points_earned_on_sale``
        drive the new fidelity footer (PR1). When omitted, the receipt
        prints the legacy form (no footer) — useful for refunds and
        offline previews where the caller doesn't have the client loaded.
        """
        if transaction.transaction_type == TransactionType.refund:
            return self._generate_refund_text(transaction)
        return self._generate_sale_text(
            transaction,
            client=client,
            loyalty_account=loyalty_account,
            points_earned_on_sale=points_earned_on_sale,
        )

    def _generate_sale_text(
        self,
        transaction: Transaction,
        *,
        client: Client | None = None,
        loyalty_account: LoyaltyAccount | None = None,
        points_earned_on_sale: int | None = None,
    ) -> str:
        """Create a formatted plain-text sale receipt.

        Includes store info, item list, totals, payment methods, the
        NF525 fiscal hash, and a fidelity footer (PR1):
        - members: name, V######, balance, points earned on this sale.
        - non-members: "Vous auriez gagné X pts" + adhesion CTA.
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

        # ---- Fidelity footer ---------------------------------------------------
        lines.append("")
        lines.append("--- Fidelite Vintiz ---".center(width))
        if client is not None and loyalty_account is not None:
            holder = f"{client.first_name} {client.last_name}".strip() or "Membre"
            if len(holder) > width:
                holder = holder[: width - 1]
            lines.append(f"Membre : {holder}")
            lines.append(f"N {loyalty_account.membership_number}")
            balance = int(loyalty_account.points or 0)
            earned = int(points_earned_on_sale or 0)
            balance_line = f"Solde : {balance} pts"
            if earned > 0:
                balance_line += f" (+{earned} sur cet achat)"
            lines.append(balance_line)
        else:
            would_earn = points_earned_on_sale
            if would_earn is None:
                would_earn = points_to_credit(float(total_ttc))
            if would_earn > 0:
                lines.append(f"Vous auriez gagne {would_earn} pts.")
            lines.append("Adherez gratuitement a votre prochain passage")
            lines.append("Carte digitale Apple/Google Wallet")

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
