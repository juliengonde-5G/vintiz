"""ZPL II label generator for the Zebra ZD421d (25×52 mm, 8 dpmm).

Vintiz imprime DEUX étiquettes par produit :

  Étiquette 1 — Info (paysage, ^A0N) :
    ┌──────────────────────────────────────────────────────┐  ← 52 mm (X, ~416 dots)
    │           Nom du produit                             │
    │   ║▌█▌▌█████▌▌ (barcode) VTZ-2026-00142             │
    │           Semaine 21                                 │
    └──────────────────────────────────────────────────────┘  ← 25 mm (Y, 200 dots)

  Étiquette 2 — Prix (paysage, ^A0N) :
    ┌──────────────────────────────────────────────────────┐
    │                   VINTIZ                             │
    │           ─────────────────────                      │
    │                  12,50 €                             │
    └──────────────────────────────────────────────────────┘

  Coordonnées : X = axe printhead (52 mm paysage, clips à 416 dots).
                Y = axe alimentation (25 mm, gap sensor coupe à 200 dots).

build_label_zpl() / build_label_set_zpl() concatènent les deux blocs
^XA…^XZ — la Zebra imprime les deux à la suite. La preview Labelary
(index /0/) rend uniquement l'étiquette 1 (info).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

LABEL_WIDTH_DOTS = 640   # canvas paysage X (axe printhead ≈ 52 mm, printer clips at 416)
LABEL_HEIGHT_DOTS = 200  # canvas paysage Y (axe alimentation, 25 mm = 200 dots)
LABELARY_DPMM = "8dpmm"
LABELARY_SIZE = "2.05x0.98"   # landscape 52 × 25 mm

DEFAULT_PRINT_RATE = 4
DEFAULT_MEDIA_DARKNESS = 0


@dataclass(frozen=True)
class LabelData:
    """Vue plain-data d'un produit pour les gabarits ZPL."""

    product_name: str
    category: str
    size: str | None
    condition: str | None
    sale_price: float
    barcode: str
    shelf_date: datetime | None
    location: str | None = None
    entry_date: datetime | None = None
    week_number: int | None = None


def _sanitize(text: str | None, *, max_length: int | None = None) -> str:
    """Strip ZPL control characters (^, ~, \\) and clamp length."""
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


def _week_label(data: LabelData) -> str:
    week = data.week_number
    if not week:
        anchor = data.shelf_date or data.entry_date
        if anchor is not None:
            week = anchor.isocalendar()[1]
    if not week:
        return "Semaine --"
    return f"Semaine {int(week):02d}"


def _price_str(price: float) -> str:
    """12.5 → '12,50 €'."""
    return f"{price:.2f} €".replace(".", ",")


def _zpl_head(pr: int, md: int) -> str:
    return (
        f"^PR{pr}^MD{md}^CI28"
        f"^PW{LABEL_WIDTH_DOTS}^LL{LABEL_HEIGHT_DOTS}"
        "^LH0,0"
    )


def build_info_label_zpl(
    data: LabelData,
    *,
    copies: int = 1,
    print_rate: int = DEFAULT_PRINT_RATE,
    media_darkness: int = DEFAULT_MEDIA_DARKNESS,
) -> str:
    """Étiquette 1 — info produit : code-barres, réf, nom, semaine."""
    copies = max(1, int(copies))
    pr = max(2, min(6, int(print_rate)))
    md = max(-30, min(30, int(media_darkness)))

    name = _sanitize(data.product_name, max_length=28) or "Article"
    ref  = _sanitize(data.barcode, max_length=24)      or "VTZ-NOREF"
    week = _week_label(data)

    # Paysage : axe X = 52 mm (printhead, ~416 dots), axe Y = 25 mm (alimentation = 200 dots).
    # Tout le contenu doit tenir dans Y ≤ ~185 (le capteur de gap coupe à 200).
    #   y=8  : nom du produit (police 30) → fin y=38
    #   y=45 : code-barres Code 128 horizontal, h=85 + ligne d'interprétation (~20) → fin y≈150
    #   y=158: semaine (police 24) → fin y=182
    return (
        "^XA"
        + _zpl_head(pr, md)
        + f"^FO0,8^FB640,1,0,C,0^A0N,30,30^FD{name}^FS"
        + f"^FO20,45^BY1,2.5,85^BCN,85,Y,N,N,A^FD{ref}^FS"
        + f"^FO0,158^FB640,1,0,C,0^A0N,24,24^FD{week}^FS"
        + f"^PQ{copies}"
        + "^XZ"
    )


def build_price_label_zpl(
    data: LabelData,
    *,
    copies: int = 1,
    print_rate: int = DEFAULT_PRINT_RATE,
    media_darkness: int = DEFAULT_MEDIA_DARKNESS,
) -> str:
    """Étiquette 2 — prix : logo VINTIZ + prix de vente."""
    copies = max(1, int(copies))
    pr = max(2, min(6, int(print_rate)))
    md = max(-30, min(30, int(media_darkness)))

    price = _price_str(float(data.sale_price))

    # Paysage, Y ≤ 185 :
    #   y=10 : "VINTIZ" (police 40) → fin y=50
    #   y=60 : séparateur horizontal
    #   y=70 : prix en grande police (95) → fin y=165
    return (
        "^XA"
        + _zpl_head(pr, md)
        + "^FO0,10^FB640,1,0,C,0^A0N,40,40^FDVINTIZ^FS"
        + "^FO40,60^GB560,3,3^FS"
        + f"^FO0,70^FB640,1,0,C,0^A0N,95,95^FD{price}^FS"
        + f"^PQ{copies}"
        + "^XZ"
    )


def build_label_zpl(
    data: LabelData,
    *,
    copies: int = 1,
    print_rate: int = DEFAULT_PRINT_RATE,
    media_darkness: int = DEFAULT_MEDIA_DARKNESS,
) -> str:
    """Génère les deux étiquettes Vintiz (info + prix) pour un produit."""
    kw: dict = dict(copies=copies, print_rate=print_rate, media_darkness=media_darkness)
    return build_info_label_zpl(data, **kw) + build_price_label_zpl(data, **kw)


# Alias conservé pour compatibilité avec le labels router.
build_label_set_zpl = build_label_zpl


# ---------------------------------------------------------------------------
# ORM adapter
# ---------------------------------------------------------------------------

_FLOOR_STATUS_VALUES = {"display", "displayed", "discounted", "deep_discounted"}


def product_to_label_data(product: Any) -> LabelData:
    """Adapte un ORM Product en LabelData."""
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
