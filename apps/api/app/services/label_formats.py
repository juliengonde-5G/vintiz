"""Presets de format d'étiquette Zebra.

Source unique de vérité : la liste exposée par ``GET /api/hardware/label/formats``
et utilisée par l'UI (dropdown des Paramètres > Materiel) comme par les
gabarits ZPL pour traduire un preset en dimensions physiques. Évite que la
caissière ait à mémoriser les couples millimètre du rouleau commandé et
prévient les divergences entre la config et le rendu.

Convention :
- ``width_mm``  = axe printhead (côté large de l'étiquette imprimée)
- ``height_mm`` = axe d'alimentation (côté qui défile)

Le preset ``custom`` est un sentinel : il signifie « dimensions saisies
manuellement », l'UI laisse alors les deux champs mm éditables. Tous les
autres presets verrouillent la saisie sur leurs valeurs.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LabelFormat:
    key: str
    label: str          # affiché dans le dropdown
    width_mm: int       # axe printhead
    height_mm: int      # axe alimentation
    note: str = ""      # contexte court (usage type)


LABEL_FORMAT_PRESETS: tuple[LabelFormat, ...] = (
    LabelFormat(
        key="vintiz_25x52",
        label="Vintiz standard — 25 × 52 mm",
        width_mm=25,
        height_mm=52,
        note="Format papier des produits seconde main (info + prix sur 2 étiquettes).",
    ),
    LabelFormat(
        key="vintiz_32x25",
        label="Petite — 32 × 25 mm",
        width_mm=32,
        height_mm=25,
        note="Accessoires bijoux, petits articles permanents.",
    ),
    LabelFormat(
        key="zebra_40x25",
        label="Compacte — 40 × 25 mm",
        width_mm=40,
        height_mm=25,
        note="Format Z-Perform 40×25 (boîtes carton, étiquettes prix simples).",
    ),
    LabelFormat(
        key="zebra_50x30",
        label="Standard — 50 × 30 mm",
        width_mm=50,
        height_mm=30,
        note="Étiquettes Zebra 50×30 par défaut (boutique, mise en avant).",
    ),
    LabelFormat(
        key="zebra_57x32",
        label="Code-barres — 57 × 32 mm",
        width_mm=57,
        height_mm=32,
        note="Code-barres lisible à 60 cm + texte court.",
    ),
    LabelFormat(
        key="zebra_70x32",
        label="Articulée — 70 × 32 mm",
        width_mm=70,
        height_mm=32,
        note="Étiquette pendentif articulée pour vêtement.",
    ),
    LabelFormat(
        key="zebra_80x120",
        label="Logistique — 80 × 120 mm",
        width_mm=80,
        height_mm=120,
        note="Étiquette transport / adresse colis (encombrant).",
    ),
    LabelFormat(
        key="zebra_102x51",
        label="Adresse — 102 × 51 mm",
        width_mm=102,
        height_mm=51,
        note="Standard Eltron / DHL / Amazon expédition.",
    ),
    LabelFormat(
        key="custom",
        label="Personnalisé (saisie manuelle)",
        width_mm=0,
        height_mm=0,
        note="Saisissez librement la largeur et la hauteur (mm).",
    ),
)


_PRESETS_BY_KEY: dict[str, LabelFormat] = {p.key: p for p in LABEL_FORMAT_PRESETS}


def list_presets() -> list[dict]:
    """Payload prêt à servir au front (un dict simple par preset)."""
    return [
        {
            "key": p.key,
            "label": p.label,
            "width_mm": p.width_mm,
            "height_mm": p.height_mm,
            "note": p.note,
            "is_custom": p.key == "custom",
        }
        for p in LABEL_FORMAT_PRESETS
    ]


def resolve_dimensions(cfg: dict) -> tuple[int, int]:
    """À partir d'une config ``label_printer``, renvoie ``(width_mm, height_mm)``.

    Logique : un preset connu (≠ custom) écrase les ``label_width_mm`` /
    ``label_height_mm`` libres — c'est la valeur du preset qui fait foi, pour
    qu'un appel direct à l'API ne puisse pas imprimer avec des dimensions
    désynchronisées de l'étiquette affichée dans les Paramètres. Inconnu /
    custom / absent → on retombe sur les dimensions libres saisies par
    l'utilisateur (avec 25×52 comme défaut historique).
    """
    key = (cfg.get("label_format") or "").strip()
    preset = _PRESETS_BY_KEY.get(key)
    if preset is not None and not preset.key == "custom" and preset.width_mm > 0 and preset.height_mm > 0:
        return preset.width_mm, preset.height_mm
    w = int(cfg.get("label_width_mm") or 25)
    h = int(cfg.get("label_height_mm") or 52)
    return max(10, w), max(10, h)
