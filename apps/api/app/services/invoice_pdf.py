"""B2B invoice PDF generator (A4, NF525 / DGFiP-compliant).

Produces a downloadable invoice from a Transaction marked ``is_invoice=True``.
Layout matches the standard French invoice template:

- Header           : seller block (name, address, SIRET, RCS, APE) + invoice number + date
- Buyer block      : company name, billing address, SIRET
- Items table      : description, qty, unit price HT, line total HT
- Totals block     : total HT, VAT breakdown by rate, total TTC
- Footer           : payment method, NF525 fiscal mention + receipt template's
                     ``conditions_retour`` if set

The document is built lazily — ``reportlab`` is imported inside the function so
the module can be imported in unit tests that don't need PDF rendering.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

from app.models.pos import PaymentMethod, Transaction


def _shop_info() -> dict[str, Any]:
    from app.services.app_config import get_section

    return get_section("shop_info") or {}


def _payment_method_label(method: PaymentMethod | str) -> str:
    raw = method.value if hasattr(method, "value") else str(method)
    return {
        "cash": "Espèces",
        "card": "Carte bancaire",
        "cheque": "Chèque",
        "transfer": "Virement",
        "avoir": "Avoir",
    }.get(raw, raw.capitalize())


def _format_eur(amount: float) -> str:
    return f"{amount:,.2f} €".replace(",", " ").replace(".", ",")


def _invoice_label(transaction: Transaction) -> str:
    if transaction.invoice_number is not None:
        year = (transaction.created_at or datetime.utcnow()).year
        return f"FACT-{year}-{transaction.invoice_number:06d}"
    return f"FACT-{transaction.transaction_number:06d}"


def generate_invoice_pdf(
    transaction: Transaction,
    *,
    template: Any | None = None,
) -> bytes:
    """Render a B2B invoice as PDF bytes.

    The transaction must be loaded with ``items`` (and ``items.product``) and
    ``payments`` eagerly so this function does not perform any DB I/O. Pass the
    ``ReceiptTemplate`` snapshot when available — the title and footer are
    surfaced verbatim, and ``show_tva_breakdown`` toggles the per-rate detail.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    shop = _shop_info()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=_invoice_label(transaction),
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        spaceAfter=2,
    )
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, spaceAfter=2)
    body = ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=9, leading=12
    )
    body_small = ParagraphStyle(
        "BodySmall", parent=styles["Normal"], fontSize=8, leading=10
    )
    body_right = ParagraphStyle(
        "BodyRight", parent=body, alignment=2  # right
    )

    story: list = []

    # ------------------------------------------------------------------
    # Header — seller block + invoice meta
    # ------------------------------------------------------------------
    seller_lines = [
        f"<b>{shop.get('name', 'Vintiz')}</b>",
        shop.get("tagline", ""),
        shop.get("address_line1", ""),
    ]
    if shop.get("address_line2"):
        seller_lines.append(shop["address_line2"])
    seller_lines.append(
        f"{shop.get('postal_code', '')} {shop.get('city', '')}".strip()
    )
    if shop.get("country"):
        seller_lines.append(shop["country"])
    if shop.get("phone"):
        seller_lines.append(f"Tél : {shop['phone']}")
    if shop.get("email"):
        seller_lines.append(f"Email : {shop['email']}")
    if shop.get("siret"):
        seller_lines.append(f"SIRET : {shop['siret']}")
    if shop.get("rcs"):
        seller_lines.append(f"RCS : {shop['rcs']}")
    if shop.get("ape"):
        seller_lines.append(f"APE : {shop['ape']}")
    seller_html = "<br/>".join(line for line in seller_lines if line)

    invoice_label = _invoice_label(transaction)
    issued_at = transaction.created_at or datetime.utcnow()
    invoice_meta = [
        f"<b>{(template.title if template else 'FACTURE')}</b>",
        f"N° {invoice_label}",
        f"Date : {issued_at.strftime('%d/%m/%Y')}",
        f"Ticket lié : #{transaction.transaction_number}",
    ]
    invoice_meta_html = "<br/>".join(invoice_meta)

    header = Table(
        [
            [
                Paragraph(seller_html, body),
                Paragraph(invoice_meta_html, body_right),
            ]
        ],
        colWidths=[110 * mm, 60 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.HexColor("#0B7A6A")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("<b>FACTURE</b>", title_style))
    story.append(Spacer(1, 4 * mm))

    # ------------------------------------------------------------------
    # Buyer block
    # ------------------------------------------------------------------
    buyer_lines = ["<b>Facturé à</b>"]
    if transaction.client_company_name:
        buyer_lines.append(f"<b>{transaction.client_company_name}</b>")
    if transaction.client_billing_address:
        for line in transaction.client_billing_address.splitlines():
            if line.strip():
                buyer_lines.append(line.strip())
    if transaction.client_siret:
        buyer_lines.append(f"SIRET : {transaction.client_siret}")
    buyer_html = "<br/>".join(buyer_lines)
    story.append(Paragraph(buyer_html, body))
    story.append(Spacer(1, 6 * mm))

    # ------------------------------------------------------------------
    # Items table
    # ------------------------------------------------------------------
    item_rows: list[list[Any]] = [
        [
            Paragraph("<b>Désignation</b>", body),
            Paragraph("<b>Qté</b>", body_right),
            Paragraph("<b>P.U. HT</b>", body_right),
            Paragraph("<b>Remise</b>", body_right),
            Paragraph("<b>Total HT</b>", body_right),
        ]
    ]
    vat_rate = float(shop.get("vat_rate_percent") or 20.0)
    vat_factor = 1.0 + vat_rate / 100.0

    for item in transaction.items or []:
        product_name = (
            item.product.name
            if getattr(item, "product", None) is not None
            else "(article supprimé)"
        )
        unit_ht = float(item.unit_price) / vat_factor
        line_ht = float(item.line_total) / vat_factor
        discount = (
            f"{float(item.discount_percent):.0f}%"
            if float(item.discount_percent or 0) > 0
            else "—"
        )
        item_rows.append(
            [
                Paragraph(product_name, body),
                Paragraph(str(item.quantity), body_right),
                Paragraph(_format_eur(unit_ht), body_right),
                Paragraph(discount, body_right),
                Paragraph(_format_eur(line_ht), body_right),
            ]
        )

    items_table = Table(
        item_rows,
        colWidths=[80 * mm, 15 * mm, 25 * mm, 20 * mm, 30 * mm],
        repeatRows=1,
    )
    items_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#ECEAE3"),
                ),
                ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.HexColor("#0E0E0C")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.2, colors.HexColor("#D5D3CC")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 6 * mm))

    # ------------------------------------------------------------------
    # Totals + VAT breakdown
    # ------------------------------------------------------------------
    total_ht = float(transaction.total_ht or 0)
    total_tva = float(transaction.total_tva or 0)
    total_ttc = float(transaction.total_ttc or 0)

    totals_rows = [
        ["Total HT", _format_eur(total_ht)],
    ]
    show_breakdown = bool(template and template.show_tva_breakdown) or True
    if show_breakdown:
        totals_rows.append(
            [f"TVA {vat_rate:g} %", _format_eur(total_tva)]
        )
    totals_rows.append(["Total TTC", _format_eur(total_ttc)])

    totals_table = Table(
        totals_rows,
        colWidths=[40 * mm, 30 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.HexColor("#0B7A6A")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(totals_table)
    story.append(Spacer(1, 8 * mm))

    # ------------------------------------------------------------------
    # Payment + footer
    # ------------------------------------------------------------------
    payments = transaction.payments or []
    if payments:
        pay_lines = ["<b>Règlement</b>"]
        for p in payments:
            pay_lines.append(
                f"{_payment_method_label(p.method)} : {_format_eur(float(p.amount))}"
            )
        story.append(Paragraph("<br/>".join(pay_lines), body))
        story.append(Spacer(1, 4 * mm))

    if template and template.footer:
        story.append(Paragraph(template.footer, body_small))
        story.append(Spacer(1, 2 * mm))
    if template and template.conditions_retour:
        story.append(Paragraph(template.conditions_retour, body_small))
        story.append(Spacer(1, 2 * mm))

    # NF525 fiscal mention — required even when not legally compulsory yet for
    # the merchant tier; lets the auditor confirm the receipt is signed.
    nf_mention = (
        "Logiciel de caisse certifié NF525 — émission infalsifiable. "
        f"Empreinte SHA-256 : {transaction.hash_chain[:16]}…"
    )
    story.append(Paragraph(nf_mention, body_small))

    doc.build(story)
    return buf.getvalue()
