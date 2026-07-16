"""Vintiz commercial offers engine.

Evaluates the active ``Offer`` rows against a cart and returns the matching
discounts / gifts / coupons that should be applied at checkout.

Schema reminder (cf. ``models/offer.py``):

  end_of_series       config = {"discount_pct": 20, "min_weeks_on_shelf": 6}
  birthday            config = {"discount_pct": 10, "window_days": 5}
  shoes_third_free    config = {"category_filter": ["chaussures"], "min_items": 3}
  progressive_voucher config = {"tiers": [{"cumul": 200, "voucher": 10}, ...],
                                "period_start": ISO, "period_end": ISO}
  bundle_3_for_2      config = {"product_ids": [...] | "category_ids": [...]}
  seasonal_gift       config = {"trigger_category": "Manteau", "min_amount": 30,
                                "gift_categories": ["Gants", "Bonnet"], "n_gifts": 1}

Output of ``evaluate_cart`` is a ``CartEvaluation`` ready for the POS:

  {
    "applied":   [<AppliedOffer>],          # discounts/gifts to add to the cart
    "vouchers":  [<EmittedCoupon>],         # coupons created post-checkout
    "messages":  [str],                     # banners for the cashier UI
  }

The engine never mutates the underlying products. Callers turn the
``AppliedOffer.line_discounts`` into ``TransactionItem.discount_percent``
deltas at sale finalization.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.offer import Offer, OfferType
from app.models.pos import Transaction, TransactionType
from app.models.product import Product


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass
class CartLine:
    """Lightweight cart line view used by the engine.

    ``product`` is optional because manual items (e.g. a sac) can also be in
    the cart. The engine ignores them when a rule needs product attributes.
    """

    product: Product | None
    quantity: int
    unit_price: float
    discount_percent: float = 0.0
    # Optional override the cashier already applied at scan-time. The engine
    # adds on top of it via ``extra_discount_percent``.
    extra_discount_percent: float = 0.0


@dataclass
class AppliedOffer:
    offer_id: uuid.UUID
    offer_type: OfferType
    name: str
    label: str                    # human banner ("Offre fin de série -20 %")
    cart_total_discount: float = 0.0
    line_discounts: dict[int, float] = field(default_factory=dict)  # cart index → % off
    free_slots: list[dict] = field(default_factory=list)            # for seasonal_gift
    voucher_to_emit: dict | None = None                             # progressive_voucher


@dataclass
class CartEvaluation:
    applied: list[AppliedOffer] = field(default_factory=list)
    vouchers: list[dict] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_offer_in_window(offer: Offer, now: datetime) -> bool:
    if offer.valid_from and offer.valid_from > now:
        return False
    if offer.valid_until and offer.valid_until < now:
        return False
    return True


def _weeks_on_shelf(shelf_date: datetime | None, now: datetime) -> int:
    if shelf_date is None:
        return 0
    if shelf_date.tzinfo is None:
        shelf_date = shelf_date.replace(tzinfo=timezone.utc)
    return max(0, (now - shelf_date).days // 7)


async def _list_active_offers(db: AsyncSession, now: datetime) -> list[Offer]:
    rows = (
        await db.execute(
            select(Offer)
            .where(Offer.active.is_(True))
            .order_by(Offer.priority.asc())
        )
    ).scalars().all()
    return [o for o in rows if _is_offer_in_window(o, now)]


async def _client_can_use(offer: Offer, client: Client | None) -> bool:
    if not offer.requires_loyalty:
        return True
    return bool(client and client.loyalty_account is not None)


def _line_total(line: CartLine) -> float:
    discount = (line.discount_percent + line.extra_discount_percent) / 100.0
    return line.unit_price * line.quantity * (1 - discount)


# ---------------------------------------------------------------------------
# Per-type evaluators
# ---------------------------------------------------------------------------


def _eval_end_of_series(
    offer: Offer, lines: list[CartLine], now: datetime
) -> AppliedOffer | None:
    """Combined sale: at least one fresh item + one ≥ N weeks gets discount."""
    cfg = offer.config or {}
    min_weeks = int(cfg.get("min_weeks_on_shelf", 6))
    pct = float(cfg.get("discount_pct", 20))

    fresh_idx: list[int] = []
    aged_idx: list[int] = []
    for idx, line in enumerate(lines):
        if line.product is None:
            continue
        weeks = _weeks_on_shelf(line.product.shelf_date, now)
        if weeks >= min_weeks:
            aged_idx.append(idx)
        else:
            fresh_idx.append(idx)

    if not fresh_idx or not aged_idx:
        return None

    line_discounts: dict[int, float] = {}
    cart_total_disc = 0.0
    for idx in aged_idx:
        line = lines[idx]
        already = line.unit_price * line.quantity * line.discount_percent / 100.0
        new_disc = line.unit_price * line.quantity * pct / 100.0
        line_discounts[idx] = pct
        cart_total_disc += max(0.0, new_disc - already)

    return AppliedOffer(
        offer_id=offer.id,
        offer_type=offer.type,
        name=offer.name,
        label=f"Fin de série −{pct:g}% sur {len(aged_idx)} article(s)",
        cart_total_discount=round(cart_total_disc, 2),
        line_discounts=line_discounts,
    )


def _eval_birthday(
    offer: Offer, client: Client | None, now: datetime
) -> AppliedOffer | None:
    """-pct on whole cart during the client's birthday week (Tue → Sat)."""
    cfg = offer.config or {}
    pct = float(cfg.get("discount_pct", 10))
    if client is None or not getattr(client, "birth_date", None):
        return None

    bd: date = client.birth_date  # type: ignore[assignment]
    today = now.date()
    # Birth day this year (or last year if Feb 29 not present etc.)
    try:
        bd_this_year = bd.replace(year=today.year)
    except ValueError:
        bd_this_year = bd.replace(year=today.year, day=28)
    # Find the Tuesday → Saturday window for the birthday week.
    bd_weekday = bd_this_year.weekday()        # Mon=0
    monday = bd_this_year - timedelta(days=bd_weekday)
    tuesday = monday + timedelta(days=1)
    saturday = monday + timedelta(days=5)
    if not (tuesday <= today <= saturday):
        return None

    return AppliedOffer(
        offer_id=offer.id,
        offer_type=offer.type,
        name=offer.name,
        label=f"Anniversaire −{pct:g}% (semaine de la cliente)",
        cart_total_discount=0.0,  # filled by caller via line_discounts
        line_discounts={i: pct for i in range(len(_birthday_eligible_lines(offer.config)))},
    )


def _birthday_eligible_lines(_cfg: dict | None) -> Iterable[int]:
    """Currently every line is eligible. Hook for future filters."""
    # NB: caller passes the actual line indexes after evaluation.
    return ()


def _apply_birthday_to_lines(applied: AppliedOffer, lines: list[CartLine]) -> None:
    """Fill line_discounts + cart_total_discount once we know the cart."""
    pct = next(iter(applied.line_discounts.values()), 0.0) if applied.line_discounts else 0.0
    if not pct and "−" in applied.label:
        try:
            pct = float(applied.label.split("−")[1].split("%")[0].replace(",", "."))
        except Exception:
            pct = 10.0
    line_discounts: dict[int, float] = {}
    total = 0.0
    for idx, line in enumerate(lines):
        line_discounts[idx] = pct
        total += line.unit_price * line.quantity * pct / 100.0
    applied.line_discounts = line_discounts
    applied.cart_total_discount = round(total, 2)


def _eval_shoes_third_free(
    offer: Offer, lines: list[CartLine]
) -> AppliedOffer | None:
    """Buy 3 pairs of shoes → cheapest is free. Repeats for every triplet."""
    cfg = offer.config or {}
    min_items = int(cfg.get("min_items", 3))
    cat_keywords = [c.lower() for c in cfg.get("category_filter", ["chaussures"])]

    def _is_shoe(line: CartLine) -> bool:
        if not line.product or not line.product.category:
            return False
        cat_name = (line.product.category.name or "").lower()
        return any(k in cat_name for k in cat_keywords)

    shoe_indices = [i for i, line in enumerate(lines) if _is_shoe(line)]
    if len(shoe_indices) < min_items:
        return None

    shoe_indices.sort(key=lambda i: _line_total(lines[i]) / max(1, lines[i].quantity))
    line_discounts: dict[int, float] = {}
    total_disc = 0.0
    n_triplets = len(shoe_indices) // 3
    for k in range(n_triplets):
        idx = shoe_indices[k]  # cheapest of this group
        line = lines[idx]
        line_discounts[idx] = 100.0
        total_disc += line.unit_price * line.quantity

    if not line_discounts:
        return None

    return AppliedOffer(
        offer_id=offer.id,
        offer_type=offer.type,
        name=offer.name,
        label=f"3 paires achetées, la moins chère offerte (×{n_triplets})",
        cart_total_discount=round(total_disc, 2),
        line_discounts=line_discounts,
    )


def _eval_bundle_3_for_2(
    offer: Offer, lines: list[CartLine]
) -> AppliedOffer | None:
    """3 for the price of 2 on a curated selection."""
    cfg = offer.config or {}
    product_ids = {str(pid) for pid in cfg.get("product_ids", [])}
    category_ids = {str(cid) for cid in cfg.get("category_ids", [])}

    def _matches(line: CartLine) -> bool:
        if not line.product:
            return False
        if product_ids and str(line.product.id) in product_ids:
            return True
        if category_ids and str(line.product.category_id) in category_ids:
            return True
        return False

    eligible = [i for i, line in enumerate(lines) if _matches(line)]
    if len(eligible) < 3:
        return None

    eligible.sort(key=lambda i: _line_total(lines[i]) / max(1, lines[i].quantity))
    line_discounts: dict[int, float] = {}
    total_disc = 0.0
    for k in range(len(eligible) // 3):
        idx = eligible[k]
        line = lines[idx]
        line_discounts[idx] = 100.0
        total_disc += line.unit_price * line.quantity

    if not line_discounts:
        return None

    return AppliedOffer(
        offer_id=offer.id,
        offer_type=offer.type,
        name=offer.name,
        label="3 pour le prix de 2",
        cart_total_discount=round(total_disc, 2),
        line_discounts=line_discounts,
    )


def _eval_seasonal_gift(
    offer: Offer, lines: list[CartLine]
) -> AppliedOffer | None:
    """Buy a category > min_amount → free item from gift_categories."""
    cfg = offer.config or {}
    trigger = (cfg.get("trigger_category") or "").lower()
    min_amount = float(cfg.get("min_amount", 0))
    gift_cats = [c.lower() for c in cfg.get("gift_categories", [])]
    n_gifts = int(cfg.get("n_gifts", 1))

    qualifying_total = 0.0
    for line in lines:
        if not line.product or not line.product.category:
            continue
        if trigger and trigger in (line.product.category.name or "").lower():
            qualifying_total += _line_total(line)

    if qualifying_total < min_amount:
        return None

    return AppliedOffer(
        offer_id=offer.id,
        offer_type=offer.type,
        name=offer.name,
        label=f"Offert : {' ou '.join(gift_cats) or 'cadeau'} (×{n_gifts})",
        free_slots=[{"categories": gift_cats, "n": n_gifts}],
    )


async def _eval_progressive_voucher(
    db: AsyncSession,
    offer: Offer,
    client: Client | None,
    cart_total: float,
    now: datetime,
) -> AppliedOffer | None:
    """Cumulative spend on the period (incl. current cart) crosses a tier."""
    cfg = offer.config or {}
    if client is None:
        return None
    tiers = sorted(cfg.get("tiers", []), key=lambda t: t.get("cumul", 0))
    if not tiers:
        return None

    period_start = _parse_iso(cfg.get("period_start"))
    period_end = _parse_iso(cfg.get("period_end")) or now
    if period_start is None:
        return None

    q = select(Transaction.total_ttc).where(
        Transaction.client_id == client.id,
        Transaction.transaction_type == TransactionType.sale,
        Transaction.created_at >= period_start,
        Transaction.created_at <= period_end,
    )
    rows = (await db.execute(q)).scalars().all()
    cumul_so_far = float(sum(rows))
    new_cumul = cumul_so_far + float(cart_total)

    crossed = [t for t in tiers if cumul_so_far < t["cumul"] <= new_cumul]
    if not crossed:
        return None
    top = crossed[-1]

    voucher = {
        "voucher_value": float(top["voucher"]),
        "tier_cumul": float(top["cumul"]),
        "valid_days": int(cfg.get("voucher_valid_days", 60)),
        "client_id": str(client.id),
        "source_offer_id": str(offer.id),
    }
    return AppliedOffer(
        offer_id=offer.id,
        offer_type=offer.type,
        name=offer.name,
        label=f"Bon de {voucher['voucher_value']:g} € débloqué (cumul {top['cumul']} €)",
        voucher_to_emit=voucher,
    )


def _parse_iso(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def evaluate_cart(
    db: AsyncSession,
    *,
    lines: list[CartLine],
    client: Client | None,
    cart_total_ttc: float,
    now: datetime | None = None,
) -> CartEvaluation:
    """Evaluate every active offer against the cart.

    The cart is left untouched — the caller decides whether to apply each
    discount. Returns a ``CartEvaluation`` with banner messages, line
    discounts, and pending vouchers.
    """
    now = now or datetime.now(timezone.utc)
    out = CartEvaluation()

    offers = await _list_active_offers(db, now)
    for offer in offers:
        if not await _client_can_use(offer, client):
            continue

        applied: AppliedOffer | None = None
        if offer.type == OfferType.end_of_series:
            applied = _eval_end_of_series(offer, lines, now)
        elif offer.type == OfferType.birthday:
            applied = _eval_birthday(offer, client, now)
            if applied:
                _apply_birthday_to_lines(applied, lines)
        elif offer.type == OfferType.shoes_third_free:
            applied = _eval_shoes_third_free(offer, lines)
        elif offer.type == OfferType.bundle_3_for_2:
            applied = _eval_bundle_3_for_2(offer, lines)
        elif offer.type == OfferType.seasonal_gift:
            applied = _eval_seasonal_gift(offer, lines)
        elif offer.type == OfferType.progressive_voucher:
            applied = await _eval_progressive_voucher(
                db, offer, client, cart_total_ttc, now
            )

        if applied is None:
            continue

        out.applied.append(applied)
        out.messages.append(applied.label)
        if applied.voucher_to_emit:
            out.vouchers.append(applied.voucher_to_emit)

    return out


# ---------------------------------------------------------------------------
# Loyalty milestone (1 € = 1 pt, 100 pts = 5 €)
# ---------------------------------------------------------------------------


LOYALTY_POINT_PER_EURO = 1
LOYALTY_MILESTONE = 100
LOYALTY_VOUCHER_VALUE = 5.0
LOYALTY_VOUCHER_VALID_DAYS = 180  # chèque cadeau fidélité valable 6 mois


def points_to_credit(amount_ttc: float, euro_per_point: int = LOYALTY_POINT_PER_EURO) -> int:
    """Return the number of loyalty points earned for a given net amount.

    ``euro_per_point`` = euros spent to earn 1 point (admin-configurable, #1).
    """
    epp = max(1, int(euro_per_point or 1))
    return max(0, int(float(amount_ttc) // epp))


def milestones_crossed(
    before: int, after: int, threshold: int = LOYALTY_MILESTONE
) -> int:
    """Number of voucher milestones crossed from ``before`` to ``after``.

    ``threshold`` = points per voucher (admin-configurable, #1).
    """
    if after <= before:
        return 0
    t = max(1, int(threshold or LOYALTY_MILESTONE))
    return (max(0, after) // t) - (max(0, before) // t)
