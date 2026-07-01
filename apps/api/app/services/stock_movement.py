"""Mouvements de stock — flux vertical (réserve↔rayon) & horizontal (zone↔zone).

Trois responsabilités :

1. **Historisation** (``record_move``) : chaque déplacement physique écrit une
   ligne ``ProductLocationEvent`` typée (from/to statut + zone), classée en
   ``to_floor`` / ``to_stock`` (vertical), ``zone_change`` (horizontal),
   ``exit`` ou ``intake``. Un changement de zone émet aussi l'évènement
   analytics ``product.zone_changed`` (jusqu'ici défini mais jamais émis).

2. **Exécution scan** (``move_product`` / ``move_by_barcode``) : le moteur
   propose, l'opérateur scanne le code-barres, on applique le mouvement
   physique (transition de statut FSM et/ou changement de zone) en une fois.

3. **Propositions IA** :
   - ``weekly_layout_plan`` — aménagement hebdo HORIZONTAL, travail zone par
     zone : « de la zone A, sortez X, Y, Z → zone B/C ».
   - ``restock_plan`` — achalandage VERTICAL au fil de l'eau : pour chaque zone
     qui se vide (ventes), on remonte de la réserve les pièces qui collent aux
     règles de la zone.

Algorithmes déterministes (offline-friendly, comme ``merchandising.py``).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.events import EventSource, EventType
from app.models.product import Category, Product, ProductStatus
from app.models.product_location import LocationMoveType, ProductLocationEvent
from app.models.store import StoreZone
from app.services.events import EventService
from app.services.merchandising import (
    _is_window_zone,
    _normalize,
    _zone_matches_rules,
    classify_size,
    score_bucket,
)

logger = logging.getLogger("vintiz.stock_movement")


# Statuts « en rayon » (sur la surface de vente) vs « en réserve » (cave).
FLOOR_STATUSES: frozenset[ProductStatus] = frozenset({
    ProductStatus.display,
    ProductStatus.displayed,
    ProductStatus.discounted,
    ProductStatus.deep_discounted,
})
STOCK_STATUSES: frozenset[ProductStatus] = frozenset({
    ProductStatus.stock,
    ProductStatus.tagged,
    ProductStatus.sorted,
    ProductStatus.received,
})
TERMINAL_STATUSES: frozenset[ProductStatus] = frozenset({
    ProductStatus.sold,
    ProductStatus.donated,
    ProductStatus.returned_to_sorting,
    ProductStatus.returned,
    ProductStatus.rejected,
})


def _coerce_status(value) -> ProductStatus | None:
    if value is None:
        return None
    if isinstance(value, ProductStatus):
        return value
    try:
        return ProductStatus(str(value))
    except ValueError:
        return None


def _coerce_uuid(value) -> uuid.UUID | None:
    if value is None or isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


def classify_move(
    from_status: ProductStatus | None,
    to_status: ProductStatus | None,
    from_zone_id: uuid.UUID | None,
    to_zone_id: uuid.UUID | None,
) -> LocationMoveType | None:
    """Classify a (status, zone) diff into a location move type.

    Returns ``None`` when the diff carries no physical relocation (e.g. a pure
    markdown rayon→rayon with the same zone) so we don't pollute the ledger.
    """
    zone_changed = from_zone_id != to_zone_id
    on_floor_before = from_status in FLOOR_STATUSES
    on_floor_after = to_status in FLOOR_STATUSES

    # Sortie définitive (don / retour tri). La vente positionne le statut
    # directement (hors transition) : on ne la classe donc pas ici.
    if to_status in TERMINAL_STATUSES and from_status not in TERMINAL_STATUSES:
        return LocationMoveType.exit
    # Réserve → rayon : mise en rayon (flux vertical montant).
    if not on_floor_before and on_floor_after:
        return LocationMoveType.to_floor
    # Rayon → réserve : retour en cave (flux vertical descendant).
    if on_floor_before and to_status in STOCK_STATUSES:
        return LocationMoveType.to_stock
    # Rayon → rayon avec changement de zone : flux horizontal.
    if on_floor_after and zone_changed:
        return LocationMoveType.zone_change
    # Première arrivée en boutique.
    if from_status is None and to_status is not None:
        return LocationMoveType.intake
    return None


async def record_move(
    db: AsyncSession,
    product: Product,
    *,
    from_status: ProductStatus | str | None,
    to_status: ProductStatus | str | None,
    from_zone_id: uuid.UUID | str | None,
    to_zone_id: uuid.UUID | str | None,
    user_id: uuid.UUID | None = None,
    reason: str | None = None,
    source: str = "manual",
    occurred_at: datetime | None = None,
) -> ProductLocationEvent | None:
    """Write one ``ProductLocationEvent`` for a physical relocation.

    Best-effort: a failure to historise must never roll back the business
    move. Returns the event (or ``None`` when the diff isn't a relocation).
    """
    fs = _coerce_status(from_status)
    ts = _coerce_status(to_status)
    fz = _coerce_uuid(from_zone_id)
    tz = _coerce_uuid(to_zone_id)

    move_type = classify_move(fs, ts, fz, tz)
    if move_type is None:
        return None

    event = ProductLocationEvent(
        product_id=product.id,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        move_type=move_type,
        from_status=fs.value if fs else None,
        to_status=ts.value if ts else None,
        from_zone_id=fz,
        to_zone_id=tz,
        user_id=user_id,
        source=source,
        reason=reason,
    )
    # The ledger is the feature's source of truth (fiche timeline + métriques),
    # so it's written atomically with the move — not swallowed like analytics.
    # None of the callers sit on the fiscal sale path (sales set status
    # directly, never via transition/record_move), so this can't break a sale.
    db.add(event)
    await db.flush()

    # Wire up the long-dormant analytics event for horizontal moves (best-effort).
    if move_type == LocationMoveType.zone_change:
        await EventService(db).emit(
            EventType.product_zone_changed,
            source=EventSource.admin,
            product_id=product.id,
            user_id=user_id,
            meta={
                "from_zone_id": str(fz) if fz else None,
                "to_zone_id": str(tz) if tz else None,
                "reason": reason,
                "move_source": source,
            },
        )
    return event


# ---------------------------------------------------------------------------
# Execution — barcode-driven physical move
# ---------------------------------------------------------------------------


class MovementError(ValueError):
    """Domain rejection surfaced as 4xx by the API layer."""


async def move_product(
    db: AsyncSession,
    product: Product,
    *,
    to_status: ProductStatus | None = None,
    to_zone_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    reason: str | None = None,
    source: str = "scan",
) -> ProductLocationEvent | None:
    """Apply a status and/or zone change to ``product`` and historise it once.

    Status changes go through the FSM (``ProductLifecycleService``) so anchors
    + analytics events fire; we suppress the lifecycle's own location write and
    record a single combined event here (clean timeline even when the operator
    moves a piece from the réserve straight into a specific zone).
    """
    from app.services.product_lifecycle import ProductLifecycleService

    before_status = product.status
    before_zone = product.zone_id

    if to_zone_id is not None:
        # Validate the target zone exists before mutating anything.
        zone = (await db.execute(
            select(StoreZone).where(StoreZone.id == to_zone_id)
        )).scalar_one_or_none()
        if zone is None:
            raise MovementError("zone_not_found")

    if to_status is not None and to_status != before_status:
        if not ProductLifecycleService.is_valid_transition(before_status, to_status):
            raise MovementError(
                f"invalid_transition:{before_status.value}->{to_status.value}"
            )
        await ProductLifecycleService(db).transition(
            product, to_status, user_id=user_id, reason=reason, record_location=False
        )

    if to_zone_id is not None and to_zone_id != before_zone:
        product.zone_id = to_zone_id
        await db.flush()
    elif (
        to_zone_id is None
        and to_status is not None
        and to_status in STOCK_STATUSES
        and before_zone is not None
    ):
        # Retour en réserve : la cave n'a pas de zones — on libère la zone
        # d'où vient la pièce (sinon l'historique d'emplacement et le plan
        # boutique garderaient un fantôme de placement).
        product.zone_id = None
        await db.flush()

    return await record_move(
        db,
        product,
        from_status=before_status,
        to_status=product.status,
        from_zone_id=before_zone,
        to_zone_id=product.zone_id,
        user_id=user_id,
        reason=reason,
        source=source,
    )


async def move_by_barcode(
    db: AsyncSession,
    barcode: str,
    *,
    to_status: ProductStatus | None = None,
    to_zone_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    reason: str | None = None,
    source: str = "scan",
) -> tuple[Product, ProductLocationEvent | None]:
    """Resolve a product by its (exact) barcode and move it. The whole
    movement module is barcode-first: the engine proposes, the operator scans,
    the move executes."""
    cleaned = (barcode or "").strip()
    if not cleaned:
        raise MovementError("empty_barcode")
    # Tolérance douchette AZERTY : le « - » des codes-barres Vintiz peut arriver
    # en « = ». On essaie le code tel quel puis sa variante tirets.
    candidates = [cleaned]
    if "=" in cleaned:
        candidates.append(cleaned.replace("=", "-"))
    product = (await db.execute(
        select(Product).where(Product.barcode.in_(candidates))
    )).scalar_one_or_none()
    if product is None:
        raise MovementError("product_not_found")
    event = await move_product(
        db,
        product,
        to_status=to_status,
        to_zone_id=to_zone_id,
        user_id=user_id,
        reason=reason,
        source=source,
    )
    return product, event


# ---------------------------------------------------------------------------
# Location history (fiche produit)
# ---------------------------------------------------------------------------


async def location_history(
    db: AsyncSession, product_id: uuid.UUID, *, limit: int = 100
) -> list[dict]:
    """Chronological location timeline for a product's sheet (newest first)."""
    capped = min(max(limit, 1), 500)
    rows = (await db.execute(
        select(ProductLocationEvent)
        .where(ProductLocationEvent.product_id == product_id)
        .order_by(ProductLocationEvent.occurred_at.desc())
        .limit(capped)
    )).scalars().all()

    zone_ids = {z for r in rows for z in (r.from_zone_id, r.to_zone_id) if z}
    zone_names: dict = {}
    if zone_ids:
        zrows = await db.execute(
            select(StoreZone.id, StoreZone.name).where(StoreZone.id.in_(zone_ids))
        )
        zone_names = {zid: zname for zid, zname in zrows.all()}

    return [
        {
            "id": str(r.id),
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "move_type": r.move_type.value,
            "from_status": r.from_status,
            "to_status": r.to_status,
            "from_zone_id": str(r.from_zone_id) if r.from_zone_id else None,
            "from_zone_name": zone_names.get(r.from_zone_id),
            "to_zone_id": str(r.to_zone_id) if r.to_zone_id else None,
            "to_zone_name": zone_names.get(r.to_zone_id),
            "source": r.source,
            "reason": r.reason,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Proposal engines — shared zone-matching (batched, no per-product DB call)
# ---------------------------------------------------------------------------


def _product_gender_token(product: Product, category: Category | None) -> str | None:
    g = getattr(product, "gender", None)
    if g is not None:
        return g.value
    if category and category.gender is not None:
        return category.gender.value
    return None


def _best_zone_for(
    product: Product,
    category: Category | None,
    zones: list[StoreZone],
    load_by_zone: dict[uuid.UUID, int],
    *,
    exclude_window: bool = False,
) -> StoreZone | None:
    """Top auto-assign zone matching a product's rules, capacity-aware.

    Batched twin of ``MerchandisingService.suggest_zone`` (no DB call) so a
    whole-floor plan stays a couple of queries.
    """
    gender_token = _product_gender_token(product, category)
    color_norm = _normalize(product.color)
    size_class = classify_size(product.size)
    score = product.trend_score

    def _free(z: StoreZone) -> int:
        return (z.capacity or 0) - load_by_zone.get(z.id, 0)

    matches = [
        z for z in zones
        if z.auto_assign
        and not (exclude_window and _is_window_zone(z))
        and _free(z) >= 1
        and _zone_matches_rules(
            z, gender_token=gender_token, color_norm=color_norm,
            size_class=size_class, score=score, category=category,
        )
    ]
    if not matches:
        return None
    matches.sort(key=lambda z: (z.assignment_priority, -_free(z), z.display_order))
    return matches[0]


async def _load_floor_state(db: AsyncSession):
    """Return (zones, products_on_floor, categories_by_id, load_by_zone)."""
    zones = (await db.execute(
        select(StoreZone).order_by(
            StoreZone.assignment_priority, StoreZone.display_order, StoreZone.name
        )
    )).scalars().all()

    products = (await db.execute(
        select(Product).where(Product.status.in_(tuple(FLOOR_STATUSES)))
    )).scalars().all()

    cat_ids = {p.category_id for p in products if p.category_id}
    categories: dict[uuid.UUID, Category] = {}
    if cat_ids:
        crows = (await db.execute(
            select(Category).where(Category.id.in_(cat_ids))
        )).scalars().all()
        categories = {c.id: c for c in crows}

    load_by_zone: dict[uuid.UUID, int] = {}
    for p in products:
        if p.zone_id is not None:
            load_by_zone[p.zone_id] = load_by_zone.get(p.zone_id, 0) + 1

    return list(zones), list(products), categories, load_by_zone


async def weekly_layout_plan(db: AsyncSession, *, max_moves_per_zone: int = 8) -> dict:
    """Aménagement HORIZONTAL de la semaine, travaillé zone par zone.

    Pour chaque produit en rayon, on calcule la zone qui colle le mieux à ses
    règles (genre / score tendance / couleur / taille / catégorie). S'il n'est
    pas déjà dans cette zone → proposition de déplacement, regroupée par zone
    d'origine (« de la zone A, déplacez ces pièces vers B/C »).
    """
    zones, products, categories, load = await _load_floor_state(db)
    zone_by_id = {z.id: z for z in zones}
    if not zones:
        return {"generated_at": datetime.now(timezone.utc).isoformat(),
                "total_moves": 0, "zones": []}

    # Work on a mutable copy of the load so capacity is respected as we plan.
    plan_load = dict(load)
    # Move the lowest-fit pieces first (low score → most likely misplaced).
    ordered = sorted(
        products,
        key=lambda p: (p.trend_score if p.trend_score is not None else 50.0),
    )

    by_source: dict[uuid.UUID | None, list[dict]] = {}
    total = 0
    for product in ordered:
        category = categories.get(product.category_id)
        current_zone = zone_by_id.get(product.zone_id) if product.zone_id else None
        target = _best_zone_for(product, category, zones, plan_load, exclude_window=True)
        if target is None or target.id == product.zone_id:
            continue
        # Reflect the planned move in the running load so we don't overfill.
        if product.zone_id is not None and plan_load.get(product.zone_id):
            plan_load[product.zone_id] -= 1
        plan_load[target.id] = plan_load.get(target.id, 0) + 1

        bucket = by_source.setdefault(product.zone_id, [])
        if len(bucket) >= max_moves_per_zone:
            continue
        bucket.append({
            "product_id": str(product.id),
            "barcode": product.barcode,
            "name": product.name,
            "brand": product.brand,
            "size": product.size,
            "color": product.color,
            "trend_score": float(product.trend_score) if product.trend_score is not None else None,
            "score_bucket": score_bucket(product.trend_score),
            "to_zone_id": str(target.id),
            "to_zone_name": target.name,
            "rationale": _move_rationale(product, current_zone, target),
        })
        total += 1

    zones_out = []
    for source_id, items in by_source.items():
        if not items:
            continue
        src = zone_by_id.get(source_id) if source_id else None
        zones_out.append({
            "from_zone_id": str(source_id) if source_id else None,
            "from_zone_name": src.name if src else "Sans zone",
            "n_moves": len(items),
            "items": items,
        })
    zones_out.sort(key=lambda z: -z["n_moves"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_moves": total,
        "zones": zones_out,
    }


def _move_rationale(
    product: Product, current: StoreZone | None, target: StoreZone
) -> str:
    bucket = score_bucket(product.trend_score)
    bits: list[str] = []
    if _is_window_zone(target):
        bits.append("vitrine")
    if bucket in {"hot", "warm"}:
        bits.append(f"score {bucket}")
    elif bucket in {"slow", "cold"}:
        bits.append("rotation lente")
    if product.brand:
        bits.append(product.brand)
    detail = " · ".join(bits) if bits else "meilleure adéquation zone"
    src = current.name if current else "réserve/sans zone"
    return f"{src} → {target.name} ({detail})."


async def restock_plan(
    db: AsyncSession,
    *,
    period_days: int = 14,
    target_fill_pct: float = 0.85,
    max_candidates_per_zone: int = 6,
) -> dict:
    """Achalandage VERTICAL au fil de l'eau (réserve → rayon).

    Pour chaque zone dont l'occupation est sous ``target_fill_pct`` (les ventes
    l'ont vidée), on calcule le déficit en pièces et on propose des articles
    de la réserve qui collent aux règles de la zone — priorisés par leur score
    tendance. Le signal « besoin » est renforcé par les ventes récentes de la
    zone (plus une zone vend, plus on la réachalande).
    """
    zones, on_floor, categories, load = await _load_floor_state(db)
    if not zones:
        return {"generated_at": datetime.now(timezone.utc).isoformat(),
                "period_days": period_days, "zones": []}

    # Stock products available to bring up to the floor.
    stock_products = (await db.execute(
        select(Product).where(
            Product.status == ProductStatus.stock,
            Product.is_test.is_(False),
        )
    )).scalars().all()
    stock_cat_ids = {p.category_id for p in stock_products if p.category_id}
    if stock_cat_ids:
        crows = (await db.execute(
            select(Category).where(Category.id.in_(stock_cat_ids))
        )).scalars().all()
        for c in crows:
            categories.setdefault(c.id, c)

    sold_by_zone = await _sold_by_zone(db, period_days=period_days)

    plan_load = dict(load)
    zones_out: list[dict] = []
    for zone in zones:
        if not zone.auto_assign or _is_window_zone(zone):
            continue
        cap = zone.capacity or 0
        if cap <= 0:
            continue
        current = plan_load.get(zone.id, 0)
        target_fill = int(cap * target_fill_pct)
        deficit = max(0, target_fill - current)
        recent_sales = sold_by_zone.get(zone.id, 0)
        # A zone needs restocking if it has room AND either it's notably empty
        # or it sold recently (demand pulled stock off the floor).
        if deficit <= 0 and recent_sales == 0:
            continue

        # Candidate stock pieces whose rules match this zone, best score first.
        candidates = [
            p for p in stock_products
            if _zone_matches_rules(
                zone,
                gender_token=_product_gender_token(p, categories.get(p.category_id)),
                color_norm=_normalize(p.color),
                size_class=classify_size(p.size),
                score=p.trend_score,
                category=categories.get(p.category_id),
            )
        ]
        candidates.sort(
            key=lambda p: (p.trend_score if p.trend_score is not None else 0.0),
            reverse=True,
        )
        n_propose = min(max(deficit, 1 if recent_sales else 0), max_candidates_per_zone)
        picks = candidates[:n_propose]
        if not picks:
            continue

        zones_out.append({
            "zone_id": str(zone.id),
            "zone_name": zone.name,
            "capacity": cap,
            "current": current,
            "occupancy_pct": round(100 * current / cap, 1) if cap else None,
            "deficit": deficit,
            "recent_sales": recent_sales,
            "candidates": [
                {
                    "product_id": str(p.id),
                    "barcode": p.barcode,
                    "name": p.name,
                    "brand": p.brand,
                    "size": p.size,
                    "color": p.color,
                    "trend_score": float(p.trend_score) if p.trend_score is not None else None,
                    "score_bucket": score_bucket(p.trend_score),
                }
                for p in picks
            ],
        })
        # Reserve the proposed pieces against the running load.
        plan_load[zone.id] = current + len(picks)

    # Most-depleted / best-selling zones first.
    zones_out.sort(key=lambda z: (-(z["recent_sales"]), -(z["deficit"])))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_days": period_days,
        "stock_available": len(stock_products),
        "zones": zones_out,
    }


async def _sold_by_zone(db: AsyncSession, *, period_days: int) -> dict[uuid.UUID, int]:
    """Count items sold per zone over the window (demand signal per zone).

    Uses the zone the sold product was sitting in (``products.zone_id``)."""
    from app.models.pos import Transaction, TransactionItem, TransactionType

    cutoff = datetime.now(timezone.utc) - _timedelta_days(period_days)
    rows = await db.execute(
        select(Product.zone_id, func.count(TransactionItem.id))
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= cutoff,
            Product.zone_id.is_not(None),
        )
        .group_by(Product.zone_id)
    )
    return {zid: int(n) for zid, n in rows.all() if zid is not None}


def _timedelta_days(days: int):
    from datetime import timedelta

    return timedelta(days=days)
