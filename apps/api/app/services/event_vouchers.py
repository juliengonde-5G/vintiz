"""Bons cadeau d'ouverture — catalogue, émission, listing (zone Événementiel).

Pour l'ouverture de la boutique, on distribue des bons cadeau (format papier,
cf. ``docs``/pièce jointe) applicables sur un prochain achat. En caisse, la
zone « Événementiel » propose un bouton par type de bon ; sur clic, le bon est
**crédité sur la fiche client** (beaucoup de créations de fiches à l'ouverture).
Au passage suivant, la caisse le **débite comme moyen de paiement**
(``PaymentMethod.voucher``).

On réutilise la table ``coupons`` (nominative, validité, usage unique) avec la
source ``event_opening``. Le catalogue des 6 types (1 €, 2 €, -5/-10/-15 %,
1 foulard offert) est éditable par le manager (Settings-backed), avec des
valeurs par défaut reprises du visuel d'ouverture.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Settings
from app.models.client import Client
from app.models.coupon import Coupon, CouponDiscountType, CouponSource
from app.services.coupon import CouponError, _draw_unique_code

_SETTINGS_KEY = "event_voucher_catalog"

# Fin de campagne par défaut (visuel d'ouverture : 04/06 → 30/08/2026).
DEFAULT_CAMPAIGN_END = "2026-08-30"
# Plafond par défaut du bon « 1 foulard offert » (€) — éditable.
DEFAULT_SCARF_CAP = 15.0

# Les 6 types du visuel d'ouverture. ``discount_value`` : montant € (amount),
# pourcentage (percent) ou plafond € de l'article offert (free_item).
DEFAULT_VOUCHER_CATALOG: list[dict] = [
    {"key": "bon_2e", "label": "2 € offert", "discount_type": "amount",
     "discount_value": 2.0, "free_item_label": None},
    {"key": "bon_1e", "label": "1 € offert", "discount_type": "amount",
     "discount_value": 1.0, "free_item_label": None},
    {"key": "remise_5", "label": "-5 %", "discount_type": "percent",
     "discount_value": 5.0, "free_item_label": None},
    {"key": "remise_10", "label": "-10 %", "discount_type": "percent",
     "discount_value": 10.0, "free_item_label": None},
    {"key": "remise_15", "label": "-15 %", "discount_type": "percent",
     "discount_value": 15.0, "free_item_label": None},
    {"key": "foulard", "label": "1 foulard offert", "discount_type": "free_item",
     "discount_value": DEFAULT_SCARF_CAP, "free_item_label": "foulard"},
]


def _with_defaults(entry: dict) -> dict:
    return {
        "key": entry["key"],
        "label": entry.get("label", entry["key"]),
        "discount_type": entry.get("discount_type", "amount"),
        "discount_value": float(entry.get("discount_value", 0) or 0),
        "free_item_label": entry.get("free_item_label"),
        "valid_until": entry.get("valid_until", DEFAULT_CAMPAIGN_END),
        "active": bool(entry.get("active", True)),
    }


async def get_catalog(db: AsyncSession) -> list[dict]:
    """Return the voucher catalog (defaults merged with manager overrides)."""
    row = (await db.execute(
        select(Settings).where(Settings.key == _SETTINGS_KEY)
    )).scalar_one_or_none()
    if row is None or not row.value:
        return [_with_defaults(e) for e in DEFAULT_VOUCHER_CATALOG]
    try:
        stored = {e["key"]: e for e in json.loads(row.value)}
    except (json.JSONDecodeError, TypeError, KeyError):
        return [_with_defaults(e) for e in DEFAULT_VOUCHER_CATALOG]
    # Defaults are the source of the canonical key set; stored entries override.
    merged: list[dict] = []
    for default in DEFAULT_VOUCHER_CATALOG:
        merged.append(_with_defaults({**default, **stored.get(default["key"], {})}))
    # Allow manager-added custom voucher types beyond the 6 defaults.
    default_keys = {e["key"] for e in DEFAULT_VOUCHER_CATALOG}
    for key, entry in stored.items():
        if key not in default_keys:
            merged.append(_with_defaults(entry))
    return merged


async def update_catalog(db: AsyncSession, catalog: list[dict]) -> list[dict]:
    """Persist the (manager-edited) catalog. Returns the normalised catalog."""
    normalised = [_with_defaults(e) for e in catalog if e.get("key")]
    payload = json.dumps(normalised, ensure_ascii=False)
    row = (await db.execute(
        select(Settings).where(Settings.key == _SETTINGS_KEY)
    )).scalar_one_or_none()
    if row is None:
        db.add(Settings(
            key=_SETTINGS_KEY,
            value=payload,
            description="Catalogue des bons cadeau d'ouverture (zone Événementiel POS)",
        ))
    else:
        row.value = payload
    await db.flush()
    return normalised


def _parse_valid_until(value: str | None, *, now: datetime) -> datetime:
    """ISO date → end-of-day UTC. Falls back to the campaign end then +88j."""
    for candidate in (value, DEFAULT_CAMPAIGN_END):
        if not candidate:
            continue
        try:
            d = datetime.fromisoformat(str(candidate)).date()
            return datetime.combine(d, time(23, 59, 59), tzinfo=timezone.utc)
        except ValueError:
            continue
    from datetime import timedelta

    return now + timedelta(days=88)


async def issue_voucher(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    type_key: str,
    user_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> Coupon:
    """Credit one gift voucher of ``type_key`` onto a client's account.

    Raises ``CouponError`` (``client_not_found`` / ``unknown_type`` /
    ``inactive_type``) on bad input."""
    now = now or datetime.now(timezone.utc)

    client = (await db.execute(
        select(Client).where(Client.id == client_id)
    )).scalar_one_or_none()
    if client is None:
        raise CouponError("client_not_found")

    catalog = {e["key"]: e for e in await get_catalog(db)}
    vtype = catalog.get(type_key)
    if vtype is None:
        raise CouponError("unknown_type")
    if not vtype.get("active", True):
        raise CouponError("inactive_type")

    code = await _draw_unique_code(db, "BON")
    coupon = Coupon(
        code=code,
        client_id=client_id,
        discount_type=CouponDiscountType(vtype["discount_type"]),
        discount_value=float(vtype["discount_value"]),
        source=CouponSource.event_opening,
        valid_from=now,
        valid_until=_parse_valid_until(vtype.get("valid_until"), now=now),
        is_active=True,
        free_item_label=vtype.get("free_item_label"),
        notes=f"Bon cadeau ouverture — {vtype['label']}",
    )
    db.add(coupon)
    await db.flush()
    return coupon


async def list_client_vouchers(
    db: AsyncSession,
    client_id: uuid.UUID,
    *,
    only_active: bool = True,
    now: datetime | None = None,
) -> list[Coupon]:
    """Event-opening vouchers held by a client. ``only_active`` keeps the
    redeemable ones (active, unredeemed, within validity)."""
    now = now or datetime.now(timezone.utc)
    rows = (await db.execute(
        select(Coupon)
        .where(
            Coupon.client_id == client_id,
            Coupon.source == CouponSource.event_opening,
        )
        .order_by(Coupon.created_at.desc())
    )).scalars().all()
    if not only_active:
        return list(rows)

    out: list[Coupon] = []
    for c in rows:
        if not c.is_active or c.redeemed_at is not None:
            continue
        vu = c.valid_until.replace(tzinfo=timezone.utc) if c.valid_until.tzinfo is None else c.valid_until
        vf = c.valid_from.replace(tzinfo=timezone.utc) if c.valid_from.tzinfo is None else c.valid_from
        if vf <= now <= vu:
            out.append(c)
    return out
