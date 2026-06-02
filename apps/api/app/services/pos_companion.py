"""POS Companion — cart-aware up-sells at client identification (PR4).

When the cashier identifies a client at the POS, this service returns a
single payload aggregating everything the cashier needs to drive the next
action:

- ``loyalty.points_current`` and ``would_earn`` (1 € = 1 pt rounded down).
- ``loyalty.can_redeem_max_cents`` capped at 50 % of the cart.
- ``suggestions``: 3 complementary products surfaced from
  :func:`PersonalShopperService` filtered by category complement
  (e.g. robe → accessoires/chaussures).
- ``coupons``: active coupons applicable for this client (via
  :func:`coupon.validate_coupon`).
- ``alerts``: lightweight cards combining RFM segment hints,
  birthday-in-7-days, and an "encore 14 € pour le prochain bon d'achat".

The endpoint is called on every cart mutation so the implementation
keeps the latency budget under 200 ms — heavy queries are gated behind
``client_id is not None``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client import Client, LoyaltyTransaction, LoyaltyTxType
from app.models.coupon import Coupon
from app.models.embeddings import ProductEmbedding
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Product, ProductStatus
from app.models.store import StoreZone
from app.services.embeddings import _cosine, _l2_normalize


logger = logging.getLogger("vintiz.pos_companion")


# Mapping from a "category just added to cart" → categories worth
# pushing as complementary suggestions. Conservative on purpose: each
# row is a small basket of related categories so the cashier's
# suggestion panel stays relevant.
CATEGORY_COMPLEMENTS: dict[str, tuple[str, ...]] = {
    "robe": ("accessoire", "chaussures", "sac", "veste"),
    "jupe": ("chemise", "pull", "ceinture"),
    "jean": ("chemise", "pull", "ceinture", "chaussures"),
    "pantalon": ("chemise", "pull", "ceinture", "chaussures"),
    "t-shirt": ("jean", "pantalon", "veste"),
    "chemise": ("jean", "pantalon", "veste", "ceinture"),
    "pull": ("jean", "jupe", "echarpe"),
    "veste": ("robe", "pantalon", "echarpe"),
    "manteau": ("echarpe", "bonnet", "gants"),
    "chaussures": ("sac", "ceinture"),
    "sac": ("ceinture", "echarpe"),
}

# Frequency cap: skip the "anniversary in 7d" card if we've already
# proposed it to this client too recently. (Cap held in the alert list,
# not persisted — the cashier only sees fresh info.)
BIRTHDAY_WINDOW_DAYS = 7


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _normalize_category(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip().lower()
    # Normalise common spellings so the mapping above keeps working.
    swaps = {
        "tshirt": "t-shirt",
        "tee-shirt": "t-shirt",
        "jeans": "jean",
        "robes": "robe",
        "chaussure": "chaussures",
        "écharpe": "echarpe",
        "echarpes": "echarpe",
    }
    return swaps.get(raw, raw)


def _points_to_credit(amount_cents: int) -> int:
    """Mirror :func:`offers_engine.points_to_credit` but in cents."""
    return max(0, int(amount_cents // 100))


def _redemption_cap_cents(cart_total_cents: int, points: int) -> int:
    """1 pt = 0.10 €, max 50 % of the cart."""
    available = points * 10  # cents
    half_cart = cart_total_cents // 2
    return max(0, min(available, half_cart))


async def _resolve_complement_categories(
    db: AsyncSession, raw_categories: list[str]
) -> list[uuid.UUID]:
    """Map raw category names from the cart to category ids worth pushing."""
    wanted: set[str] = set()
    for raw in raw_categories:
        canonical = _normalize_category(raw)
        if canonical and canonical in CATEGORY_COMPLEMENTS:
            wanted.update(CATEGORY_COMPLEMENTS[canonical])
    if not wanted:
        return []
    rows = await db.execute(
        select(Category.id, Category.name).where(
            Category.name.in_(list(wanted))
        )
    )
    return [row[0] for row in rows.all()]


async def _suggest_complementary(
    db: AsyncSession,
    *,
    client: Client,
    cart_categories: list[str],
    excluded_product_ids: set[uuid.UUID],
    top_n: int = 3,
) -> list[dict[str, Any]]:
    """Cheap retrieval: trend_score-ranked items in complementary categories.

    No embedding query here — this endpoint runs on every cart mutation
    so we trade a bit of personalisation for latency. Personal Shopper v2
    remains the place for full semantic recommendations.
    """
    target_category_ids = await _resolve_complement_categories(db, cart_categories)
    if not target_category_ids:
        return []

    stmt = (
        select(Product)
        .where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
            Product.category_id.in_(target_category_ids),
        )
        .order_by(desc(Product.trend_score))
        .limit(top_n * 3)
    )
    rows = await db.execute(stmt)
    products = list(rows.scalars().all())

    # V4 — visual look completion (§6.2): re-rank the complementary candidates
    # by visual similarity to the cart's anchor pieces. The static mapping above
    # stays the candidate source / fallback. Uses the real CLIP vector when the
    # backend is active, the structured one otherwise — and skips silently when
    # no embedding is available (keeps the trend_score order).
    anchor = await _cart_visual_centroid(db, excluded_product_ids)
    look_completion = False
    if anchor is not None and products:
        erows = await db.execute(
            select(ProductEmbedding).where(
                ProductEmbedding.product_id.in_([p.id for p in products])
            )
        )
        cand_emb = {e.product_id: e for e in erows.scalars().all()}
        if cand_emb:
            look_completion = True

            def _visual_sim(p: Product) -> float:
                e = cand_emb.get(p.id)
                return _cosine(anchor, e.visual_embedding) if e else -1.0

            products.sort(
                key=lambda p: (_visual_sim(p), float(p.trend_score or 0)),
                reverse=True,
            )

    # Resolve physical zone names once (mini-fiche « localisation » on the POS).
    zone_ids = {p.zone_id for p in products if p.zone_id}
    zone_names: dict = {}
    if zone_ids:
        zrows = await db.execute(
            select(StoreZone.id, StoreZone.name).where(StoreZone.id.in_(zone_ids))
        )
        zone_names = {zid: zname for zid, zname in zrows.all()}

    out: list[dict[str, Any]] = []
    seen_categories: set[uuid.UUID] = set()
    for product in products:
        if product.id in excluded_product_ids:
            continue
        if product.category_id in seen_categories:
            continue  # one product per category
        seen_categories.add(product.category_id)
        category_name = product.category.name if product.category else None
        reason = (
            f"Complète {cart_categories[0]}"
            if cart_categories
            else "Tendance disponible"
        )
        if category_name:
            reason = (
                f"{category_name.title()} assorti au look"
                if look_completion
                else f"{category_name.title()} pour compléter"
            )
        out.append({
            "product_id": str(product.id),
            "name": product.name,
            "price_cents": int(round(float(product.sale_price) * 100)),
            # Raw upload first — same image the POS search renders reliably.
            # The storefront (Photoroom) copy can 404 on the POS when processing
            # was skipped / not persisted, which broke the suggestion thumbnails.
            "photo_url": product.photo_url or product.storefront_photo_url,
            "score": float(product.trend_score or 0),
            "reason": reason,
            "size": product.size,
            "color": product.color,
            "zone_name": zone_names.get(product.zone_id),
        })
        if len(out) >= top_n:
            break
    return out


async def _cart_visual_centroid(
    db: AsyncSession, product_ids: set[uuid.UUID]
) -> list[float] | None:
    """Mean visual embedding of the pieces already in the cart (the look anchor).

    ``None`` when the cart is empty or none of its pieces have an embedding —
    the caller then keeps the trend-ranked order."""
    if not product_ids:
        return None
    rows = await db.execute(
        select(ProductEmbedding).where(
            ProductEmbedding.product_id.in_(product_ids)
        )
    )
    vecs = [
        e.visual_embedding
        for e in rows.scalars().all()
        if e.visual_embedding is not None and len(e.visual_embedding) > 0
    ]
    if not vecs:  # list of vectors — plain-list truthiness, safe
        return None
    dim = len(vecs[0])
    summed = [0.0] * dim
    for v in vecs:
        for i in range(dim):
            summed[i] += v[i]
    return _l2_normalize(summed)


async def _eligible_coupons(
    db: AsyncSession, *, client_id: uuid.UUID, cart_total_cents: int
) -> list[dict[str, Any]]:
    from app.services.coupon import CouponError, validate_coupon
    from app.models.coupon import CouponSource

    rows = await db.execute(
        select(Coupon)
        .where(
            Coupon.client_id == client_id,
            Coupon.is_active.is_(True),
            Coupon.redeemed_at.is_(None),
            # Les bons cadeau d'ouverture (event_opening) sont affectés comme
            # moyen de paiement (PaymentMethod.voucher) via leur propre rail —
            # ils sont surfacés séparément, pas dans la section remise-coupon.
            Coupon.source != CouponSource.event_opening,
        )
        .order_by(Coupon.valid_until.asc())
    )
    coupons = rows.scalars().all()
    cart_total_eur = cart_total_cents / 100
    out: list[dict[str, Any]] = []
    for coupon in coupons:
        try:
            preview = await validate_coupon(
                db,
                code=coupon.code,
                cart_total=cart_total_eur,
                client_id=client_id,
            )
        except CouponError:
            continue
        out.append({
            "code": preview.code,
            "discount_type": preview.discount_type,
            "discount_value": preview.discount_value,
            "discount_cents": int(round(preview.discount_amount * 100)),
            "new_total_cents": int(round(preview.new_total * 100)),
            "source": preview.source,
            "valid_until": preview.valid_until.isoformat() if preview.valid_until else None,
        })
    return out


async def _build_alerts(
    db: AsyncSession,
    *,
    client: Client,
    points_current: int,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

    # RFM segment hints — fire on the most actionable buckets only.
    segment = (client.rfm_segment or "").lower()
    if segment == "at_risk":
        alerts.append({
            "type": "rfm_at_risk",
            "level": "warning",
            "message": "Cliente at_risk — proposer un coupon de relance pour la rappeler.",
        })
    elif segment == "champion":
        alerts.append({
            "type": "rfm_champion",
            "level": "info",
            "message": "Cliente champion — pensez à mentionner les nouveautés tendance.",
        })
    elif segment == "hibernating":
        alerts.append({
            "type": "rfm_hibernating",
            "level": "warning",
            "message": "Cliente hibernating — premier passage depuis longtemps.",
        })

    # Birthday window — fire if the next anniversary falls within 7 days.
    if client.birth_date is not None:
        today = date.today()
        try:
            this_year = client.birth_date.replace(year=today.year)
        except ValueError:
            this_year = None
        next_birthday: date | None = None
        if this_year is not None:
            next_birthday = this_year if this_year >= today else this_year.replace(year=today.year + 1)
        if next_birthday and (next_birthday - today).days <= BIRTHDAY_WINDOW_DAYS:
            day_count = (next_birthday - today).days
            label = "aujourd'hui" if day_count == 0 else f"dans {day_count} jour(s)"
            alerts.append({
                "type": "birthday_soon",
                "level": "info",
                "message": f"Anniversaire {label} — coupon ANNIV-… probablement actif.",
            })

    # Loyalty milestone progress — encourage the upsell.
    until_next = (100 - (points_current % 100)) if points_current >= 0 else None
    if until_next is not None and 0 < until_next <= 14:
        alerts.append({
            "type": "loyalty_milestone_close",
            "level": "info",
            "message": f"Encore {until_next} pts pour le prochain bon de 8 €.",
        })

    return alerts


async def companion_payload(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    cart_total_cents: int,
    cart_product_ids: list[uuid.UUID],
) -> dict[str, Any]:
    """Aggregate the POS companion payload for a given client + cart.

    Raises :class:`LookupError` if the client doesn't exist.
    """
    row = await db.execute(
        select(Client)
        .options(selectinload(Client.loyalty_account))
        .where(Client.id == client_id)
    )
    client = row.scalar_one_or_none()
    if client is None:
        raise LookupError(f"Client {client_id} not found")

    points_current = int(client.loyalty_account.points or 0) if client.loyalty_account else 0
    would_earn = _points_to_credit(cart_total_cents)
    can_redeem = _redemption_cap_cents(cart_total_cents, points_current) if client.loyalty_account else 0

    # Categories present in the cart — drives the complementary suggestions.
    cart_categories: list[str] = []
    if cart_product_ids:
        rows = await db.execute(
            select(Product)
            .options(selectinload(Product.category))
            .where(Product.id.in_(cart_product_ids))
        )
        for product in rows.scalars().all():
            if product.category and product.category.name:
                cart_categories.append(product.category.name)

    suggestions = await _suggest_complementary(
        db,
        client=client,
        cart_categories=cart_categories,
        excluded_product_ids=set(cart_product_ids),
    )
    coupons = await _eligible_coupons(
        db, client_id=client.id, cart_total_cents=cart_total_cents
    )
    alerts = await _build_alerts(
        db, client=client, points_current=points_current
    )

    return {
        "client": {
            "id": str(client.id),
            "first_name": client.first_name,
            "last_name": client.last_name,
            "rfm_segment": client.rfm_segment,
            "membership_number": client.loyalty_account.membership_number
            if client.loyalty_account else None,
        },
        "loyalty": {
            "active": client.loyalty_account is not None,
            "points_current": points_current,
            "would_earn": would_earn,
            "can_redeem_max_cents": can_redeem,
        },
        "suggestions": suggestions,
        "coupons": coupons,
        "alerts": alerts,
    }
