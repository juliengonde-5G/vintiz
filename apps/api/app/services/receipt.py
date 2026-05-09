import os
from datetime import datetime, timezone
from typing import Any

from app.models.client import Client, LoyaltyAccount
from app.models.pos import Transaction, TransactionType
from app.services.offers_engine import points_to_credit


def _wrap_for_print(text: str, width: int) -> list[str]:
    """Coupe une chaîne en chunks de longueur ≤ width, sans casser de mot."""
    if len(text) <= width:
        return [text]
    chunks: list[str] = []
    current = ""
    for word in text.split():
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks


class ReceiptService:
    """Generate formatted receipt text for transactions."""

    STORE_NAME = "VINTIZ"
    STORE_ADDRESS = "6 rue Saint-Jacques, 27200 Vernon"

    def _resolve_header(self, template: Any | None) -> tuple[str, str]:
        """Return ``(title, address)`` lines, preferring the template + the
        persisted shop_info section over the hardcoded defaults."""
        try:
            from app.services.app_config import get_section

            shop = get_section("shop_info") or {}
        except Exception:
            shop = {}
        title = (template.title if template else "") or shop.get(
            "name", self.STORE_NAME
        )
        addr_parts = [
            shop.get("address_line1", ""),
            f"{shop.get('postal_code', '')} {shop.get('city', '')}".strip(),
        ]
        address = ", ".join(p for p in addr_parts if p) or self.STORE_ADDRESS
        return title.upper(), address

    def generate_receipt_text(
        self,
        transaction: Transaction,
        *,
        client: Client | None = None,
        loyalty_account: LoyaltyAccount | None = None,
        points_earned_on_sale: int | None = None,
        template: Any | None = None,
    ) -> str:
        """Dispatch to the sale or refund template based on transaction type.

        Optional ``client``/``loyalty_account``/``points_earned_on_sale``
        drive the new fidelity footer (PR1). When omitted, the receipt
        prints the legacy form (no footer) — useful for refunds and
        offline previews where the caller doesn't have the client loaded.
        """
        if transaction.transaction_type == TransactionType.refund:
            return self._generate_refund_text(transaction, template=template)
        return self._generate_sale_text(
            transaction,
            client=client,
            loyalty_account=loyalty_account,
            points_earned_on_sale=points_earned_on_sale,
            template=template,
        )

    def _generate_sale_text(
        self,
        transaction: Transaction,
        *,
        client: Client | None = None,
        loyalty_account: LoyaltyAccount | None = None,
        points_earned_on_sale: int | None = None,
        template: Any | None = None,
    ) -> str:
        """Create a formatted plain-text sale receipt.

        Includes store info, item list, totals, payment methods, the
        NF525 fiscal hash, and a fidelity footer (PR1):
        - members: name, V######, balance, points earned on this sale.
        - non-members: "Vous auriez gagné X pts" + adhesion CTA.
        """
        lines: list[str] = []
        width = 42

        # Header — prefer template title + persisted shop_info.
        title, address = self._resolve_header(template)
        lines.append(title.center(width))
        lines.append(address.center(width))
        lines.append("=" * width)

        # Transaction info
        dt = transaction.created_at or datetime.now(timezone.utc)
        is_invoice_flag = (
            getattr(transaction, "is_invoice", False) is True
        )
        invoice_no = getattr(transaction, "invoice_number", None)
        ticket_label = "Facture" if is_invoice_flag else "Ticket"
        lines.append(f"{ticket_label} #{transaction.transaction_number}")
        if is_invoice_flag and isinstance(invoice_no, int):
            lines.append(f"FACT-{dt.year}-{invoice_no:06d}")
            company = getattr(transaction, "client_company_name", None)
            siret = getattr(transaction, "client_siret", None)
            if isinstance(company, str) and company:
                buyer = company[: width - 1] if len(company) > width else company
                lines.append(buyer)
            if isinstance(siret, str) and siret:
                lines.append(f"SIRET : {siret}")
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

        # ---- Fidelity footer (gated by template) ------------------------------
        show_loyalty = template is None or bool(
            getattr(template, "show_loyalty_footer", True)
        )
        if show_loyalty:
            lines.append("")
            lines.append("--- Fidelite Vintiz ---".center(width))
            if client is not None and loyalty_account is not None:
                holder = (
                    f"{client.first_name} {client.last_name}".strip() or "Membre"
                )
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
        custom_footer = (template.footer if template else "") or ""
        if custom_footer.strip():
            for line in custom_footer.splitlines():
                stripped = line.strip()
                if not stripped:
                    lines.append("")
                else:
                    lines.append(stripped[:width].center(width))
        else:
            lines.append("Merci de votre visite !".center(width))

        # Avis Google — invitation post-achat (audit O5).
        # L'URL `https://g.page/r/{place_id}/review` redirige directement
        # vers le formulaire d'avis. Configurée via env GOOGLE_REVIEW_URL,
        # affichée seulement si le template ne l'a pas déjà incluse dans
        # son footer custom.
        review_url = os.getenv("GOOGLE_REVIEW_URL", "").strip()
        if review_url:
            lines.append("")
            lines.append("Votre avis compte beaucoup !".center(width))
            lines.append("Notez-nous sur Google :".center(width))
            # On scinde l'URL pour éviter une coupe au milieu sur 42 col.
            for chunk in _wrap_for_print(review_url, width):
                lines.append(chunk.center(width))
        lines.append("")

        return "\n".join(lines)

    def _generate_refund_text(
        self,
        transaction: Transaction,
        *,
        template: Any | None = None,
    ) -> str:
        """Refund receipt — visually distinct, references the original sale."""
        lines: list[str] = []
        width = 42

        title, address = self._resolve_header(template)
        lines.append(title.center(width))
        lines.append(address.center(width))
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
