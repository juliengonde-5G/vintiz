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
    # Tokenize both sides to avoid "robe" matching "robotique" etc.
    cat_tokens = {tok for tok in cat_norm.split() if len(tok) > 2}
    type_tokens = {tok for tok in types_norm.replace(",", " ").split() if len(tok) > 2}
    return bool(cat_tokens & type_tokens)


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

        Decision rules (deterministic):
        1. If the product is Hot (score ≥ 75) AND there's a window zone with
           ≥ 1 free slot, route to window. The score acts as the green
           light for the spotlight position.
        2. Otherwise, pick the least-saturated zone among those whose
           product_types matches the product's category. Among ties,
           prefer the one with the most free capacity.
        3. If no category match exists, fall back to the least-saturated
           non-window zone overall.
        4. If no zones are configured at all, return a "no suggestion"
           result without raising.

        Returns a ``ZoneSuggestion`` describing the recommendation plus a
        short ``rationale`` Sophie can read out loud.
        """
        zones_result = await self.db.execute(
            select(StoreZone).order_by(StoreZone.display_order, StoreZone.name)
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

        # Resolve product category (if any) — used for matching.
        category: Category | None = None
        if product.category_id is not None:
            cat_row = await self.db.execute(
                select(Category).where(Category.id == product.category_id)
            )
            category = cat_row.scalar_one_or_none()

        bucket = score_bucket(product.trend_score)

        # Rule 1: Hot → window
        for zone in zones:
            if not _is_window_zone(zone):
                continue
            free = (zone.capacity or 0) - load_by_zone.get(zone.id, 0)
            if bucket == "hot" and free >= 1:
                fallback = self._pick_category_zone(
                    zones, load_by_zone, category, exclude_id=zone.id
                )
                return ZoneSuggestion(
                    primary_zone_id=str(zone.id),
                    primary_zone_name=zone.name,
                    alternative_zone_id=str(fallback.id) if fallback else None,
                    alternative_zone_name=fallback.name if fallback else None,
                    should_go_to_window=True,
                    rationale=(
                        f"Score Hot ({product.trend_score:.0f}) — vitrine "
                        f"{zone.name} libre. Si saturée plus tard, replier "
                        f"vers {fallback.name if fallback else 'une zone catégorie'}."
                    ),
                )

        # Rule 2/3: category match → least-loaded
        primary = self._pick_category_zone(zones, load_by_zone, category)
        alternative = (
            self._pick_least_loaded_non_window(
                zones, load_by_zone, exclude_id=primary.id if primary else None
            )
            if primary
            else None
        )
        if primary is not None:
            return ZoneSuggestion(
                primary_zone_id=str(primary.id),
                primary_zone_name=primary.name,
                alternative_zone_id=str(alternative.id) if alternative else None,
                alternative_zone_name=alternative.name if alternative else None,
                should_go_to_window=False,
                rationale=(
                    f"Catégorie {category.name if category else 'inconnue'} → "
                    f"{primary.name} (la moins saturée parmi les zones "
                    f"compatibles)."
                ),
            )

        # Rule 4: no category match anywhere
        fallback = self._pick_least_loaded_non_window(zones, load_by_zone)
        if fallback is None:
            fallback = zones[0]
        return ZoneSuggestion(
            primary_zone_id=str(fallback.id),
            primary_zone_name=fallback.name,
            alternative_zone_id=None,
            alternative_zone_name=None,
            should_go_to_window=False,
            rationale=(
                "Aucune zone n'est typée pour cette catégorie : "
                f"placement par défaut en {fallback.name}."
            ),
        )

    @staticmethod
    def _pick_category_zone(
        zones: Iterable[StoreZone],
        load_by_zone: dict,
        category: Category | None,
        exclude_id=None,
    ) -> StoreZone | None:
        if category is None:
            return None
        matching = [
            z for z in zones
            if _zone_matches_category(z, category)
            and not _is_window_zone(z)
            and z.id != exclude_id
        ]
        if not matching:
            return None
        # Sort by free capacity DESC (most room first), tie-break on display_order.
        matching.sort(
            key=lambda z: (
                -((z.capacity or 0) - load_by_zone.get(z.id, 0)),
                z.display_order,
            )
        )
        return matching[0]

    @staticmethod
    def _pick_least_loaded_non_window(
        zones: Iterable[StoreZone],
        load_by_zone: dict,
        exclude_id=None,
    ) -> StoreZone | None:
        candidates = [
            z for z in zones
            if not _is_window_zone(z) and z.id != exclude_id
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
