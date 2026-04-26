"""Customer brief — enriched lookup for POS upsell (L2.3).

Delivers Sophie (cashier) an actionable 2-second context when a loyalty
card is scanned : last visit, favorite categories / brands / colors, size
profile, and 3 Personal Shopper picks ready to be tapped into the cart.

Driven by the persona §5 in ``docs/AUDIT_2026_05_BOUTIQUE.md`` :
   "Sophie n'a pas de contexte de vente additionnelle"

Function ``get_customer_brief`` aggregates :
- Client identity + loyalty + avoir
- Last visit date + days since
- Lifetime value + favorite categories (top 3) + brands (top 2) + colors (top 2)
- Size profile (deduced from purchases)
- 3 Personal Shopper picks (best-effort, falls back to top-scored displayed)
- Active reservation (P4-005)
- Anniversary coupon (P4-008)
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client import Client, LoyaltyTxType
from app.models.coupon import Coupon
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Product, ProductStatus


logger = logging.getLogger(__name__)


async def get_customer_brief(
    db: AsyncSession, client_id: uuid.UUID
) -> dict[str, Any] | None:
    """Aggregate everything needed by ``LoyaltyCustomerCard`` UI.

    Returns ``None`` if the client doesn't exist.
    """
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.loyalty_account))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        return None

    loyalty = client.loyalty_account
    loyalty_block = None
    if loyalty:
        loyalty_block = {
            "points": loyalty.points,
            "tier": loyalty.tier,
        }

    # --- Transactions in the last 12 months (sale only — refunds excluded) ---
    tx_q = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.items).selectinload(TransactionItem.product).selectinload(Product.category))
        .where(
            Transaction.client_id == client_id,
            Transaction.transaction_type == TransactionType.sale,
        )
        .order_by(desc(Transaction.created_at))
        .limit(50)
    )
    transactions = tx_q.scalars().all()

    last_visit = transactions[0].created_at if transactions else None
    days_since = None
    if last_visit:
        days_since = (datetime.now(timezone.utc) - last_visit.replace(tzinfo=timezone.utc)).days

    # --- Aggregates ---
    lifetime_value = sum(float(t.total_ttc or 0) for t in transactions)
    cat_counter: Counter[str] = Counter()
    brand_counter: Counter[str] = Counter()
    color_counter: Counter[str] = Counter()
    size_haut: Counter[str] = Counter()
    size_bas: Counter[str] = Counter()

    last_purchases = []
    for t in transactions[:3]:
        for it in (t.items or [])[:1]:  # 1 item per transaction in summary
            prod = it.product
            if prod:
                last_purchases.append({
                    "date": t.created_at.isoformat() if t.created_at else None,
                    "name": prod.name,
                    "price": float(it.unit_price_ttc or 0),
                })

    for t in transactions:
        for it in t.items or []:
            prod = it.product
            if not prod:
                continue
            if prod.category and prod.category.name:
                cat_counter[prod.category.name] += 1
            if prod.brand:
                brand_counter[prod.brand] += 1
            if prod.color:
                color_counter[prod.color.lower()] += 1
            if prod.size:
                # Heuristic split : numeric size → bas (pants/skirts), letter → haut.
                if prod.size.strip().isdigit():
                    size_bas[prod.size] += 1
                else:
                    size_haut[prod.size] += 1

    favorite_categories = [
        {"name": n, "count": c, "share": round(c / max(1, sum(cat_counter.values())), 2)}
        for n, c in cat_counter.most_common(3)
    ]
    favorite_brands = [b for b, _ in brand_counter.most_common(2)]
    favorite_colors = [c for c, _ in color_counter.most_common(2)]

    size_profile: dict[str, str] = {}
    if size_haut:
        size_profile["haut"] = size_haut.most_common(1)[0][0]
    if size_bas:
        size_profile["bas"] = size_bas.most_common(1)[0][0]

    # --- Personal Shopper picks (best-effort) ---
    ps_picks: list[dict] = []
    try:
        from app.services.personal_shopper import PersonalShopperService

        ps_result = await PersonalShopperService(db).recommend(
            client_id=client_id, limit=3
        )
        # The service may return narrative + recommendations; fish out the recs.
        recs = ps_result.get("recommendations") or ps_result.get("products") or []
        for rec in recs[:3]:
            ps_picks.append({
                "id": rec.get("id") or rec.get("product_id"),
                "name": rec.get("name", ""),
                "thumb": rec.get("photo_url") or rec.get("thumb"),
                "score": rec.get("trend_score") or rec.get("score"),
            })
    except Exception as exc:  # noqa: BLE001
        logger.debug("PS picks unavailable: %s", exc)

    # Fallback : if PS returned nothing, surface 3 top-scored displayed products.
    if not ps_picks:
        fallback_q = await db.execute(
            select(Product)
            .where(
                Product.status.in_([ProductStatus.displayed, ProductStatus.stock]),
                Product.is_test.is_(False),
            )
            .order_by(desc(Product.trend_score))
            .limit(3)
        )
        for prod in fallback_q.scalars().all():
            ps_picks.append({
                "id": str(prod.id),
                "name": prod.name,
                "thumb": prod.photo_url,
                "score": prod.trend_score,
            })

    # --- Active reservation (P4-005) ---
    active_reservation = None
    try:
        from app.models.reservation import Reservation, ReservationStatus

        res_q = await db.execute(
            select(Reservation).where(
                Reservation.client_id == client_id,
                Reservation.status == ReservationStatus.active,
            ).limit(1)
        )
        res = res_q.scalar_one_or_none()
        if res:
            active_reservation = {
                "id": str(res.id),
                "product_id": str(res.product_id) if res.product_id else None,
                "expires_at": res.expires_at.isoformat() if res.expires_at else None,
            }
    except Exception:
        pass

    # --- Anniversary coupon (P4-008) ---
    anniversary_coupon = None
    try:
        cp_q = await db.execute(
            select(Coupon).where(
                Coupon.client_id == client_id,
                Coupon.is_active.is_(True),
                Coupon.redeemed_at.is_(None),
            ).order_by(Coupon.created_at.desc()).limit(1)
        )
        cp = cp_q.scalar_one_or_none()
        if cp:
            anniversary_coupon = {
                "code": cp.code,
                "discount_value": float(cp.discount_value or 0),
                "valid_until": cp.valid_until.isoformat() if cp.valid_until else None,
            }
    except Exception:
        pass

    return {
        "id": str(client.id),
        "first_name": client.first_name,
        "last_name": client.last_name,
        "email": client.email,
        "phone": client.phone,
        "loyalty": loyalty_block,
        "loyalty_points": loyalty.points if loyalty else 0,
        "tier": loyalty.tier if loyalty else "Bronze",
        "avoir_credit": float(client.avoir_credit or 0),
        "last_visit": last_visit.isoformat() if last_visit else None,
        "days_since_last_visit": days_since,
        "lifetime_value": round(lifetime_value, 2),
        "favorite_categories": favorite_categories,
        "favorite_brands": favorite_brands,
        "favorite_colors": favorite_colors,
        "size_profile": size_profile,
        "last_purchases": last_purchases,
        "personal_shopper_picks_today": ps_picks,
        "active_reservation": active_reservation,
        "anniversary_coupon": anniversary_coupon,
        "consents": {
            "marketing_email": bool(client.email_optin),
            "sms": bool(client.sms_optin),
        },
        "rfm_segment": client.rfm_segment,
    }
