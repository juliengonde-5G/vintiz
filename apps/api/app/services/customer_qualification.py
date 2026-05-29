"""Customer qualification — computed taste signals (Personal Shopper 360 V2).

From a member's last 15 *sale* transactions (gifts excluded), derive structured
signals that **enrich** the recommender and the appro brief without touching the
embedding engine (audit §9.4):

- ``season_bias`` (winter / summer / all) — there is no ``saison`` column on
  ``Product``, so we infer it with a keyword heuristic over the bought pieces'
  category + name.
- ``price_ceiling_cents`` + ``price_sensitivity`` — quantiles + dispersion of
  the prices actually paid.
- ``trend_affinity`` [0-1] — mean ``trend_score`` of the bought pieces,
  normalised.

Gifts (``Transaction.exclude_from_taste``) are filtered out of the window so an
atypical purchase doesn't skew the profile (§4.3). The service only *writes*
nullable columns on ``Client`` — additive and reversible.
"""

from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, Consent, ConsentPurpose
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Product

QUALIFICATION_VERSION = "qualif-v1-2026-05"

# Season inference keywords (FR), matched against "category name + product name".
_WINTER_KEYWORDS = {
    "manteau", "doudoune", "parka", "pull", "laine", "cachemire", "écharpe",
    "echarpe", "gants", "bonnet", "polaire", "velours", "bottes", "bottines",
    "col roulé", "col roule", "moufle", "anorak",
}
_SUMMER_KEYWORDS = {
    "short", "maillot", "bikini", "sandale", "tong", "lin", "débardeur",
    "debardeur", "bermuda", "paille", "crop", "bain", "espadrille",
}


def classify_season(text: str | None) -> str | None:
    """Return ``"winter"`` / ``"summer"`` / ``None`` (all-season) for a label."""
    t = (text or "").lower()
    if any(k in t for k in _WINTER_KEYWORDS):
        return "winter"
    if any(k in t for k in _SUMMER_KEYWORDS):
        return "summer"
    return None


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


async def compute_qualification(
    db: AsyncSession, customer_id: uuid.UUID, *, max_transactions: int = 15
) -> dict | None:
    """Compute + persist the qualification signals for ``customer_id``.

    Returns the computed dict, or ``None`` when there's no analysable history
    or the member hasn't granted profiling consent (the columns are left
    untouched in that case — RGPD §9.6: signals are only computed with consent).
    """
    consent = (
        await db.execute(
            select(Consent)
            .where(
                Consent.client_id == customer_id,
                Consent.purpose == ConsentPurpose.profiling,
            )
            .order_by(desc(Consent.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    if consent is None or not consent.granted:
        return None

    recent_tx = (
        select(Transaction.id)
        .where(
            Transaction.client_id == customer_id,
            Transaction.transaction_type == TransactionType.sale,
            Transaction.exclude_from_taste.is_(False),
        )
        .order_by(desc(Transaction.created_at))
        .limit(max_transactions)
        .subquery()
    )
    rows = (
        await db.execute(
            select(Product, TransactionItem.unit_price)
            .join(TransactionItem, TransactionItem.product_id == Product.id)
            .join(recent_tx, TransactionItem.transaction_id == recent_tx.c.id)
        )
    ).all()
    if not rows:
        return None

    # --- season_bias --------------------------------------------------------
    winter = summer = 0
    for product, _price in rows:
        cat_name = product.category.name if product.category else ""
        season = classify_season(f"{cat_name} {product.name}")
        if season == "winter":
            winter += 1
        elif season == "summer":
            summer += 1
    classified = winter + summer
    if classified and winter >= max(1, int(0.6 * classified)):
        season_bias = "winter"
    elif classified and summer >= max(1, int(0.6 * classified)):
        season_bias = "summer"
    else:
        season_bias = "all"

    # --- price_ceiling_cents + price_sensitivity ----------------------------
    prices = sorted(float(p) for _prod, p in rows if p is not None)
    price_ceiling_cents: int | None = None
    price_sensitivity: float | None = None
    if prices:
        p90 = _quantile(prices, 0.9)
        price_ceiling_cents = int(round(p90 * 100))
        mean = sum(prices) / len(prices)
        if mean > 0 and len(prices) >= 2:
            var = sum((x - mean) ** 2 for x in prices) / len(prices)
            cv = (var ** 0.5) / mean  # coefficient of variation
            price_sensitivity = round(_clamp01(cv), 4)
        else:
            price_sensitivity = 0.0

    # --- trend_affinity -----------------------------------------------------
    trend_scores = [
        float(prod.trend_score) for prod, _p in rows if prod.trend_score is not None
    ]
    trend_affinity: float | None = None
    if trend_scores:
        trend_affinity = round(_clamp01(sum(trend_scores) / len(trend_scores) / 100.0), 4)

    customer = (
        await db.execute(select(Client).where(Client.id == customer_id))
    ).scalar_one_or_none()
    if customer is None:
        return None
    customer.season_bias = season_bias
    customer.price_ceiling_cents = price_ceiling_cents
    customer.price_sensitivity = price_sensitivity
    customer.trend_affinity = trend_affinity
    await db.flush()

    return {
        "season_bias": season_bias,
        "price_ceiling_cents": price_ceiling_cents,
        "price_sensitivity": price_sensitivity,
        "trend_affinity": trend_affinity,
        "n_transactions_analyzed": len({r[0].id for r in rows}) if rows else 0,
        "version": QUALIFICATION_VERSION,
    }


async def recompute_all_qualifications(db: AsyncSession) -> dict:
    """Batch pass over every customer with a purchase history (nightly cron)."""
    customer_ids = (
        await db.execute(
            select(Transaction.client_id)
            .where(
                Transaction.client_id.is_not(None),
                Transaction.transaction_type == TransactionType.sale,
            )
            .distinct()
        )
    ).scalars().all()
    computed = 0
    for cid in customer_ids:
        result = await compute_qualification(db, cid)
        if result is not None:
            computed += 1
    return {"scanned": len(customer_ids), "computed": computed}


async def score_atypie(
    db: AsyncSession, customer_id: uuid.UUID, product: Product
) -> dict:
    """Heuristic "is this purchase atypical (maybe a gift)?" score (§4.3).

    Looks at the customer's past purchases vs the product's gender / category /
    size. Returns ``{"atypie": 0..1, "ask": bool, "reasons": [...]}``. Used by
    the POS to decide whether to surface the « Cet achat est-il pour vous ? »
    micro-question. Never blocks — purely advisory.
    """
    from app.models.product import Gender

    rows = (
        await db.execute(
            select(Product.gender, Product.category_id, Product.size)
            .join(TransactionItem, TransactionItem.product_id == Product.id)
            .join(Transaction, Transaction.id == TransactionItem.transaction_id)
            .where(
                Transaction.client_id == customer_id,
                Transaction.transaction_type == TransactionType.sale,
                Transaction.exclude_from_taste.is_(False),
            )
        )
    ).all()

    customer = (
        await db.execute(select(Client).where(Client.id == customer_id))
    ).scalar_one_or_none()

    atypie = 0.0
    reasons: list[str] = []

    # Gender mismatch vs the declared profile (strongest signal).
    declared = (customer.gender_profile if customer else None) or None
    if (
        declared in ("femme", "homme")
        and product.gender in (Gender.femme, Gender.homme)
        and product.gender.value != declared
    ):
        atypie += 0.5
        reasons.append("genre opposé au profil")

    if rows:
        past_categories = {r[1] for r in rows}
        past_sizes = {(r[2] or "").lower() for r in rows if r[2]}
        if product.category_id not in past_categories:
            atypie += 0.3
            reasons.append("catégorie jamais achetée")
        if product.size and product.size.lower() not in past_sizes and past_sizes:
            atypie += 0.2
            reasons.append("taille inhabituelle")

    atypie = _clamp01(atypie)
    return {"atypie": round(atypie, 2), "ask": atypie >= 0.5, "reasons": reasons}
