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
    # Genre hérité de la catégorie (``homme`` | ``femme`` | ``enfant`` |
    # ``mixte``). Affiché en abrégé sur l'étiquette info à côté du nom + taille
    # ; ``mixte`` / vide → rien d'imprimé. Voir ``_gender_token``.
    gender: str | None = None


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


# Genre abrégé imprimé en 3e variable de la 1re ligne, à côté du nom + taille.
# Le genre est désormais un attribut produit explicite (homme/femme/enfant/
# mixte) → unisexe = "U". Vide / inconnu → rien (fiches sans genre).
_GENDER_TOKENS = {"homme": "H", "femme": "F", "enfant": "E", "mixte": "U"}


def _gender_token(gender: str | None) -> str:
    """homme→H, femme→F, enfant→E, mixte(unisexe)→U ; vide / inconnu → ''."""
    if not gender:
        return ""
    return _GENDER_TOKENS.get(str(gender).strip().lower(), "")


def _barcode_layout(
    ref: str, *, canvas_w: int = LABEL_WIDTH_DOTS, right_shift: int = 0
) -> tuple[int, int]:
    """Module width + x-origin so the Code 128 is centred and fits the canvas.

    Largeur Code 128 (modules) = start(11) + n×11 + checksum(11) + stop(13)
    + 2 zones de silence (10 chacune). On choisit la largeur de module la plus
    grande qui rentre (meilleure lisibilité scanner), puis on centre.

    ``right_shift`` ajoute une marge à gauche (décale le code-barres vers la
    droite) pour compenser l'offset physique du printhead ; on clampe pour que
    le code reste dans le canvas.
    """
    n = len(ref)
    modules = 11 * (n + 2) + 13 + 20
    for by in (3, 2, 1):
        width = by * modules
        if width <= canvas_w - 16:
            centered = (canvas_w - width) // 2
            max_x = canvas_w - width - 8
            return by, max(8, min(centered + right_shift, max_x))
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

    size = _sanitize(data.size, max_length=5)
    gender = _gender_token(data.gender)
    # Le nom partage sa ligne avec la taille (T.xx) et le genre (H/F/E) : on
    # raccourcit le nom selon ce qui l'accompagne pour tenir sur une ligne
    # (640 dots). Le suffixe genre coûte ~3 caractères.
    name_max = 18 if size else 28
    if gender:
        name_max = max(8, name_max - 3)
    name = _sanitize(data.product_name, max_length=name_max) or "Article"
    title = name
    if size:
        title += f"  T.{size}"
    if gender:
        title += f"  {gender}"
    ref  = _sanitize(data.barcode, max_length=24) or "VTZ-NOREF"
    week = _week_label(data)

    # Paysage 640×300 (12 dpmm). Tout centré sur la largeur (^FB640), empilé
    # verticalement dans Y ≤ ~250 (zone imprimable utile) :
    #   y=8  : nom du produit (police 30) → fin y=38
    #   y=46 : code-barres Code 128 décalé à droite, h=90 + interprétation
    #   y=172: semaine (police 30) → fin y=202
    by, bx = _barcode_layout(ref, right_shift=28)
    return (
        "^XA"
        + _zpl_head(pr, md)
        + f"^FO0,8^FB640,1,0,C,0^A0N,30,28^FD{title}^FS"
        + f"^FO{bx},46^BY{by},2.5,90^BCN,90,Y,N,N,A^FD{ref}^FS"
        + f"^FO0,172^FB640,1,0,C,0^A0N,30,28^FD{week}^FS"
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

    # Paysage 640×300, centré, Y ≤ ~270 :
    #   y=20 : "VINTIZ" (police 46) → fin y=66
    #   y=90 : séparateur horizontal
    #   y=105: prix (police 85×52)
    return (
        "^XA"
        + _zpl_head(pr, md)
        + "^FO0,20^FB640,1,0,C,0^A0N,46,42^FDVINTIZ^FS"
        + "^FO40,90^GB560,3,3^FS"
        + f"^FO0,105^FB640,1,0,C,0^A0N,85,52^FD{price}^FS"
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
    category = getattr(product, "category", None)
    category_name = category.name if category else "Article"
    # Le genre du PRODUIT (saisi à l'ajout / proposé par l'image) est la source
    # de la 3e variable ; à défaut (fiches antérieures au champ) on retombe sur
    # le genre de la catégorie. _gender_token() fait l'abréviation côté gabarit.
    gender_raw = getattr(product, "gender", None)
    if gender_raw is None and category is not None:
        gender_raw = getattr(category, "gender", None)
    gender = getattr(gender_raw, "value", gender_raw)
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
        gender=gender,
    )
