"""Merchandising / store-plan helpers (P2-005 → P2-008).

One service to keep the four moving parts coherent:
- ``zone_occupancy``        — store-plan view (P2-005)
- ``suggest_zone``          — automatic placement on tagging (P2-006)
- ``propose_weekly_window`` — Monday 06:00 cron output (P2-007)
- ``locate_product``        — "Où est cette pièce ?" (P2-008)

The placement and window algorithms are deterministic so they're cheap
and offline-friendly; a follow-up will optionally chain Claude on top
(prompts §7.2 + §7.6 of the audit).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.merchandising import WindowDisplayProposal
from app.models.product import Category, Product, ProductStatus
from app.models.store import StoreZone

logger = logging.getLogger("vintiz")


# ---------------------------------------------------------------------------
# Score buckets (Hot / Warm / Slow / Cold), aligned with V1 audit §5.3.
# ---------------------------------------------------------------------------


SCORE_HOT_FLOOR = 75.0
SCORE_WARM_FLOOR = 50.0
SCORE_SLOW_FLOOR = 25.0


def score_bucket(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= SCORE_HOT_FLOOR:
        return "hot"
    if score >= SCORE_WARM_FLOOR:
        return "warm"
    if score >= SCORE_SLOW_FLOOR:
        return "slow"
    return "cold"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _is_window_zone(zone: StoreZone) -> bool:
    """Heuristic: zones whose name or product_types mentions 'vitrine'."""
    haystack = _normalize(f"{zone.name} {zone.product_types or ''}")
    return "vitrine" in haystack


def _zone_matches_category(zone: StoreZone, category: Category | None) -> bool:
    if category is None or not zone.product_types:
        return False
    cat_norm = _normalize(category.name)
    types_norm = _normalize(zone.product_types)
    if not cat_norm:
        return False
    # product_types peut être un tableau JSON ('["robe","robes"]') ou une
    # chaîne CSV ; on neutralise crochets/guillemets avant de tokeniser.
    types_norm = re.sub(r'[\[\]"]', " ", types_norm)
    # Tokenize both sides to avoid "robe" matching "robotique" etc.
    cat_tokens = {tok for tok in cat_norm.split() if len(tok) > 2}
    type_tokens = {tok for tok in types_norm.replace(",", " ").split() if len(tok) > 2}
    return bool(cat_tokens & type_tokens)


def _color_matches(color_norm: str, tokens: list | None) -> bool:
    """True si la couleur (normalisée) partage un token avec la liste de la
    zone. « bleu marine » matche ["bleu"] ; insensible casse/accents."""
    if not tokens or not color_norm:
        return False
    color_tokens = {tok for tok in color_norm.split() if tok}
    want = {_normalize(str(t)) for t in tokens if t}
    return bool(color_tokens & want)


# Classes de tailles pour les règles "grandes tailles" / "petites tailles".
_SIZE_PETITE = {"XXS", "XS", "S"}
_SIZE_STANDARD = {"M", "L"}
_SIZE_GRANDE = {"XL", "XXL", "XXXL", "2XL", "3XL", "4XL"}


def classify_size(size: str | None) -> str | None:
    """Mappe une taille libre vers 'petite' / 'standard' / 'grande' (ou None).

    Lettres (XS…XXXL) + numériques vêtement (≤36 petite, 38-42 standard,
    ≥44 grande). Les chaussures sont routées par catégorie avant toute
    condition de taille → un mauvais classement numérique reste sans effet.
    """
    if not size:
        return None
    s = size.strip().upper().replace(" ", "")
    if not s:
        return None
    if "GRANDE" in s:
        return "grande"
    if s in _SIZE_PETITE:
        return "petite"
    if s in _SIZE_STANDARD:
        return "standard"
    if s in _SIZE_GRANDE:
        return "grande"
    m = re.match(r"(\d+)", s)
    if m:
        n = int(m.group(1))
        if n <= 36:
            return "petite"
        if n <= 42:
            return "standard"
        return "grande"
    return None


def _zone_matches_rules(
    zone: StoreZone,
    *,
    gender_token: str | None,
    color_norm: str,
    size_class: str | None,
    score: float | None,
    category: Category | None,
) -> bool:
    """True si le produit satisfait TOUTES les conditions posées sur la zone.

    Une condition absente (None / liste vide) n'est pas testée — donc une zone
    avec seulement match_genders=["homme"] est le fourre-tout homme.
    """
    if zone.match_genders:
        if gender_token is None or gender_token not in set(zone.match_genders):
            return False
    if zone.min_trend_score is not None:
        if score is None or float(score) < float(zone.min_trend_score):
            return False
    if zone.match_colors:
        if not _color_matches(color_norm, zone.match_colors):
            return False
    if zone.match_size_classes:
        if size_class is None or size_class not in set(zone.match_size_classes):
            return False
    if zone.product_types:
        if not _zone_matches_category(zone, category):
            return False
    return True


def _suggestion_rationale(
    zone: StoreZone,
    product: Product,
    category: Category | None,
    gender_token: str | None,
    size_class: str | None,
    score: float | None,
) -> str:
    """Phrase courte expliquant l'affectation (lisible au comptoir)."""
    if _is_window_zone(zone):
        s = f"{score:.0f}" if score is not None else "?"
        return f"Score tendance {s} — vitrine {zone.name} libre."
    if zone.min_trend_score is not None:
        s = f"{score:.0f}" if score is not None else "?"
        return f"Tendance (score {s} ≥ {float(zone.min_trend_score):.0f}) → {zone.name}."
    bits: list[str] = []
    if gender_token:
        bits.append(gender_token)
    if zone.match_colors and product.color:
        bits.append(f"couleur {product.color}")
    if zone.match_size_classes and size_class:
        bits.append(f"taille {size_class}")
    if zone.product_types and category:
        bits.append(category.name)
    detail = " · ".join(bits) if bits else "placement"
    return f"{detail} → {zone.name}."


@dataclass
class ZoneSuggestion:
    primary_zone_id: str | None
    primary_zone_name: str | None
    alternative_zone_id: str | None
    alternative_zone_name: str | None
    should_go_to_window: bool
    rationale: str


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MerchandisingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- Store-plan view (P2-005) ------------------------------------------

    async def zone_occupancy(self) -> list[dict]:
        """Return one row per zone with current occupancy + score colour map."""
        zones_result = await self.db.execute(
            select(StoreZone).order_by(StoreZone.display_order, StoreZone.name)
        )
        zones = zones_result.scalars().all()
        if not zones:
            return []

        # One DB call to count + score per zone.
        agg_result = await self.db.execute(
            select(
                Product.zone_id,
                func.count(Product.id).label("n"),
                func.avg(Product.trend_score).label("avg_score"),
            )
            .where(
                Product.zone_id.is_not(None),
                Product.status.in_(
                    [ProductStatus.display, ProductStatus.displayed,
                     ProductStatus.discounted, ProductStatus.deep_discounted]
                ),
            )
            .group_by(Product.zone_id)
        )
        agg_by_zone = {row.zone_id: row for row in agg_result.all()}

        rows: list[dict] = []
        for zone in zones:
            agg = agg_by_zone.get(zone.id)
            n = int(agg.n) if agg else 0
            avg_score = float(agg.avg_score) if agg and agg.avg_score is not None else None
            occupancy_pct = (
                round(100 * n / zone.capacity, 1) if zone.capacity else None
            )
            rows.append({
                "id": str(zone.id),
                "name": zone.name,
                "description": zone.description,
                "capacity": zone.capacity,
                "product_types": zone.product_types,
                "color_code": zone.color_code,
                "icon": zone.icon,
                "is_window": _is_window_zone(zone),
                "pos_x": zone.pos_x,
                "pos_y": zone.pos_y,
                "width": zone.width,
                "height": zone.height,
                "shape": zone.shape,
                "n_products": n,
                "occupancy_pct": occupancy_pct,
                "avg_score": round(avg_score, 1) if avg_score is not None else None,
                "score_bucket": score_bucket(avg_score),
            })
        return rows

    # -- Suggest zone for a product (P2-006) -------------------------------

    async def suggest_zone(self, product: Product) -> ZoneSuggestion:
        """Pick the zone where a freshly-tagged product should land.

        Moteur par règles (cascade gender-first, capacity-aware) : on évalue
        les zones par ``assignment_priority`` croissant ; pour chaque zone
        ``auto_assign`` on vérifie que TOUTES ses conditions présentes (genre /
        score tendance / couleur / classe de taille / catégorie) passent et
        qu'il reste ≥ 1 place. La 1re zone qui matche est primaire, la suivante
        alternative ; à priorité égale on préfère la plus de place libre.

        Reste consultatif : l'opérateur confirme à l'étiquetage. Les règles
        sont éditables en base (/zones), pas codées en dur.
        """
        zones_result = await self.db.execute(
            select(StoreZone).order_by(
                StoreZone.assignment_priority, StoreZone.display_order, StoreZone.name
            )
        )
        zones = zones_result.scalars().all()
        if not zones:
            logger.warning(
                "suggest_zone: aucune zone configurée — product_id=%s, fallback rationale renvoyé",
                product.id,
            )
            return ZoneSuggestion(
                primary_zone_id=None, primary_zone_name=None,
                alternative_zone_id=None, alternative_zone_name=None,
                should_go_to_window=False,
                rationale="Aucune zone configurée. Configurez d'abord le plan boutique.",
            )

        # Compute current load per zone in one query.
        load_result = await self.db.execute(
            select(Product.zone_id, func.count(Product.id))
            .where(
                Product.zone_id.is_not(None),
                Product.status.in_(
                    [ProductStatus.display, ProductStatus.displayed,
                     ProductStatus.discounted, ProductStatus.deep_discounted]
                ),
            )
            .group_by(Product.zone_id)
        )
        load_by_zone = {row[0]: int(row[1]) for row in load_result.all()}

        # Resolve product category (carries gender) — used for matching.
        category: Category | None = None
        if product.category_id is not None:
            cat_row = await self.db.execute(
                select(Category).where(Category.id == product.category_id)
            )
            category = cat_row.scalar_one_or_none()

        # Le genre du PRODUIT (saisi à l'ajout / proposé par l'image) prime ;
        # à défaut (fiches antérieures au champ), on retombe sur celui de la
        # catégorie. C'est la base de l'affectation de zone.
        product_gender = getattr(product, "gender", None)
        if product_gender is not None:
            gender_token = product_gender.value
        elif category and category.gender is not None:
            gender_token = category.gender.value
        else:
            gender_token = None
        color_norm = _normalize(product.color)
        size_class = classify_size(product.size)
        score = product.trend_score

        def _free(zone: StoreZone) -> int:
            return (zone.capacity or 0) - load_by_zone.get(zone.id, 0)

        matches = [
            z for z in zones
            if z.auto_assign
            and _free(z) >= 1
            and _zone_matches_rules(
                z, gender_token=gender_token, color_norm=color_norm,
                size_class=size_class, score=score, category=category,
            )
        ]
        # Priorité croissante ; à égalité, plus de place libre puis display_order.
        matches.sort(key=lambda z: (z.assignment_priority, -_free(z), z.display_order))

        if matches:
            primary = matches[0]
            alternative = matches[1] if len(matches) > 1 else None
            return ZoneSuggestion(
                primary_zone_id=str(primary.id),
                primary_zone_name=primary.name,
                alternative_zone_id=str(alternative.id) if alternative else None,
                alternative_zone_name=alternative.name if alternative else None,
                should_go_to_window=_is_window_zone(primary),
                rationale=_suggestion_rationale(
                    primary, product, category, gender_token, size_class, score
                ),
            )

        # Aucune règle ne matche (ou tout est plein) → zone la moins chargée
        # parmi les zones auto_assign hors vitrine.
        fallback = self._pick_least_loaded_non_window(zones, load_by_zone)
        if fallback is None:
            fallback = zones[0]
        return ZoneSuggestion(
            primary_zone_id=str(fallback.id),
            primary_zone_name=fallback.name,
            alternative_zone_id=None,
            alternative_zone_name=None,
            should_go_to_window=_is_window_zone(fallback),
            rationale=(
                "Aucune zone ne correspond aux règles : "
                f"placement par défaut en {fallback.name}."
            ),
        )

    @staticmethod
    def _pick_least_loaded_non_window(
        zones: Iterable[StoreZone],
        load_by_zone: dict,
        exclude_id=None,
    ) -> StoreZone | None:
        candidates = [
            z for z in zones
            if not _is_window_zone(z) and z.auto_assign and z.id != exclude_id
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda z: (
                -((z.capacity or 0) - load_by_zone.get(z.id, 0)),
                z.display_order,
            )
        )
        return candidates[0]

    # -- Locate (P2-008) ---------------------------------------------------

    async def locate_product(self, query: str) -> list[dict]:
        """Resolve an ambiguous query (barcode or name fragment) into one
        or more on-floor products with their zone label."""
        cleaned = (query or "").strip()
        if not cleaned:
            return []

        # Exact barcode wins.
        exact = await self.db.execute(
            select(Product, StoreZone)
            .outerjoin(StoreZone, Product.zone_id == StoreZone.id)
            .where(Product.barcode == cleaned)
        )
        rows = list(exact.all())
        if not rows:
            like = f"%{cleaned}%"
            fuzzy = await self.db.execute(
                select(Product, StoreZone)
                .outerjoin(StoreZone, Product.zone_id == StoreZone.id)
                .where(or_(Product.name.ilike(like), Product.barcode.ilike(like)))
                .limit(20)
            )
            rows = list(fuzzy.all())

        return [
            {
                "id": str(product.id),
                "barcode": product.barcode,
                "name": product.name,
                "status": product.status.value,
                "sale_price": float(product.sale_price),
                "zone_id": str(zone.id) if zone else None,
                "zone_name": zone.name if zone else None,
                "zone_color": zone.color_code if zone else None,
                "zone_icon": zone.icon if zone else None,
            }
            for product, zone in rows
        ]

    # -- Weekly window proposal (P2-007) -----------------------------------

    @staticmethod
    def iso_week_key(when: datetime | None = None) -> str:
        when = when or datetime.now(timezone.utc)
        year, week, _ = when.isocalendar()
        return f"{year}-W{week:02d}"

    async def propose_weekly_window(
        self,
        *,
        target_pieces: int = 8,
        when: datetime | None = None,
    ) -> WindowDisplayProposal:
        """Build the proposal for the running ISO week and upsert it.

        Deterministic algorithm:
        - Score-sort all displayable products by trend_score desc (None last).
        - Walk the list keeping at most 1 product per category to maximise
          variety, until ``target_pieces`` is reached.
        - Tag the first item as 'central', the next two as 'left' / 'right',
          the rest 'back' to give Sophie a layout hint without over-
          engineering.
        - Theme = top brand among picks (or "Sélection mixte" if no brand
          dominates).
        """
        result = await self.db.execute(
            select(Product)
            .where(
                Product.status.in_(
                    [ProductStatus.display, ProductStatus.displayed,
                     ProductStatus.discounted, ProductStatus.deep_discounted]
                )
            )
            .order_by(
                desc(func.coalesce(Product.trend_score, 0)),
                desc(Product.created_at),
            )
        )
        candidates = list(result.scalars().all())

        seen_categories: set = set()
        picks: list[Product] = []
        for product in candidates:
            if product.category_id in seen_categories:
                continue
            picks.append(product)
            seen_categories.add(product.category_id)
            if len(picks) >= target_pieces:
                break

        # If diversity-by-category killed the pool too early, top up with
        # the next best products regardless of category.
        if len(picks) < target_pieces:
            picked_ids = {p.id for p in picks}
            for product in candidates:
                if product.id in picked_ids:
                    continue
                picks.append(product)
                if len(picks) >= target_pieces:
                    break

        positions = ["central", "left", "right"] + ["back"] * max(
            0, len(picks) - 3
        )
        items = [
            {
                "product_id": str(p.id),
                "barcode": p.barcode,
                "name": p.name,
                "brand": p.brand,
                "color": p.color,
                "sale_price": float(p.sale_price),
                "trend_score": p.trend_score,
                "position": positions[idx] if idx < len(positions) else "back",
                "rationale": _pick_rationale(p),
            }
            for idx, p in enumerate(picks)
        ]

        brand_counts = Counter(p.brand for p in picks if p.brand)
        if brand_counts and brand_counts.most_common(1)[0][1] >= 2:
            theme = f"Mise en avant {brand_counts.most_common(1)[0][0]}"
        else:
            theme = "Sélection mixte de la semaine"

        proposal = {
            "theme": theme,
            "color_palette": _palette_from_picks(picks),
            "items": items,
            "next_review_date": _next_monday(when).date().isoformat(),
        }

        iso_week = self.iso_week_key(when)
        existing_row = await self.db.execute(
            select(WindowDisplayProposal).where(
                WindowDisplayProposal.iso_week == iso_week
            )
        )
        existing = existing_row.scalar_one_or_none()
        if existing is None:
            row = WindowDisplayProposal(
                iso_week=iso_week,
                proposal=proposal,
                used_llm=False,
            )
            self.db.add(row)
            await self.db.flush()
            return row
        existing.proposal = proposal
        existing.used_llm = False
        existing.accepted_at = None
        existing.accepted_by_user_id = None
        await self.db.flush()
        return existing

    async def get_current_window_proposal(
        self, when: datetime | None = None
    ) -> WindowDisplayProposal | None:
        iso_week = self.iso_week_key(when)
        result = await self.db.execute(
            select(WindowDisplayProposal).where(
                WindowDisplayProposal.iso_week == iso_week
            )
        )
        return result.scalar_one_or_none()

    async def accept_window_proposal(
        self, proposal_id, user_id
    ) -> WindowDisplayProposal:
        from fastapi import HTTPException

        result = await self.db.execute(
            select(WindowDisplayProposal).where(
                WindowDisplayProposal.id == proposal_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        row.accepted_at = datetime.now(timezone.utc)
        row.accepted_by_user_id = user_id
        await self.db.flush()
        return row


# ---------------------------------------------------------------------------
# Small helpers used only by propose_weekly_window
# ---------------------------------------------------------------------------


def _pick_rationale(product: Product) -> str:
    bucket = score_bucket(product.trend_score)
    bits = []
    if bucket == "hot":
        bits.append("score Hot")
    elif bucket == "warm":
        bits.append("score Warm")
    if product.brand:
        bits.append(f"marque {product.brand}")
    if product.color:
        bits.append(f"couleur {product.color}")
    return ", ".join(bits) or "Pièce de la semaine"


def _palette_from_picks(picks: Iterable[Product]) -> list[str]:
    """Compose a palette by mapping the most-frequent product colours to
    soft hex hints. Limited to 3 entries to keep Sophie's vitrine
    readable."""
    color_to_hex = {
        "noir": "#1a1a1a",
        "blanc": "#f5f5f5",
        "gris": "#9aa0a6",
        "beige": "#e8d5b7",
        "camel": "#c19a6b",
        "rose": "#fbcfe8",
        "bleu": "#bfdbfe",
        "vert": "#bbf7d0",
        "jaune": "#fef08a",
        "rouge": "#fecaca",
        "marron": "#a78b6b",
    }
    counts = Counter(
        _normalize(p.color or "") for p in picks if p.color
    )
    palette: list[str] = []
    for color, _ in counts.most_common(3):
        for key, hex_value in color_to_hex.items():
            if key in color:
                palette.append(hex_value)
                break
    return palette or ["#fff3ed", "#ffc5df", "#008678"]


def _next_monday(when: datetime | None) -> datetime:
    when = when or datetime.now(timezone.utc)
    days_until_monday = (7 - when.weekday()) % 7 or 7
    from datetime import timedelta

    return when + timedelta(days=days_until_monday)
