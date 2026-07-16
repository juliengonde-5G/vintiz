"""Z report PDF generator (A4, NF525-compliant).

Renders the daily fiscal report a tax auditor expects to see:

- Header                : shop info + Z number + cashier + period
- Cash drawer block     : opening / closing breakdown by denomination,
                           expected vs counted, discrepancy alert in red
- Daily totals          : transactions per method (cash, CB, cheque, avoir),
                           sale count, refund count + amount
- Cash movements        : every in/out captured during the day with reason
- Hash chain            : current Z hash + previous Z hash (chain integrity)
- NF525 mention         : "Logiciel certifié — empreinte SHA-256 …"

Used by:
- ``GET /api/pos/z-reports/{id}/pdf`` — live or persisted snapshot
- ``FiscalService.lock_z_report`` — captured byte-identical at lock time
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cash_movement import CashMovement, CashMovementDirection
from app.models.pos import (
    CashDrawer,
    Payment,
    PaymentMethod,
    Transaction,
    TransactionType,
    ZReport,
)


def _shop_info() -> dict[str, Any]:
    from app.services.app_config import get_section

    return get_section("shop_info") or {}


def _format_eur(amount: float) -> str:
    return f"{amount:,.2f} €".replace(",", " ").replace(".", ",")


def _payment_method_label(method: PaymentMethod | str) -> str:
    raw = method.value if hasattr(method, "value") else str(method)
    return {
        "cash": "Espèces",
        "card": "Carte bancaire",
        "cheque": "Chèque",
        "cheque_cdc": "Chèque CDC",
        "transfer": "Virement",
        "avoir": "Avoir",
    }.get(raw, raw.capitalize())


def _reason_label(reason: str) -> str:
    return {
        "bank_deposit": "Dépôt banque",
        "supplier_payment": "Paiement fournisseur",
        "personal_withdrawal": "Prélèvement personnel",
        "float_top_up": "Réappro. fonds de caisse",
        "other": "Autre",
    }.get(reason, reason)


async def _aggregate_payment_totals(
    db: AsyncSession, drawer: CashDrawer
) -> dict[str, dict[str, float]]:
    """Sum payments per method, split by sale vs refund.

    Returns a dict like::

        {
            "cash":   {"sales": 230.0, "refunds": 0.0, "count": 4},
            "card":   {"sales": 410.5, "refunds": 0.0, "count": 7},
            ...
        }
    """
    out: dict[str, dict[str, float]] = {}
    methods_q = await db.execute(
        select(
            Payment.method,
            Transaction.transaction_type,
            func.sum(Payment.amount),
            func.count(Payment.id),
        )
        .join(Transaction, Payment.transaction_id == Transaction.id)
        .where(Transaction.created_at >= drawer.opened_at)
        .where(
            Transaction.created_at <= (drawer.closed_at or datetime.utcnow())
        )
        .group_by(Payment.method, Transaction.transaction_type)
    )
    for method, tx_type, total, count in methods_q.all():
        key = method.value if hasattr(method, "value") else str(method)
        bucket = out.setdefault(
            key, {"sales": 0.0, "refunds": 0.0, "count": 0}
        )
        amount = float(total or 0)
        n = int(count or 0)
        if tx_type == TransactionType.refund or (
            hasattr(tx_type, "value") and tx_type.value == "refund"
        ):
            bucket["refunds"] += amount
        else:
            bucket["sales"] += amount
        bucket["count"] += n
    return out


async def generate_z_report_pdf(db: AsyncSession, z_report: ZReport) -> bytes:
    """Render the Z report as A4 PDF bytes.

    Loads the linked drawer, the daily transactions and cash movements; the
    snapshot is purely read-only so this can be re-run by ``lock_z_report`` to
    persist the byte-identical artefact.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    drawer_row = (
        await db.execute(
            select(CashDrawer).where(CashDrawer.id == z_report.cash_drawer_id)
        )
    ).scalar_one()

    payment_totals = await _aggregate_payment_totals(db, drawer_row)

    # Cash movements in chronological order
    movements_q = await db.execute(
        select(CashMovement)
        .where(CashMovement.drawer_id == drawer_row.id)
        .order_by(CashMovement.created_at.asc())
    )
    movements = movements_q.scalars().all()

    in_total = sum(
        float(m.amount)
        for m in movements
        if m.direction == CashMovementDirection.inflow
    )
    out_total = sum(
        float(m.amount)
        for m in movements
        if m.direction == CashMovementDirection.outflow
    )

    shop = _shop_info()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        title=f"Z report #{z_report.report_number}",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "ZH1", parent=styles["Title"], fontSize=18, leading=22, spaceAfter=4
    )
    h2 = ParagraphStyle(
        "ZH2", parent=styles["Heading2"], fontSize=11, leading=14,
        textColor=colors.HexColor("#0B7A6A"), spaceBefore=6, spaceAfter=2,
    )
    body = ParagraphStyle(
        "ZBody", parent=styles["Normal"], fontSize=9, leading=12
    )
    body_right = ParagraphStyle(
        "ZBodyRight", parent=body, alignment=2
    )
    body_small = ParagraphStyle(
        "ZBodySmall", parent=styles["Normal"], fontSize=8, leading=10
    )
    body_alert = ParagraphStyle(
        "ZBodyAlert", parent=body, textColor=colors.HexColor("#9B2D2D")
    )

    story: list = []

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    title = f"<b>Rapport Z #{z_report.report_number:04d}</b>"
    story.append(Paragraph(title, h1))

    # Régularisation a posteriori — mention explicite (NF525) : ce Z couvre une
    # journée dont l'ouverture de caisse avait été oubliée. Établi à sa date
    # réelle, jamais antidaté ; comptage espèces non rejoué.
    if getattr(z_report, "is_regularization", False):
        story.append(Paragraph(
            "<b>⚠ CLÔTURE DE RÉGULARISATION A POSTERIORI</b><br/>"
            f"Motif : {z_report.regularization_reason or '—'}",
            body,
        ))
        story.append(Spacer(1, 2 * mm))

    period_from = drawer_row.opened_at.strftime("%d/%m/%Y %H:%M")
    period_to = (
        drawer_row.closed_at.strftime("%d/%m/%Y %H:%M")
        if drawer_row.closed_at
        else "(en cours)"
    )
    head_meta = "<br/>".join(
        line for line in [
            f"<b>{shop.get('name', 'Vintiz')}</b>",
            shop.get("address_line1", ""),
            f"{shop.get('postal_code', '')} {shop.get('city', '')}".strip(),
            f"SIRET : {shop['siret']}" if shop.get("siret") else "",
            f"Période : {period_from} → {period_to}",
            f"Cashier ID : {drawer_row.cashier_id or '—'}",
            f"Émis le : {(z_report.created_at or datetime.utcnow()).strftime('%d/%m/%Y %H:%M')}",
        ]
        if line
    )
    story.append(Paragraph(head_meta, body))
    story.append(Spacer(1, 4 * mm))

    # ------------------------------------------------------------------
    # Cash drawer reconciliation
    # ------------------------------------------------------------------
    story.append(Paragraph("Réconciliation tiroir-caisse", h2))

    opening = float(drawer_row.opening_amount or 0)
    closing = (
        float(drawer_row.closing_amount)
        if drawer_row.closing_amount is not None
        else None
    )
    expected = (
        float(drawer_row.expected_amount)
        if drawer_row.expected_amount is not None
        else None
    )
    discrepancy: float | None = None
    if closing is not None and expected is not None:
        discrepancy = round(closing - expected, 2)

    drawer_rows = [
        ["Fond initial", _format_eur(opening)],
        [
            "Espèces encaissées",
            _format_eur(payment_totals.get("cash", {}).get("sales", 0.0)),
        ],
        [
            "Remboursements espèces",
            "-" + _format_eur(
                payment_totals.get("cash", {}).get("refunds", 0.0)
            ),
        ],
        ["Entrées (mouvements)", _format_eur(in_total)],
        ["Sorties (mouvements)", "-" + _format_eur(out_total)],
        [
            "Attendu en caisse",
            _format_eur(expected) if expected is not None else "—",
        ],
        [
            "Compté en caisse",
            _format_eur(closing) if closing is not None else "—",
        ],
    ]
    if discrepancy is not None:
        sign = "+" if discrepancy >= 0 else "-"
        drawer_rows.append(
            ["Écart", f"{sign}{_format_eur(abs(discrepancy))}"]
        )
    drawer_table = Table(
        drawer_rows,
        colWidths=[80 * mm, 40 * mm],
        hAlign="LEFT",
    )
    drawer_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.2, colors.HexColor("#D5D3CC")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(drawer_table)

    allowed = (
        float(drawer_row.allowed_discrepancy)
        if drawer_row.allowed_discrepancy is not None
        else None
    )
    if discrepancy is not None and allowed is not None and abs(discrepancy) > allowed:
        story.append(Spacer(1, 2 * mm))
        story.append(
            Paragraph(
                f"<b>⚠ Écart hors tolérance ({_format_eur(allowed)})</b>",
                body_alert,
            )
        )
        if drawer_row.closing_note:
            story.append(
                Paragraph(
                    "Commentaire : " + drawer_row.closing_note, body_small
                )
            )
    story.append(Spacer(1, 4 * mm))

    # ------------------------------------------------------------------
    # Denomination breakdown — opening + closing
    # ------------------------------------------------------------------
    open_breakdown = drawer_row.opening_breakdown or []
    close_breakdown = drawer_row.closing_breakdown or []
    if open_breakdown or close_breakdown:
        story.append(Paragraph("Détail par dénomination", h2))
        breakdown_rows = [
            [
                Paragraph("<b>Coupure</b>", body),
                Paragraph("<b>Ouverture</b>", body_right),
                Paragraph("<b>Clôture</b>", body_right),
            ]
        ]

        def _index(rows: list[dict]) -> dict[float, int]:
            return {float(r.get("denom", 0)): int(r.get("count", 0)) for r in rows}

        open_idx = _index(open_breakdown)
        close_idx = _index(close_breakdown)
        for denom in sorted(set(open_idx) | set(close_idx), reverse=True):
            n_open = open_idx.get(denom, 0)
            n_close = close_idx.get(denom, 0)
            label = (
                f"{int(denom)} €" if denom >= 1 else f"{int(denom * 100)} cts"
            )
            breakdown_rows.append(
                [
                    Paragraph(label, body),
                    Paragraph(
                        f"{n_open} × {_format_eur(denom)} = {_format_eur(n_open * denom)}",
                        body_right,
                    ),
                    Paragraph(
                        f"{n_close} × {_format_eur(denom)} = {_format_eur(n_close * denom)}",
                        body_right,
                    ),
                ]
            )
        bd = Table(breakdown_rows, colWidths=[30 * mm, 65 * mm, 65 * mm])
        bd.setStyle(
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
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(bd)
        story.append(Spacer(1, 4 * mm))

    # ------------------------------------------------------------------
    # Sales by payment method
    # ------------------------------------------------------------------
    story.append(Paragraph("Encaissements par moyen de paiement", h2))
    method_header = [
        Paragraph("<b>Moyen</b>", body),
        Paragraph("<b>Ventes</b>", body_right),
        Paragraph("<b>Remb.</b>", body_right),
        Paragraph("<b>Net</b>", body_right),
        Paragraph("<b>Nb</b>", body_right),
    ]
    method_rows = [method_header]
    for method in ("cash", "card", "cheque", "cheque_cdc", "avoir", "transfer"):
        bucket = payment_totals.get(method)
        if not bucket:
            continue
        net = bucket["sales"] - bucket["refunds"]
        method_rows.append(
            [
                Paragraph(_payment_method_label(method), body),
                Paragraph(_format_eur(bucket["sales"]), body_right),
                Paragraph("-" + _format_eur(bucket["refunds"]), body_right),
                Paragraph(_format_eur(net), body_right),
                Paragraph(str(bucket["count"]), body_right),
            ]
        )
    method_rows.append(
        [
            Paragraph("<b>Total</b>", body),
            Paragraph(_format_eur(float(z_report.total_sales)), body_right),
            Paragraph(
                "-" + _format_eur(float(z_report.total_refunds)), body_right
            ),
            Paragraph(_format_eur(float(z_report.total_net)), body_right),
            Paragraph(str(z_report.transaction_count), body_right),
        ]
    )
    methods_table = Table(
        method_rows,
        colWidths=[50 * mm, 30 * mm, 30 * mm, 30 * mm, 20 * mm],
    )
    methods_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECEAE3")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.HexColor("#0E0E0C")),
                ("LINEBELOW", (0, 1), (-1, -2), 0.2, colors.HexColor("#D5D3CC")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.HexColor("#0B7A6A")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(methods_table)
    story.append(Spacer(1, 4 * mm))

    # ------------------------------------------------------------------
    # Cash movements timeline
    # ------------------------------------------------------------------
    if movements:
        story.append(Paragraph("Mouvements de caisse", h2))
        mv_rows = [
            [
                Paragraph("<b>Heure</b>", body),
                Paragraph("<b>Sens</b>", body),
                Paragraph("<b>Motif</b>", body),
                Paragraph("<b>Montant</b>", body_right),
                Paragraph("<b>Note</b>", body),
            ]
        ]
        for mv in movements:
            ts = mv.created_at.strftime("%H:%M") if mv.created_at else ""
            sign = "Entrée" if mv.direction == CashMovementDirection.inflow else "Sortie"
            mv_rows.append(
                [
                    Paragraph(ts, body),
                    Paragraph(sign, body),
                    Paragraph(_reason_label(mv.reason.value), body),
                    Paragraph(_format_eur(float(mv.amount)), body_right),
                    Paragraph(mv.note or "—", body_small),
                ]
            )
        mv_table = Table(
            mv_rows,
            colWidths=[18 * mm, 18 * mm, 50 * mm, 30 * mm, 60 * mm],
        )
        mv_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECEAE3")),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.HexColor("#0E0E0C")),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.2, colors.HexColor("#D5D3CC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(mv_table)
        story.append(Spacer(1, 4 * mm))

    # ------------------------------------------------------------------
    # Hash chain + NF525 footer
    # ------------------------------------------------------------------
    chain = (
        f"Hash courant : {z_report.hash}<br/>"
        f"Hash précédent : {z_report.previous_hash or '0'}"
    )
    if z_report.is_locked:
        chain += "<br/><b>Verrouillé</b>"
        if z_report.locked_at:
            chain += f" le {z_report.locked_at.strftime('%d/%m/%Y %H:%M')}"
        if z_report.pdf_sha256:
            chain += f"<br/>SHA-256 PDF : {z_report.pdf_sha256[:16]}…"
    story.append(Paragraph(chain, body_small))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "Logiciel de caisse Vintiz — conforme NF525 / article 88 du CGI. "
            "Document inaltérable et conservé pendant 6 ans (art. L.102B LPF).",
            body_small,
        )
    )

    doc.build(story)
    return buf.getvalue()
