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

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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
    # défilement (^LL416) ; le contenu est donc tourné (``^A0R`` / ``^BCR``)
    # pour se lire à l'horizontale. Comme ``^POI`` retourne l'étiquette de
    # 180°, les lignes sont posées en x croissant du bas vers le haut visuel
    # (réf en premier dans le code → en bas ; Semaine en dernier → en haut).
    # Positions en dots (8/mm) ; ajuster contre /labels/preview au besoin.
    return (
        "^XA"
        # Print orientation inversée (180°) : l'étiquette sort dans le bon sens
        # de lecture par rapport au sens d'éjection de la Zebra ZD421d. Doit
        # précéder les champs ^FO pour s'appliquer à toute l'étiquette.
        "^POI"
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


def _price_label(data: "LabelData") -> str:
    """Prix de vente formaté FR : ``39,00 €`` (virgule décimale)."""
    value = float(getattr(data, "sale_price", 0) or 0)
    return f"{value:.2f} €".replace(".", ",")


# --- Logo Vintiz rasterisé en graphique ZPL (^GFA) -------------------------
# Le monogramme VZ est rastérisé une seule fois en bitmap 1 bit puis émis en
# ^GFA sur l'étiquette prix. Lazy + caché : pas de coût au boot, et un logo
# manquant ou PIL absent retombe proprement sur le lettrage texte.
_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo-teal.png"
LOGO_TARGET_DOTS = 96  # taille du monogramme sur l'étiquette (≈ 12 mm)
_logo_zpl_cache: tuple[str, int, int] | None = None
_logo_attempted = False
_logo_lock = threading.Lock()


def _image_to_gfa(img: Any) -> tuple[str, int, int]:
    """Encode une image PIL mode ``1`` en champ graphique ZPL ``^GFA``.

    Renvoie ``(zpl, width_dots, height_dots)``. Bit à 1 = point noir (ZPL),
    or en mode ``1`` un pixel noir vaut 0 — on inverse donc le test.
    """
    w, h = img.size
    bytes_per_row = (w + 7) // 8
    total = bytes_per_row * h
    px = img.load()
    rows: list[str] = []
    for y in range(h):
        rb = bytearray(bytes_per_row)
        for x in range(w):
            if px[x, y] == 0:  # noir
                rb[x >> 3] |= 0x80 >> (x & 7)
        rows.append(rb.hex().upper())
    return f"^GFA,{total},{total},{bytes_per_row}," + "".join(rows), w, h


def _logo_zpl_graphic() -> tuple[str, int, int] | None:
    """``(^GFA, width, height)`` du monogramme, ou None si indisponible.

    Le logo est composé sur blanc, mis à l'échelle, tourné de 90° (pour
    s'aligner sur le texte ``^A0R`` ; ``^POI`` applique ensuite les 180°
    restants), puis seuillé en 1 bit noir/blanc.
    """
    global _logo_zpl_cache, _logo_attempted
    if _logo_attempted:
        return _logo_zpl_cache
    with _logo_lock:
        if _logo_attempted:
            return _logo_zpl_cache
        try:
            from PIL import Image

            img = Image.open(_LOGO_PATH).convert("RGBA")
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            bg.alpha_composite(img)
            gray = bg.convert("L")
            w, h = gray.size
            scale = LOGO_TARGET_DOTS / max(w, h)
            gray = gray.resize(
                (max(1, round(w * scale)), max(1, round(h * scale))),
                Image.LANCZOS,
            )
            gray = gray.transpose(Image.Transpose.ROTATE_270)
            bw = gray.point(lambda p: 0 if p < 140 else 255, mode="1")
            _logo_zpl_cache = _image_to_gfa(bw)
        except Exception:  # noqa: BLE001 — PIL absent / logo manquant → repli texte
            _logo_zpl_cache = None
        _logo_attempted = True
        return _logo_zpl_cache


def build_price_label_zpl(
    data: LabelData,
    *,
    copies: int = 1,
    print_rate: int = DEFAULT_PRINT_RATE,
    media_darkness: int = DEFAULT_MEDIA_DARKNESS,
) -> str:
    """Render the SECOND tag : monogramme Vintiz (image) + prix de vente.

    Même média et même orientation que l'étiquette produit (25×52 mm,
    contenu tourné + ``^POI``). Le logo est le monogramme VZ rastérisé en
    ``^GFA`` ; si l'image est indisponible, repli sur le lettrage texte.
    Le prix est imprimé en gros sous le logo.
    """
    if copies < 1:
        copies = 1
    pr = max(2, min(6, int(print_rate)))
    md = max(-30, min(30, int(media_darkness)))
    price = _price_label(data)

    # Sous ^POI, x croissant = du bas vers le haut visuel : prix en bas
    # (x faible), logo en haut (x élevé).
    logo = _logo_zpl_graphic()
    if logo is not None:
        gfa, lw, lh = logo
        lx = max(0, LABEL_WIDTH_DOTS - lw - 6)
        ly = max(0, (LABEL_HEIGHT_DOTS - lh) // 2)
        brand_field = f"^FO{lx},{ly}{gfa}^FS"
    else:
        brand_field = "^FO150,8^A0R,48,48^FB400,1,0,C,0^FDVINTIZ^FS"

    return (
        "^XA"
        "^POI"
        f"^PR{pr}"
        f"^MD{md}"
        "^CI28"
        f"^PW{LABEL_WIDTH_DOTS}"
        f"^LL{LABEL_HEIGHT_DOTS}"
        "^LH0,0"
        # Prix de vente (gros, bas visuel).
        f"^FO16,8^A0R,80,80^FB400,1,0,C,0^FD{price}^FS"
        # Monogramme VZ (haut visuel) ou repli lettrage.
        f"{brand_field}"
        f"^PQ{copies}"
        "^XZ"
    )


def build_label_set_zpl(
    data: LabelData,
    *,
    copies: int = 1,
    print_rate: int = DEFAULT_PRINT_RATE,
    media_darkness: int = DEFAULT_MEDIA_DARKNESS,
) -> str:
    """Jeu d'étiquettes imprimé à l'édition : tag produit + tag prix.

    Concatène les deux jobs ZPL (``^XA…^XZ`` × 2) ; la Zebra imprime donc
    deux étiquettes à la suite — l'étiquette code-barres/réf puis l'étiquette
    logo + prix.
    """
    kwargs = {"print_rate": print_rate, "media_darkness": media_darkness}
    return (
        build_label_zpl(data, copies=copies, **kwargs)
        + build_price_label_zpl(data, copies=copies, **kwargs)
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
