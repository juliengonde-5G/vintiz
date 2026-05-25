"""ZPL II label generator for the Zebra ZD421d (25×52 mm, 8 dpmm).

Vintiz imprime DEUX étiquettes par produit :

  Étiquette 1 — Info (paysage, ^A0N) :
    ┌──────────────────────────────────────────────────────┐  ← 52 mm (X, 640 dots)
    │                  Nom du produit                      │
    │            ║▌█▌▌█████▌▌ (code-barres centré)         │
    │                   Semaine 21                         │
    └──────────────────────────────────────────────────────┘  ← 25 mm (Y, 300 dots)

  Étiquette 2 — Prix (paysage, ^A0N) :
    ┌──────────────────────────────────────────────────────┐
    │                     VINTIZ                           │
    │              ─────────────────────                   │
    │                    12,50 €                           │
    └──────────────────────────────────────────────────────┘

  ZD421d 300 dpi : X = axe printhead (52 mm = 640 dots), Y = axe
  alimentation (25 mm = 300 dots). Tout est centré (^FB640) ; la largeur
  de module du code-barres s'adapte pour rester dans les 640 dots.

build_label_zpl() / build_label_set_zpl() concatènent les deux blocs
^XA…^XZ — la Zebra imprime les deux à la suite. La preview Labelary
(index /0/) rend uniquement l'étiquette 1 (info).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# ZD421d 300 dpi (12 dpmm) : l'étiquette test ^PW640 remplit correctement les
# 52 mm → 640 dots / 52 mm ≈ 12 dpmm. En paysage : X = 52 mm = 640 dots
# (axe printhead), Y = 25 mm = 300 dots (axe alimentation).
LABEL_WIDTH_DOTS = 640   # canvas paysage X (printhead, 52 mm)
LABEL_HEIGHT_DOTS = 300  # canvas paysage Y (alimentation, 25 mm)
LABELARY_DPMM = "12dpmm"
LABELARY_SIZE = "2.1x0.98"   # landscape 53 × 25 mm

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


def _barcode_layout(ref: str, *, canvas_w: int = LABEL_WIDTH_DOTS) -> tuple[int, int]:
    """Module width + x-origin so the Code 128 is centred and fits the canvas.

    Largeur Code 128 (modules) = start(11) + n×11 + checksum(11) + stop(13)
    + 2 zones de silence (10 chacune). On choisit la largeur de module la plus
    grande qui rentre (meilleure lisibilité scanner), puis on centre.
    """
    n = len(ref)
    modules = 11 * (n + 2) + 13 + 20
    for by in (3, 2, 1):
        width = by * modules
        if width <= canvas_w - 16:
            return by, max(8, (canvas_w - width) // 2)
    return 1, 8


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

    # Paysage 640×300 (12 dpmm). Tout centré sur la largeur (^FB640), empilé
    # dans Y ≤ ~290. Largeur de glyphe < hauteur pour que les chaînes longues
    # tiennent dans 640 ; le nom peut se replier sur 2 lignes.
    #   y=12 : nom du produit (police 38×32, max 2 lignes) → fin ≤ y=88
    #   y=95 : code-barres Code 128 horizontal centré, h=110 + interprétation
    #   y=250: semaine (police 30×28)
    by, bx = _barcode_layout(ref)
    return (
        "^XA"
        + _zpl_head(pr, md)
        + f"^FO0,12^FB640,2,0,C,0^A0N,38,32^FD{name}^FS"
        + f"^FO{bx},95^BY{by},2.5,110^BCN,110,Y,N,N,A^FD{ref}^FS"
        + f"^FO0,250^FB640,1,0,C,0^A0N,30,28^FD{week}^FS"
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

    # Paysage 640×300, centré, Y ≤ ~290. Largeur de glyphe < hauteur pour que
    # les prix longs (ex. "199,00 €") tiennent dans 640 :
    #   y=40 : "VINTIZ" (police 60×54) → fin y=100
    #   y=130: séparateur horizontal
    #   y=155: prix en grande police (110×66) → fin y=265
    return (
        "^XA"
        + _zpl_head(pr, md)
        + "^FO0,40^FB640,1,0,C,0^A0N,60,54^FDVINTIZ^FS"
        + "^FO40,130^GB560,3,3^FS"
        + f"^FO0,155^FB640,1,0,C,0^A0N,110,66^FD{price}^FS"
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
