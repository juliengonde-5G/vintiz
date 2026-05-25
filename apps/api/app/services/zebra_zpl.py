"""ZPL II label generator for the Zebra ZD421d (25×52 mm, 8 dpmm).

Vintiz imprime DEUX étiquettes par produit :

  Étiquette 1 — Info :
    ┌─────────────────────────────────────────────┐
    │ Réf  ║▌█▌▌█  Nom du produit     Semaine 21  │
    └─────────────────────────────────────────────┘
    Contenu : code-barres Code 128 (rotaté 90°) + réf (ligne
    d'interprétation) + nom du produit + numéro de semaine.

  Étiquette 2 — Prix :
    ┌─────────────────────────────────────────────┐
    │  VINTIZ  │            12,50 €               │
    └─────────────────────────────────────────────┘
    Contenu : logo texte VINTIZ + prix de vente.

build_label_zpl() / build_label_set_zpl() concatènent les deux blocs
^XA…^XZ — la Zebra imprime les deux à la suite. La preview Labelary
(index /0/) rend uniquement l'étiquette 1 (info).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

LABEL_WIDTH_DOTS = 200   # 25 mm
LABEL_HEIGHT_DOTS = 416  # 52 mm
LABELARY_DPMM = "8dpmm"
LABELARY_SIZE = "0.98x2.05"

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
        "^POI"   # invert 180° — la ZD421d sort l'étiquette du bon côté
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

    # Mise en page paysage (52 mm horizontal, 25 mm vertical).
    # Tout le contenu est rotaté 90° CW (^A0R / ^BCR) pour se lire
    # à l'horizontale. De gauche à droite (y croissant) :
    #   réf (bas visuel) | code-barres | nom | semaine (haut visuel)
    # De haut en bas (x croissant dans les 200 dots = 25 mm) :
    #   x=8  : ligne de réf (police 22)
    #   x=38 : code-barres Code 128 (hauteur 82 dots)
    #   x=132: nom du produit (police 30)
    #   x=168: semaine (police 24)
    return (
        "^XA"
        + _zpl_head(pr, md)
        + f"^FO8,12^A0R,22,22^FB392,1,0,C,0^FD{ref}^FS"
        + f"^FO38,12^BY2,2.5,82^BCR,82,N,N,N,A^FD{ref}^FS"
        + f"^FO132,12^A0R,30,30^FB392,1,0,C,0^FD{name}^FS"
        + f"^FO168,12^A0R,24,24^FB392,1,0,C,0^FD{week}^FS"
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

    # Paysage également. De haut en bas (x croissant) :
    #   x=16 : "VINTIZ" (police 30, bande étroite)
    #   x=60 : séparateur vertical (trait 2 dots × 416 dots)
    #   x=80 : prix en grande police (80 dots de haut, 52 dots de large/char)
    return (
        "^XA"
        + _zpl_head(pr, md)
        + "^FO16,12^A0R,30,30^FB392,1,0,C,0^FDVINTIZ^FS"
        + "^FO60,0^GB2,416,2^FS"
        + f"^FO80,12^A0R,80,52^FB392,1,0,C,0^FD{price}^FS"
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
