"""ZPL II label generator for the Zebra ZD421d (80×120 mm, 8 dpmm).

The label is laid out on a 640×960-dot canvas (3.15″ × 4.72″ @ 8 dpmm) and
matches the Vintiz boutique template:

    ┌──────────────────────┐
    │       VINTIZ         │   bold display
    │ ──────────────────── │
    │   Nom de l'article   │   ≤ 30 chars
    │   Catégorie • T.M    │
    │   État : Excellent   │
    │                      │
    │       12,00 €        │   huge, centered
    │                      │
    │ ──────────────────── │
    │  ▌█▌█▌█▌█▌█▌█▌█▌█▌  │   Code 128 + interpretation line
    │  VTZ-2026-00142      │
    │                      │
    │  Rayon : 14/05/2026  │
    │  Démarque : 13/06/26 │
    └──────────────────────┘

The function returns a UTF-8 ZPL string ready to be POSTed to Labelary for
preview, or written to a TCP socket on the printer port 9100.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

# 80 × 120 mm @ 8 dpmm
LABEL_WIDTH_DOTS = 640
LABEL_HEIGHT_DOTS = 960
LABELARY_DPMM = "8dpmm"
LABELARY_SIZE = "3.15x4.72"

MARKDOWN_DAYS = 30

# Print rate (^PR) — inches per second. ZD421d 203 dpi supports 2-6 ips.
# Lower = sharper print on small fonts and barcodes ; higher = faster
# throughput when batch-printing dozens of labels. 4 ips is a balanced
# default that keeps the Code 128 scannable.
DEFAULT_PRINT_RATE = 4

# Media darkness (^MD) — relative offset from the printer's permanent
# darkness setting (set via the front-panel pause+feed calibration).
# Range -30..30. 0 = use the printer's saved value. Positive values
# burn darker (better contrast on Vintiz cream labels but eats the
# print head faster).
DEFAULT_MEDIA_DARKNESS = 0


@dataclass(frozen=True)
class LabelData:
    """Plain-data view of a product, ready for the ZPL template.

    Decoupled from the SQLAlchemy ``Product`` so the template is trivially
    unit-testable without a database.
    """

    product_name: str
    category: str
    size: str | None
    condition: str | None
    sale_price: float
    barcode: str
    shelf_date: datetime | None


def _sanitize(text: str | None, *, max_length: int | None = None) -> str:
    """Strip ZPL control characters and clamp length.

    The ZPL caret (``^``), tilde (``~``) and backslash (``\\``) prefixes
    introduce commands; they MUST NOT appear inside ``^FD`` data. We replace
    them with safe equivalents rather than raise: a malformed product name
    should never break a print job.
    """
    if not text:
        return ""
    cleaned = (
        text.replace("\\", "/")
        .replace("^", "-")
        .replace("~", "-")
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )
    if max_length is not None and len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 1].rstrip() + "…"
    return cleaned


def _format_price(amount: float) -> str:
    return f"{amount:.2f} €".replace(".", ",")


def _format_date(dt: datetime | None) -> str:
    return dt.strftime("%d/%m/%Y") if dt else "—"


def build_label_zpl(
    data: LabelData,
    *,
    copies: int = 1,
    print_rate: int = DEFAULT_PRINT_RATE,
    media_darkness: int = DEFAULT_MEDIA_DARKNESS,
) -> str:
    """Render a single Vintiz product label as a ZPL II string.

    ``copies`` is passed through to ``^PQ`` so a single submission can
    print several physical labels (used by the batch endpoint with
    ``copies=N``).

    ``print_rate`` and ``media_darkness`` let the manager tune the
    output without redeploying : faster speed for big batches, darker
    burn for low-contrast media. Both are clamped to the ZPL II valid
    ranges (PR: 2..6 for ZD421d 203 dpi, MD: -30..30).
    """
    if copies < 1:
        copies = 1
    pr = max(2, min(6, int(print_rate)))
    md = max(-30, min(30, int(media_darkness)))

    name = _sanitize(data.product_name, max_length=30) or "Article"
    category = _sanitize(data.category, max_length=20) or "Article"
    size = _sanitize(data.size, max_length=10)
    condition = _sanitize(data.condition, max_length=20) or "Bon état"
    price = _format_price(float(data.sale_price))
    ref = _sanitize(data.barcode, max_length=24) or "VTZ-NOREF"
    shelf_label = _format_date(data.shelf_date)
    markdown_label = _format_date(
        (data.shelf_date + timedelta(days=MARKDOWN_DAYS)) if data.shelf_date else None
    )

    category_line = f"{category} • T.{size}" if size else category

    # ZPL II — `^CI28` enables UTF-8 so accented characters in the name,
    # category and condition fields render correctly. ``^PR`` and ``^MD``
    # are sent at the top of every job so the manager's tuning takes
    # effect even after the printer was power-cycled (these commands
    # don't persist by default — use ``^JU S`` to save).
    return (
        "^XA"
        f"^PR{pr}"
        f"^MD{md}"
        "^CI28"
        f"^PW{LABEL_WIDTH_DOTS}"
        f"^LL{LABEL_HEIGHT_DOTS}"
        "^LH0,0"
        # Header — VINTIZ wordmark
        "^FO0,40^FB640,1,0,C,0^A0N,80,80^FDVINTIZ^FS"
        # Top separator
        "^FO20,135^GB600,2,2^FS"
        # Product name (auto-wraps onto 2 lines if needed)
        f"^FO20,165^FB600,2,5,C,0^A0N,32,32^FD{name}^FS"
        # Category • Size
        f"^FO20,265^FB600,1,0,C,0^A0N,28,28^FD{category_line}^FS"
        # Condition / état
        f"^FO20,310^FB600,1,0,C,0^A0N,24,24^FD{condition}^FS"
        # PRICE — large, centered
        f"^FO0,380^FB640,1,0,C,0^A0N,140,130^FD{price}^FS"
        # Bottom separator
        "^FO20,560^GB600,2,2^FS"
        # Code 128 barcode + human-readable line
        "^FO80,595^BY3,3,160"
        f"^BCN,160,Y,N,N,A^FD{ref}^FS"
        # Reference (mirrors the interpretation line, prefixed)
        f"^FO20,790^FB600,1,0,C,0^A0N,24,24^FDRéf : {ref}^FS"
        # Dates — shelf + markdown J+30
        f"^FO20,840^FB600,1,0,C,0^A0N,22,22^FDRayon depuis : {shelf_label}^FS"
        f"^FO20,880^FB600,1,0,C,0^A0N,22,22^FDDémarque le : {markdown_label}^FS"
        f"^PQ{copies}"
        "^XZ"
    )


def product_to_label_data(product: Any) -> LabelData:
    """Adapt an ORM ``Product`` to ``LabelData``.

    Kept here (rather than in the router) so the bridge has one canonical
    source and the unit tests can build their fixtures the same way the
    runtime does.
    """
    category_name = product.category.name if getattr(product, "category", None) else "Article"
    shelf = getattr(product, "displayed_at", None) or getattr(product, "shelf_date", None)
    return LabelData(
        product_name=getattr(product, "name", "") or "",
        category=category_name,
        size=getattr(product, "size", None),
        condition=getattr(product, "condition", None),
        sale_price=float(getattr(product, "sale_price", 0) or 0),
        barcode=getattr(product, "barcode", "") or "",
        shelf_date=shelf,
    )
