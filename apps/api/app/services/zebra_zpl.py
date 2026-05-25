"""ZPL II label generator for the Zebra ZD421d (25×52 mm, 8 dpmm).

Vintiz standard tag — small clothing/price label, 25 mm wide × 52 mm long.
Only four fields, per the boutique brief:

    ┌───────────────┐
    │ ║▌█▌█▌  N  S   │   Code 128 (rotated) + name + week, read sideways
    │ ║▌█▌█▌  o  e   │
    │ ║▌█▌█▌  m  m   │
    │ VTZ-2026-00142 │   ← barcode interpretation line = réf
    └───────────────┘

The label is laid out on a 200×416-dot canvas (25 × 52 mm @ 8 dpmm). Because a
``VTZ-YYYY-NNNNNN`` reference is far too long to print a horizontal Code 128
across 25 mm, the barcode is **rotated 90°** (``^BCR``) so its length runs along
the 52 mm side and stays scannable; the name and week are printed as rotated
text columns beside it (the tag is read held sideways).

The function returns a UTF-8 ZPL string ready to be POSTed to Labelary for
preview, or written to a TCP socket on the printer port 9100.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# 25 × 52 mm @ 8 dpmm (Zebra ZD421d, 203 dpi). Width = across the print head,
# length = feed direction. Change here (+ hardware.json label_*_mm) to retarget
# a different media size.
LABEL_WIDTH_DOTS = 200   # 25 mm
LABEL_HEIGHT_DOTS = 416  # 52 mm
LABELARY_DPMM = "8dpmm"
# Labelary path size is in inches: 25 mm ≈ 0.98", 52 mm ≈ 2.05".
LABELARY_SIZE = "0.98x2.05"

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
    unit-testable without a database. The 25×52 tag only prints the barcode
    (``barcode``), the product name and the intake week; the other fields are
    kept for backward compatibility with existing callers / fixtures.
    """

    product_name: str
    category: str
    size: str | None
    condition: str | None
    sale_price: float
    barcode: str
    shelf_date: datetime | None
    location: str | None = None
    entry_date: datetime | None = None
    # ISO week of intake. When None it is derived from shelf/entry date.
    week_number: int | None = None


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


def _week_label(data: "LabelData") -> str:
    """`Semaine NN` from the product's week number, or derived from a date."""
    week = data.week_number
    if not week:
        anchor = data.shelf_date or data.entry_date
        if anchor is not None:
            week = anchor.isocalendar()[1]
    if not week:
        return "Semaine —"
    return f"Semaine {int(week):02d}"


def build_label_zpl(
    data: LabelData,
    *,
    copies: int = 1,
    print_rate: int = DEFAULT_PRINT_RATE,
    media_darkness: int = DEFAULT_MEDIA_DARKNESS,
) -> str:
    """Render a single Vintiz 25×52 mm product tag as a ZPL II string.

    Content (per the boutique brief): Code 128 barcode, its reference
    (interpretation line), the product name and the intake week — nothing else.

    ``copies`` is passed through to ``^PQ`` so a single submission can print
    several physical labels (used by the batch endpoint). ``print_rate`` and
    ``media_darkness`` let the manager tune output without redeploying; both
    are clamped to the ZPL II valid ranges (PR 2..6, MD -30..30).
    """
    if copies < 1:
        copies = 1
    pr = max(2, min(6, int(print_rate)))
    md = max(-30, min(30, int(media_darkness)))

    ptype = _sanitize(data.category, max_length=22) or "Article"
    ref = _sanitize(data.barcode, max_length=24) or "VTZ-NOREF"
    week = _week_label(data)

    # ZPL II — ``^CI28`` enables UTF-8 so accented characters render.
    # Mise en page PAYSAGE : la tablette tient l'étiquette dans le sens de la
    # longueur (52 mm horizontal). Quatre lignes empilées, de haut en bas :
    #   Semaine · Type produit · code-barres (Code 128) · réf produit.
    # Le média est chargé 25 mm en largeur de tête (^PW200) × 52 mm en
    # défilement (^LL416) ; le contenu est tourné (``^A0R`` / ``^BCR``)
    # pour se lire à l'horizontale (top du label vers la droite).
    # Positions en dots (8/mm) ; ajuster contre /labels/preview au besoin.
    return (
        "^XA"
        f"^PR{pr}"
        f"^MD{md}"
        "^CI28"
        f"^PW{LABEL_WIDTH_DOTS}"
        f"^LL{LABEL_HEIGHT_DOTS}"
        "^LH0,0"
        # Réf produit (bas visuel).
        f"^FO8,12^A0R,22,22^FB392,1,0,C,0^FD{ref}^FS"
        # Code-barres Code 128 — barres seules (réf imprimée à part). Module
        # 2 dots, hauteur 82 dots ; court le long des 52 mm.
        f"^FO38,12^BY2,2.5,82^BCR,82,N,N,N,A^FD{ref}^FS"
        # Type produit (catégorie).
        f"^FO132,12^A0R,30,30^FB392,1,0,C,0^FD{ptype}^FS"
        # Semaine d'arrivage (haut visuel).
        f"^FO176,12^A0R,24,24^FB392,1,0,C,0^FD{week}^FS"
        f"^PQ{copies}"
        "^XZ"
    )


# Product statuses that mean the item is physically on the shop floor.
_FLOOR_STATUS_VALUES = {"display", "displayed", "discounted", "deep_discounted"}


def product_to_label_data(product: Any) -> LabelData:
    """Adapt an ORM ``Product`` to ``LabelData``.

    Kept here (rather than in the router) so the bridge has one canonical
    source and the unit tests build their fixtures the same way the runtime
    does.
    """
    category_name = product.category.name if getattr(product, "category", None) else "Article"
    shelf = getattr(product, "displayed_at", None) or getattr(product, "shelf_date", None)
    received = getattr(product, "received_at", None)

    status = getattr(product, "status", None)
    status_val = getattr(status, "value", status)
    location = "rayon" if status_val in _FLOOR_STATUS_VALUES else "stock"

    return LabelData(
        product_name=getattr(product, "name", "") or "",
        category=category_name,
        size=getattr(product, "size", None),
        condition=getattr(product, "condition", None),
        sale_price=float(getattr(product, "sale_price", 0) or 0),
        barcode=getattr(product, "barcode", "") or "",
        shelf_date=shelf,
        location=location,
        entry_date=received,
        week_number=getattr(product, "week_number", None),
    )
