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

    Styled with the Vintiz charte « Sauge Néo » : VINTIZ wordmark logo, teal
    accents, off-white panels, on an A4 page.
    """
    from pathlib import Path

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image as RLImage,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    # ---- Charte v3 « Sauge Néo » ----
    # Accent colour is template-driven (Tickets & Factures studio); falls back
    # to the charte teal when the template has no override or an invalid hex.
    _accent = "#0B7A6A"
    if template is not None and getattr(template, "accent_color", None):
        _accent = template.accent_color
    try:
        TEAL = colors.HexColor(_accent)
    except Exception:  # noqa: BLE001 — never fail an invoice on a bad colour
        TEAL = colors.HexColor("#0B7A6A")
    INK = colors.HexColor("#0E0E0C")
    INK_SOFT = colors.HexColor("#4A4A47")
    INK_MUTE = colors.HexColor("#8B8B86")
    CREAM = colors.HexColor("#F6F5F1")
    LINE = colors.HexColor("#D5D3CC")
    WHITE = colors.white

    CONTENT_W = 174 * mm  # A4 (210) minus 2×18 mm margins

    shop = _shop_info()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=_invoice_label(transaction),
    )

    styles = getSampleStyleSheet()
    wordmark = ParagraphStyle(
        "Wordmark", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=26, leading=28, textColor=TEAL, spaceAfter=0,
    )
    title_style = ParagraphStyle(
        "InvoiceTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=24, textColor=TEAL, alignment=2, spaceAfter=0,
    )
    meta_style = ParagraphStyle(
        "Meta", parent=styles["Normal"], fontSize=9, leading=13,
        textColor=INK_SOFT, alignment=2,
    )
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=12, textColor=INK)
    body_soft = ParagraphStyle("BodySoft", parent=body, textColor=INK_SOFT)
    body_small = ParagraphStyle(
        "BodySmall", parent=styles["Normal"], fontSize=7.5, leading=10, textColor=INK_MUTE
    )
    body_right = ParagraphStyle("BodyRight", parent=body, alignment=2)
    th = ParagraphStyle("TH", parent=body, fontName="Helvetica-Bold", textColor=WHITE)
    th_right = ParagraphStyle("THRight", parent=th, alignment=2)

    def _rule(color=TEAL, weight=1.2):
        t = Table([[""]], colWidths=[CONTENT_W], rowHeights=[1])
        t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), weight, color)]))
        return t

    story: list = []

    # ------------------------------------------------------------------
    # Header band — logo (or wordmark) + FACTURE title + meta
    # ------------------------------------------------------------------
    # Configurable company logo (Settings › Tickets & Factures) takes
    # precedence over the bundled wordmark asset.
    configured_logo = (shop.get("logo_path") or "").strip()
    logo_path = (
        Path(configured_logo)
        if configured_logo
        else Path(__file__).resolve().parent.parent / "assets" / "receipt-logo.png"
    )
    logo_flow: Any = None
    if logo_path.exists():
        try:
            from PIL import Image as PILImage

            with PILImage.open(logo_path) as im:
                iw, ih = im.size
            ratio = (ih / iw) if iw else 0.3
            lw = 42 * mm
            lh = lw * ratio
            if lh > 18 * mm:  # clamp height
                lh = 18 * mm
                lw = lh / ratio if ratio else 42 * mm
            logo_flow = RLImage(str(logo_path), width=lw, height=lh)
            logo_flow.hAlign = "LEFT"
        except Exception:  # noqa: BLE001 — never fail the invoice on a bad asset
            logo_flow = None
    if logo_flow is None:
        logo_flow = Paragraph("VINTIZ", wordmark)

    title_text = (template.title if template and template.title else "FACTURE")
    header = Table(
        [[logo_flow, Paragraph(title_text, title_style)]],
        colWidths=[94 * mm, 80 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header)

    invoice_label = _invoice_label(transaction)
    issued_at = transaction.created_at or datetime.utcnow()
    meta_html = " &nbsp;·&nbsp; ".join(
        [
            f"N° <b>{invoice_label}</b>",
            f"Date : {issued_at.strftime('%d/%m/%Y')}",
            f"Ticket lié : #{transaction.transaction_number}",
        ]
    )
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(meta_html, meta_style))
    story.append(Spacer(1, 3 * mm))
    story.append(_rule())
    story.append(Spacer(1, 5 * mm))

    # ------------------------------------------------------------------
    # Émetteur + Facturé à (side by side, buyer on a cream panel)
    # ------------------------------------------------------------------
    accent_tag = _accent.lstrip("#") or "0B7A6A"
    name_line = f"<b>{shop.get('name', 'Vintiz')}</b>"
    if shop.get("legal_form"):
        name_line += f" — {shop['legal_form']}"
    seller_lines = [
        f"<font color='#{accent_tag}'><b>ÉMETTEUR</b></font>",
        name_line,
        shop.get("tagline", ""),
        shop.get("address_line1", ""),
    ]
    if shop.get("address_line2"):
        seller_lines.append(shop["address_line2"])
    seller_lines.append(f"{shop.get('postal_code', '')} {shop.get('city', '')}".strip())
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
    if shop.get("tva_intracom"):
        seller_lines.append(f"TVA intracom. : {shop['tva_intracom']}")
    if shop.get("capital_social"):
        seller_lines.append(f"Capital : {shop['capital_social']}")
    seller_html = "<br/>".join(line for line in seller_lines if line)

    buyer_lines = [f"<font color='#{accent_tag}'><b>FACTURÉ À</b></font>"]
    if transaction.client_company_name:
        buyer_lines.append(f"<b>{transaction.client_company_name}</b>")
    if transaction.client_billing_address:
        for line in transaction.client_billing_address.splitlines():
            if line.strip():
                buyer_lines.append(line.strip())
    if transaction.client_siret:
        buyer_lines.append(f"SIRET : {transaction.client_siret}")
    if len(buyer_lines) == 1:
        buyer_lines.append("<i>Client comptant</i>")
    buyer_html = "<br/>".join(buyer_lines)

    parties = Table(
        [[Paragraph(seller_html, body_soft), Paragraph(buyer_html, body)]],
        colWidths=[90 * mm, 84 * mm],
    )
    parties.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (1, 0), (1, 0), CREAM),
                ("BOX", (1, 0), (1, 0), 0.5, LINE),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("LEFTPADDING", (1, 0), (1, 0), 8),
                ("RIGHTPADDING", (1, 0), (1, 0), 8),
                ("TOPPADDING", (1, 0), (1, 0), 8),
                ("BOTTOMPADDING", (1, 0), (1, 0), 8),
            ]
        )
    )
    story.append(parties)
    story.append(Spacer(1, 7 * mm))

    # Optional intro note (template-driven).
    if template is not None and getattr(template, "header_note", None):
        story.append(Paragraph(template.header_note, body_soft))
        story.append(Spacer(1, 4 * mm))

    # ------------------------------------------------------------------
    # Items table
    # ------------------------------------------------------------------
    item_rows: list[list[Any]] = [
        [
            Paragraph("Désignation", th),
            Paragraph("Qté", th_right),
            Paragraph("P.U. HT", th_right),
            Paragraph("Remise", th_right),
            Paragraph("Total HT", th_right),
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
        colWidths=[79 * mm, 13 * mm, 26 * mm, 22 * mm, 34 * mm],
        repeatRows=1,
    )
    item_style = [
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
    ]
    # Zebra striping on body rows for legibility.
    for r in range(1, len(item_rows)):
        if r % 2 == 0:
            item_style.append(("BACKGROUND", (0, r), (-1, r), CREAM))
    items_table.setStyle(TableStyle(item_style))
    story.append(items_table)
    story.append(Spacer(1, 6 * mm))

    # ------------------------------------------------------------------
    # Totals + VAT breakdown (right-aligned, TTC on a teal band)
    # ------------------------------------------------------------------
    total_ht = float(transaction.total_ht or 0)
    total_tva = float(transaction.total_tva or 0)
    total_ttc = float(transaction.total_ttc or 0)

    totals_rows = [["Total HT", _format_eur(total_ht)]]
    show_breakdown = bool(template and template.show_tva_breakdown) or True
    if show_breakdown:
        totals_rows.append([f"TVA {vat_rate:g} %", _format_eur(total_tva)])
    totals_rows.append(["Total TTC", _format_eur(total_ttc)])

    totals_table = Table(totals_rows, colWidths=[44 * mm, 34 * mm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TEXTCOLOR", (0, 0), (-1, -2), INK_SOFT),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                # TTC band
                ("BACKGROUND", (0, -1), (-1, -1), TEAL),
                ("TEXTCOLOR", (0, -1), (-1, -1), WHITE),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, -1), (-1, -1), 11),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(totals_table)
    story.append(Spacer(1, 9 * mm))

    # ------------------------------------------------------------------
    # Payment + footer
    # ------------------------------------------------------------------
    show_payment_block = (
        getattr(template, "show_payment_block", True) if template else True
    )
    payments = transaction.payments or []
    if show_payment_block and (payments or shop.get("iban")):
        pay_lines = [f"<font color='#{accent_tag}'><b>RÈGLEMENT</b></font>"]
        for p in payments:
            pay_lines.append(
                f"{_payment_method_label(p.method)} : {_format_eur(float(p.amount))}"
            )
        if template is not None and getattr(template, "payment_terms", None):
            pay_lines.append(template.payment_terms)
        if shop.get("iban"):
            bic = f" — BIC : {shop['bic']}" if shop.get("bic") else ""
            pay_lines.append(f"IBAN : {shop['iban']}{bic}")
        story.append(Paragraph("<br/>".join(pay_lines), body))
        story.append(Spacer(1, 5 * mm))

    if template and template.footer:
        story.append(Paragraph(template.footer, body_small))
        story.append(Spacer(1, 2 * mm))
    if template and template.conditions_retour:
        story.append(Paragraph(template.conditions_retour, body_small))
        story.append(Spacer(1, 2 * mm))
    show_legal = getattr(template, "show_legal_mentions", True) if template else True
    if show_legal and template and getattr(template, "legal_mentions", None):
        story.append(Paragraph(template.legal_mentions, body_small))
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 2 * mm))
    story.append(_rule(color=LINE, weight=0.5))
    story.append(Spacer(1, 2 * mm))

    # NF525 fiscal mention — required even when not legally compulsory yet for
    # the merchant tier; lets the auditor confirm the receipt is signed.
    nf_mention = (
        "Logiciel de caisse certifié NF525 — émission infalsifiable. "
        f"Empreinte SHA-256 : {(transaction.hash_chain or '')[:16]}…"
    )
    story.append(Paragraph(nf_mention, body_small))

    doc.build(story)
    return buf.getvalue()
