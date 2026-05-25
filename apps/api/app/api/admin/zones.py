"""Zone CRUD, layout update, zone analytics, zone products, furniture items, and zone tags."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker, get_current_user
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Product, ProductStatus
from app.models.store import StoreZone
from app.models.user import User

router = APIRouter(tags=["admin"])

manager_only = RoleChecker(["manager"])

# ---------------------------------------------------------------------------
# Zone schema models
# ---------------------------------------------------------------------------


class ZoneCreate(BaseModel):
    name: str
    description: str | None = None
    capacity: int = 0
    product_types: List[str] | None = None
    color_code: str | None = "#1A7A6A"
    pos_x: int | None = None
    pos_y: int | None = None
    width: int | None = None
    height: int | None = None
    shape: str | None = None
    icon: str | None = None
    photo_url: str | None = None
    sales_target_monthly: float | None = None
    display_order: int | None = None
    match_genders: List[str] | None = None
    match_colors: List[str] | None = None
    match_size_classes: List[str] | None = None
    min_trend_score: float | None = None
    assignment_priority: int | None = None
    auto_assign: bool | None = None


class ZoneUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    capacity: int | None = None
    product_types: List[str] | None = None
    color_code: str | None = None
    pos_x: int | None = None
    pos_y: int | None = None
    width: int | None = None
    height: int | None = None
    shape: str | None = None
    icon: str | None = None
    photo_url: str | None = None
    sales_target_monthly: float | None = None
    display_order: int | None = None
    match_genders: List[str] | None = None
    match_colors: List[str] | None = None
    match_size_classes: List[str] | None = None
    min_trend_score: float | None = None
    assignment_priority: int | None = None
    auto_assign: bool | None = None


class ZoneLayoutItem(BaseModel):
    id: uuid.UUID
    pos_x: int
    pos_y: int
    width: int
    height: int


class ZoneLayoutPayload(BaseModel):
    items: List[ZoneLayoutItem]


def _serialize_zone(zone: StoreZone, product_count: int | None = None) -> dict:
    parsed_types = None
    if zone.product_types:
        try:
            parsed_types = json.loads(zone.product_types)
        except Exception:
            parsed_types = [zone.product_types]
    out = {
        "id": str(zone.id),
        "name": zone.name,
        "description": zone.description,
        "capacity": zone.capacity,
        "product_types": parsed_types,
        "color_code": zone.color_code,
        "pos_x": zone.pos_x,
        "pos_y": zone.pos_y,
        "width": zone.width,
        "height": zone.height,
        "shape": zone.shape,
        "icon": zone.icon,
        "photo_url": zone.photo_url,
        "sales_target_monthly": float(zone.sales_target_monthly) if zone.sales_target_monthly is not None else None,
        "display_order": zone.display_order,
        "match_genders": zone.match_genders,
        "match_colors": zone.match_colors,
        "match_size_classes": zone.match_size_classes,
        "min_trend_score": float(zone.min_trend_score) if zone.min_trend_score is not None else None,
        "assignment_priority": zone.assignment_priority,
        "auto_assign": zone.auto_assign,
    }
    if product_count is not None:
        out["product_count"] = product_count
    return out


# ---------------------------------------------------------------------------
# Zone CRUD
# ---------------------------------------------------------------------------


@router.get("/zones")
async def list_zones(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List all zones with product count and full layout metadata."""
    result = await db.execute(
        select(StoreZone).order_by(StoreZone.display_order, StoreZone.name)
    )
    zones = result.scalars().all()

    output = []
    for zone in zones:
        count_result = await db.execute(
            select(func.count(Product.id)).where(Product.zone_id == zone.id)
        )
        product_count = count_result.scalar_one() or 0
        output.append(_serialize_zone(zone, product_count=product_count))
    return output


@router.get("/zones/{zone_id}")
async def get_zone(
    zone_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get a single zone by id with current product count.

    Used by the detail page to avoid re-downloading the full list and
    array-finding client-side (which could silently miss a zone on a stale
    cache hit).
    """
    result = await db.execute(select(StoreZone).where(StoreZone.id == zone_id))
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    count_result = await db.execute(
        select(func.count(Product.id)).where(Product.zone_id == zone.id)
    )
    product_count = count_result.scalar_one() or 0
    return _serialize_zone(zone, product_count=product_count)


@router.post("/zones", status_code=status.HTTP_201_CREATED)
async def create_zone(
    zone_in: ZoneCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new store zone."""
    product_types_json = json.dumps(zone_in.product_types) if zone_in.product_types is not None else None
    zone = StoreZone(
        name=zone_in.name,
        description=zone_in.description,
        capacity=zone_in.capacity,
        product_types=product_types_json,
        color_code=zone_in.color_code or "#1A7A6A",
        pos_x=zone_in.pos_x if zone_in.pos_x is not None else 10,
        pos_y=zone_in.pos_y if zone_in.pos_y is not None else 10,
        width=zone_in.width if zone_in.width is not None else 20,
        height=zone_in.height if zone_in.height is not None else 20,
        shape=zone_in.shape or "rounded",
        icon=zone_in.icon,
        photo_url=zone_in.photo_url,
        sales_target_monthly=zone_in.sales_target_monthly,
        display_order=zone_in.display_order if zone_in.display_order is not None else 0,
        match_genders=zone_in.match_genders,
        match_colors=zone_in.match_colors,
        match_size_classes=zone_in.match_size_classes,
        min_trend_score=zone_in.min_trend_score,
        assignment_priority=zone_in.assignment_priority if zone_in.assignment_priority is not None else 100,
        auto_assign=zone_in.auto_assign if zone_in.auto_assign is not None else True,
    )
    db.add(zone)
    await db.flush()
    await db.refresh(zone)
    await db.commit()
    return _serialize_zone(zone, product_count=0)


@router.put("/zones/{zone_id}")
async def update_zone(
    zone_id: uuid.UUID,
    zone_in: ZoneUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update an existing store zone."""
    result = await db.execute(select(StoreZone).where(StoreZone.id == zone_id))
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    data = zone_in.model_dump(exclude_unset=True)
    for field in ("name", "description", "capacity", "color_code", "pos_x", "pos_y",
                  "width", "height", "shape", "icon", "photo_url",
                  "sales_target_monthly", "display_order",
                  "match_genders", "match_colors", "match_size_classes",
                  "min_trend_score", "assignment_priority", "auto_assign"):
        if field in data:
            setattr(zone, field, data[field])
    if "product_types" in data and data["product_types"] is not None:
        zone.product_types = json.dumps(data["product_types"])

    await db.flush()
    await db.refresh(zone)
    await db.commit()
    return _serialize_zone(zone)


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Delete a store zone. Unassigns all products in that zone first."""
    result = await db.execute(select(StoreZone).where(StoreZone.id == zone_id))
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    products_result = await db.execute(
        select(Product).where(Product.zone_id == zone_id)
    )
    for product in products_result.scalars().all():
        product.zone_id = None
    await db.flush()

    await db.delete(zone)
    await db.flush()
    await db.commit()


@router.post("/zones/layout")
async def update_zones_layout(
    payload: ZoneLayoutPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Batch update zone positions/sizes after drag & drop on the 2D plan."""
    updated = 0
    for item in payload.items:
        result = await db.execute(select(StoreZone).where(StoreZone.id == item.id))
        zone = result.scalar_one_or_none()
        if zone is None:
            continue
        zone.pos_x = max(0, min(100, item.pos_x))
        zone.pos_y = max(0, min(100, item.pos_y))
        zone.width = max(4, min(100, item.width))
        zone.height = max(4, min(100, item.height))
        updated += 1
    await db.commit()
    return {"updated": updated}


@router.get("/zones/{zone_id}/analytics")
async def zone_analytics(
    zone_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return 30-day analytics for a zone: CA, rotation, top products, alerts."""
    result = await db.execute(select(StoreZone).where(StoreZone.id == zone_id))
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    now = datetime.now(timezone.utc)
    start_30 = now - timedelta(days=30)
    start_60 = now - timedelta(days=60)

    active_res = await db.execute(
        select(func.count(Product.id)).where(
            Product.zone_id == zone_id,
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
        )
    )
    active_count = active_res.scalar_one() or 0

    sold_30 = await db.execute(
        select(
            func.count(TransactionItem.id),
            func.coalesce(func.sum(TransactionItem.unit_price), 0),
        )
        .join(Product, Product.id == TransactionItem.product_id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Product.zone_id == zone_id,
            Transaction.created_at >= start_30,
            Transaction.transaction_type == TransactionType.sale,
        )
    )
    sold_count, sold_revenue = sold_30.one()

    sold_prev = await db.execute(
        select(
            func.count(TransactionItem.id),
            func.coalesce(func.sum(TransactionItem.unit_price), 0),
        )
        .join(Product, Product.id == TransactionItem.product_id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Product.zone_id == zone_id,
            Transaction.created_at >= start_60,
            Transaction.created_at < start_30,
            Transaction.transaction_type == TransactionType.sale,
        )
    )
    prev_count, prev_revenue = sold_prev.one()

    top_res = await db.execute(
        select(
            Product.id,
            Product.name,
            Product.brand,
            func.count(TransactionItem.id).label("units"),
            func.coalesce(func.sum(TransactionItem.unit_price), 0).label("revenue"),
        )
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Product.zone_id == zone_id,
            Transaction.created_at >= start_30,
            Transaction.transaction_type == TransactionType.sale,
        )
        .group_by(Product.id, Product.name, Product.brand)
        .order_by(func.count(TransactionItem.id).desc())
        .limit(5)
    )
    top_products = [
        {
            "id": str(row.id),
            "name": row.name,
            "brand": row.brand,
            "units": int(row.units),
            "revenue": float(row.revenue),
        }
        for row in top_res
    ]

    alerts: list[dict] = []
    occupancy_pct = (active_count / zone.capacity * 100.0) if zone.capacity else 0.0
    if zone.capacity and occupancy_pct < 40:
        alerts.append({
            "level": "warning",
            "code": "sous_occupation",
            "message": f"Zone sous-remplie ({occupancy_pct:.0f}% de la capacite)",
        })
    if zone.capacity and occupancy_pct > 95:
        alerts.append({
            "level": "info",
            "code": "saturation",
            "message": "Zone satureee — envisage de redistribuer",
        })
    # Product.shelf_date is TIMESTAMP WITHOUT TIME ZONE → strip tz to avoid asyncpg DataError
    stale_cutoff = (now - timedelta(days=60)).replace(tzinfo=None)
    stale_res = await db.execute(
        select(func.count(Product.id)).where(
            Product.zone_id == zone_id,
            Product.status == ProductStatus.display,
            Product.shelf_date < stale_cutoff,
        )
    )
    stale_count = stale_res.scalar_one() or 0
    if stale_count > 0:
        alerts.append({
            "level": "warning",
            "code": "stock_age",
            "message": f"{stale_count} article(s) en rayon depuis plus de 60 jours",
        })

    spark: list[float] = []
    for day_offset in range(30, 0, -1):
        day_start = now - timedelta(days=day_offset)
        day_end = day_start + timedelta(days=1)
        day_res = await db.execute(
            select(func.coalesce(func.sum(TransactionItem.line_total), 0))
            .join(Transaction, Transaction.id == TransactionItem.transaction_id)
            .join(Product, Product.id == TransactionItem.product_id)
            .where(
                Product.zone_id == zone_id,
                Transaction.created_at >= day_start,
                Transaction.created_at < day_end,
                Transaction.transaction_type == TransactionType.sale,
            )
        )
        spark.append(float(day_res.scalar_one() or 0))

    def _pct_delta(curr: float, prev: float) -> float | None:
        if prev <= 0:
            return None
        return (curr - prev) / prev * 100.0

    return {
        "zone_id": str(zone.id),
        "zone_name": zone.name,
        "active_products": active_count,
        "capacity": zone.capacity,
        "occupancy_pct": round(occupancy_pct, 1),
        "revenue_30d": float(sold_revenue or 0),
        "revenue_prev_30d": float(prev_revenue or 0),
        "revenue_delta_pct": _pct_delta(float(sold_revenue or 0), float(prev_revenue or 0)),
        "units_30d": int(sold_count or 0),
        "units_prev_30d": int(prev_count or 0),
        "top_products": top_products,
        "alerts": alerts,
        "sparkline_30d": spark,
        "sales_target_monthly": float(zone.sales_target_monthly) if zone.sales_target_monthly else None,
        "target_reached_pct": (
            round(float(sold_revenue or 0) / float(zone.sales_target_monthly) * 100.0, 1)
            if zone.sales_target_monthly and float(zone.sales_target_monthly) > 0
            else None
        ),
    }


@router.get("/zones/{zone_id}/products")
async def zone_products(
    zone_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List products currently assigned to a zone."""
    result = await db.execute(
        select(Product).where(Product.zone_id == zone_id).order_by(Product.shelf_date.desc().nullslast())
    )
    products = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "brand": p.brand,
            "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            "sale_price": float(p.sale_price) if p.sale_price is not None else None,
            "shelf_date": p.shelf_date.isoformat() if p.shelf_date else None,
            "photo_url": p.photo_url,
            "trend_score": float(p.trend_score) if p.trend_score is not None else None,
        }
        for p in products
    ]


# ---------------------------------------------------------------------------
# Furniture items + zone tags (iso 2.5D mapping)
# ---------------------------------------------------------------------------


VALID_ZONE_TAGS = {
    "homme", "femme", "enfant", "accessoire",
    "derniere_demarque", "nouveaute", "premium",
    "saisonnier", "vitrine", "tete_gondole",
}

VALID_FURNITURE_TYPES = {
    "portant", "mannequin", "etagere", "table_presentation",
    "comptoir_caisse", "cabine_essayage", "vitrine",
    "mur", "porte_entree", "tete_gondole",
}


class FurnitureItemPayload(BaseModel):
    zone_id: uuid.UUID | None = None
    type: str
    variant: str | None = None
    pos_x: float = 0
    pos_y: float = 0
    rotation: int = 0
    scale: float = 1.0
    label: str | None = None


@router.get("/furniture", dependencies=[Depends(manager_only)])
async def list_furniture(
    db: Annotated[AsyncSession, Depends(get_db)],
    zone_id: uuid.UUID | None = Query(default=None),
):
    from app.models.store import FurnitureItem

    stmt = select(FurnitureItem)
    if zone_id:
        stmt = stmt.where(FurnitureItem.zone_id == zone_id)
    rows = await db.execute(stmt)
    return [
        {
            "id": str(f.id),
            "zone_id": str(f.zone_id) if f.zone_id else None,
            "type": f.type,
            "variant": f.variant,
            "pos_x": f.pos_x,
            "pos_y": f.pos_y,
            "rotation": f.rotation,
            "scale": f.scale,
            "label": f.label,
        }
        for f in rows.scalars().all()
    ]


@router.post("/furniture", dependencies=[Depends(manager_only)])
async def create_furniture(
    payload: FurnitureItemPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.store import FurnitureItem

    if payload.type not in VALID_FURNITURE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"type must be one of {sorted(VALID_FURNITURE_TYPES)}",
        )
    f = FurnitureItem(
        zone_id=payload.zone_id,
        type=payload.type,
        variant=payload.variant,
        pos_x=payload.pos_x,
        pos_y=payload.pos_y,
        rotation=payload.rotation,
        scale=max(0.5, min(2.0, payload.scale)),
        label=payload.label,
    )
    db.add(f)
    await db.flush()
    await db.refresh(f)
    return {"id": str(f.id)}


@router.put("/furniture/{furn_id}", dependencies=[Depends(manager_only)])
async def update_furniture(
    furn_id: uuid.UUID,
    payload: FurnitureItemPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.store import FurnitureItem

    res = await db.execute(select(FurnitureItem).where(FurnitureItem.id == furn_id))
    f = res.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Furniture not found")
    f.zone_id = payload.zone_id
    f.type = payload.type
    f.variant = payload.variant
    f.pos_x = payload.pos_x
    f.pos_y = payload.pos_y
    f.rotation = payload.rotation
    f.scale = max(0.5, min(2.0, payload.scale))
    f.label = payload.label
    await db.flush()
    return {"ok": True}


@router.delete("/furniture/{furn_id}", dependencies=[Depends(manager_only)])
async def delete_furniture(
    furn_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.store import FurnitureItem

    res = await db.execute(select(FurnitureItem).where(FurnitureItem.id == furn_id))
    f = res.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Furniture not found")
    await db.delete(f)
    await db.flush()
    return {"ok": True}


class ZoneTagsPayload(BaseModel):
    tags: list[str]


@router.get("/zones/{zone_id}/tags", dependencies=[Depends(manager_only)])
async def list_zone_tags(
    zone_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.store import ZoneTag

    rows = await db.execute(select(ZoneTag).where(ZoneTag.zone_id == zone_id))
    return [t.tag for t in rows.scalars().all()]


@router.put("/zones/{zone_id}/tags", dependencies=[Depends(manager_only)])
async def set_zone_tags(
    zone_id: uuid.UUID,
    payload: ZoneTagsPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Replace the tag set for a zone — atomic upsert (delete+insert)."""
    from app.models.store import ZoneTag

    invalid = set(payload.tags) - VALID_ZONE_TAGS
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Tags inconnus : {sorted(invalid)}. Valides : {sorted(VALID_ZONE_TAGS)}",
        )

    res = await db.execute(select(ZoneTag).where(ZoneTag.zone_id == zone_id))
    for tag in res.scalars().all():
        await db.delete(tag)

    for t in set(payload.tags):
        db.add(ZoneTag(zone_id=zone_id, tag=t))
    await db.flush()
    return {"tags": sorted(set(payload.tags))}
