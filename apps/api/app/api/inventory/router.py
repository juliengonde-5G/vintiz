import os
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.product import Category, Product, ProductStatus
from app.models.inventory import Supplier, Order
from app.models.user import User
from app.services.batch import BatchService
from app.services.photo import PhotoService
from app.services.product_lifecycle import ProductLifecycleService
from app.schemas.product import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/inventory", tags=["inventory"])


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@router.get("/products", response_model=PaginatedResponse[ProductResponse])
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: uuid.UUID | None = None,
    status: str | None = None,
    search: str | None = None,
):
    """List products with pagination, filtering, and search."""
    query = select(Product)

    if category_id:
        query = query.where(Product.category_id == category_id)
    if status:
        query = query.where(Product.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Product.name.ilike(pattern),
                Product.barcode.ilike(pattern),
                Product.brand.ilike(pattern),
            )
        )

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    products = result.scalars().all()

    pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


class ProductFromPhotoRequest(BaseModel):
    """Body for ``POST /api/inventory/products/from-photo`` (L3.2).

    All fields except ``photo_url`` are optional. The orchestration extracts
    type / brand / size / color / condition / gamme via Vision and falls
    back to defaults when they're missing.
    """

    photo_url: str
    category_id: uuid.UUID | None = None
    sale_price_hint: float = 0.0
    purchase_price_hint: float = 0.0
    is_test: bool = False


@router.post("/products/from-photo", status_code=status.HTTP_201_CREATED)
async def create_product_from_photo(
    payload: ProductFromPhotoRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a Product from a photo URL — Vision auto-fills the fields.

    Returns the created product, the Vision payload, the score breakdown,
    and a zone suggestion. Resilient to Vision failure (degraded mode).
    """
    from app.services.product_intake import create_from_photo

    result = await create_from_photo(
        db,
        photo_url=payload.photo_url,
        category_id_hint=payload.category_id,
        sale_price_hint=payload.sale_price_hint,
        purchase_price_hint=payload.purchase_price_hint,
        is_test=payload.is_test,
    )

    # P1-003 instrumentation — keep parity with the legacy create_product.
    from app.models.events import EventSource, EventType
    from app.services.events import EventService
    await EventService(db).emit(
        EventType.product_created,
        source=EventSource.admin,
        product_id=uuid.UUID(result["product"]["id"]),
        user_id=current_user.id,
        meta={
            "from_photo": True,
            "vision_used": result["vision_used"],
            "barcode": result["product"]["barcode"],
            "is_test": payload.is_test,
        },
    )
    return result


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_in: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new product."""
    # Generate a barcode if not provided
    barcode_value = product_in.barcode or str(uuid.uuid4())[:12]

    product = Product(
        barcode=barcode_value,
        name=product_in.name,
        category_id=product_in.category_id,
        size=product_in.size,
        color=product_in.color,
        brand=product_in.brand,
        purchase_price=product_in.purchase_price,
        sale_price=product_in.sale_price,
        status=product_in.status,
        week_number=product_in.week_number,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)

    # P1-003: trace inventory creation for downstream analytics.
    from app.models.events import EventSource, EventType
    from app.services.events import EventService
    await EventService(db).emit(
        EventType.product_created,
        source=EventSource.admin,
        product_id=product.id,
        user_id=current_user.id,
        meta={
            "barcode": product.barcode,
            "category_id": str(product.category_id),
            "sale_price": float(product.sale_price),
            "brand": product.brand,
        },
    )

    return ProductResponse.model_validate(product)


@router.get("/products/search")
async def search_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(..., min_length=1, description="Search query"),
    include_sold: bool = Query(False, description="Inclure aussi les produits vendus/retournés"),
):
    """Recherche produits par nom, code-barres ou catégorie. Limité à 20 résultats.

    Par défaut, exclut les produits au statut ``sold`` ou ``returned`` (utile
    pour la caisse — on ne propose que des articles vendables). Passer
    ``?include_sold=true`` pour inclure tout l'historique (ex: SAV, retours).
    """
    pattern = f"%{q}%"
    query = (
        select(Product)
        .outerjoin(Category, Product.category_id == Category.id)
        .where(
            or_(
                Product.name.ilike(pattern),
                Product.barcode.ilike(pattern),
                Category.name.ilike(pattern),
            )
        )
    )
    if not include_sold:
        query = query.where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display])
        )
    query = query.limit(20)
    result = await db.execute(query)
    products = result.scalars().all()

    # P4-005: products currently held by an active reservation are
    # surfaced with a flag so the cashier can refuse the sale or look
    # up the holder in the reservations page.
    from app.services.reservation import list_active_reservation_product_ids

    reserved_ids = await list_active_reservation_product_ids(db)
    return [
        {
            "id": str(p.id),
            "barcode": p.barcode,
            "name": p.name,
            "sale_price": float(p.sale_price),
            "status": p.status.value,
            "category": p.category.name if p.category else None,
            "reserved": p.id in reserved_ids,
        }
        for p in products
    ]


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get a single product by ID."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.model_validate(product)


@router.get("/products/{product_id}/label")
async def get_product_label(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Generate and return a PNG label for a product."""
    from fastapi.responses import Response
    from app.services.label import generate_label, life_cycle_tag_color
    from app.services.barcode import generate_barcode

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    category_name = product.category.name if product.category else "Article"
    week = product.week_number or 1
    barcode_data = product.barcode

    # Generate barcode image
    try:
        barcode_png = generate_barcode(week, category_name[:4].upper(), 1, int(product.sale_price * 100))
    except Exception:
        barcode_png = None

    # Pick the life-cycle tag colour (P3-002).
    tag_color = life_cycle_tag_color(
        status=product.status.value,
        displayed_at=product.displayed_at,
    )

    # Generate full label
    label_png = generate_label(
        product_name=product.name,
        category=category_name,
        barcode_data=barcode_data,
        price=f"{float(product.sale_price):.2f} €",
        week=week,
        barcode_image=barcode_png,
        tag_color=tag_color,
    )

    return Response(content=label_png, media_type="image/png")


@router.post("/products/{product_id}/print-label")
async def print_product_label(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    quantity: int = Query(1, ge=1, le=20),
):
    """Send the product label to the SATO CT4-LX (SBPL, TCP 9100)."""
    from app.services import sato_service
    from app.services.barcode import generate_barcode
    from app.services.hardware_config import load_config
    from app.services.label import generate_label

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    cfg = load_config()["label_printer"]
    if not cfg.get("enabled"):
        raise HTTPException(status_code=400, detail="Imprimante SATO desactivee dans les parametres")
    host = cfg.get("host") or ""
    port = int(cfg.get("port") or 9100)
    if not host:
        raise HTTPException(status_code=400, detail="Adresse IP SATO non configuree")

    category_name = product.category.name if product.category else "Article"
    week = product.week_number or 1
    try:
        barcode_png = generate_barcode(week, category_name[:4].upper(), 1, int(product.sale_price * 100))
    except Exception:  # noqa: BLE001
        barcode_png = None

    label_png = generate_label(
        product_name=product.name,
        category=category_name,
        barcode_data=product.barcode,
        price=f"{float(product.sale_price):.2f} €",
        week=week,
        barcode_image=barcode_png,
    )

    try:
        sato_service.print_label(label_png, host=host, port=port, quantity=quantity)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Imprimante SATO injoignable : {exc}") from exc

    return {"success": True, "quantity": quantity, "product_id": str(product_id)}


@router.get("/products/{product_id}/score")
async def get_product_score(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Compute and return detailed score for a product."""
    from app.models.product import ProductPhoto
    from app.services.brand_tiers import get_brand_score
    from app.services.category_trends import get_category_trend
    from app.services.scoring_service import compute_score

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get category avg price
    avg_result = await db.execute(
        select(func.avg(Product.sale_price)).where(Product.category_id == product.category_id)
    )
    avg_price = avg_result.scalar_one_or_none() or float(product.sale_price)

    # Plug in the live category trend (P2-010) — replaces the old static 50.0.
    trend = await get_category_trend(db, product.category_id)

    # Plug in the DB-driven brand tier (P2-012).
    brand_score = await get_brand_score(db, product.brand)

    # Plug in photo count + Vision confidence (P2-011). Aggregating in
    # the request handler keeps compute_score sync + pure.
    photo_rows = (await db.execute(
        select(ProductPhoto.ai_confidence)
        .where(ProductPhoto.product_id == product_id)
    )).all()
    photo_count = len(photo_rows)
    confidences = [c for (c,) in photo_rows if c is not None]
    photo_avg_confidence = (
        sum(confidences) / len(confidences) if confidences else None
    )

    score = compute_score(
        shelf_date=product.shelf_date,
        sale_price=float(product.sale_price),
        category_avg_price=float(avg_price),
        condition="tres_bon",
        brand=product.brand,
        photo_url=product.photo_url,
        category_trend=trend,
        brand_score=brand_score,
        photo_count=photo_count,
        photo_avg_confidence=photo_avg_confidence,
    )
    return score


@router.get("/products/{product_id}/insights")
async def get_product_insights(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """P4-010: small set of contextual badges for the POS UI.

    Sales velocity, time on the floor, brand tier, Vintiz score and
    active hold. Computed on demand — cheap (< 5 small queries) so the
    badge can refresh whenever the cashier scans a barcode.
    """
    from app.services.product_insights import compute_for_product, to_dict

    result = await compute_for_product(db, product_id)
    return to_dict(result)


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: uuid.UUID,
    product_in: ProductUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update an existing product."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    await db.flush()
    await db.refresh(product)
    return ProductResponse.model_validate(product)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Soft-delete a product by setting status to 'returned'."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    product.status = ProductStatus.returned
    await db.flush()


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List all categories."""
    result = await db.execute(select(Category))
    categories = result.scalars().all()
    return [CategoryResponse.model_validate(c) for c in categories]


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_in: CategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new category."""
    category = Category(
        name=category_in.name,
        parent_id=category_in.parent_id,
        gender=category_in.gender,
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return CategoryResponse.model_validate(category)


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

@router.get("/suppliers")
async def list_suppliers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List all suppliers."""
    result = await db.execute(select(Supplier))
    return result.scalars().all()


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
async def create_supplier(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    contact_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
):
    """Create a new supplier."""
    supplier = Supplier(name=name, contact_name=contact_name, email=email, phone=phone)
    db.add(supplier)
    await db.flush()
    await db.refresh(supplier)
    return supplier


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@router.get("/orders")
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List all orders."""
    result = await db.execute(select(Order))
    return result.scalars().all()


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order(
    reference: str,
    supplier_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    purchase_cost: float = 0,
    notes: str | None = None,
):
    """Create a new order."""
    order = Order(
        reference=reference,
        supplier_id=supplier_id,
        purchase_cost=purchase_cost,
        notes=notes,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)
    return order


# ---------------------------------------------------------------------------
# Multi-photos (P1-008) — list / add / set primary / reorder / delete
# ---------------------------------------------------------------------------


class PhotoAddRequest(BaseModel):
    url: str
    ai_analyzed_at: datetime | None = None
    ai_confidence: float | None = None


class PhotoReorderRequest(BaseModel):
    ordered_ids: list[uuid.UUID]


@router.get("/products/{product_id}/photos")
async def list_product_photos(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await PhotoService(db).list_photos(product_id)


@router.post(
    "/products/{product_id}/photos", status_code=status.HTTP_201_CREATED
)
async def add_product_photo(
    product_id: uuid.UUID,
    request: PhotoAddRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    photo = await PhotoService(db).add_photo(
        product_id=product_id,
        url=request.url,
        ai_analyzed_at=request.ai_analyzed_at,
        ai_confidence=request.ai_confidence,
    )
    await db.commit()
    return {
        "id": str(photo.id),
        "url": photo.url,
        "is_primary": photo.is_primary,
        "order_index": photo.order_index,
    }


@router.post("/products/{product_id}/photos/{photo_id}/primary")
async def set_primary_photo(
    product_id: uuid.UUID,
    photo_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    photo = await PhotoService(db).set_primary(product_id, photo_id)
    await db.commit()
    return {"id": str(photo.id), "is_primary": True}


@router.post("/products/{product_id}/photos/reorder")
async def reorder_product_photos(
    product_id: uuid.UUID,
    request: PhotoReorderRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    rows = await PhotoService(db).reorder(product_id, request.ordered_ids)
    await db.commit()
    return rows


# Local storage for uploaded photos. Resolved relative to the project root so
# the mount in main.py and this router agree on the same folder regardless of
# where uvicorn is launched from. Switch to S3/Scaleway later by replacing
# the body of this handler.
UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "uploads" / "products"
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post(
    "/products/{product_id}/photos/upload",
    status_code=status.HTTP_201_CREATED,
)
async def upload_product_photo(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    """Accept a multipart upload, persist the file under uploads/products/, then
    register it via PhotoService so it benefits from the same invariants
    (primary mirror, contiguous order_index, audit trail).
    """
    # Validate that the product exists upfront — avoids orphan files on disk.
    product_row = await db.execute(select(Product).where(Product.id == product_id))
    if product_row.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Product not found")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_PHOTO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {sorted(ALLOWED_PHOTO_EXTENSIONS)}",
        )

    # Read with cap to bound memory + reject oversized uploads.
    blob = await file.read(MAX_PHOTO_BYTES + 1)
    if len(blob) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_PHOTO_BYTES // (1024 * 1024)} MB)",
        )
    if not blob:
        raise HTTPException(status_code=400, detail="Empty file")

    target_dir = UPLOAD_ROOT / str(product_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{uuid.uuid4().hex}{suffix}"
    target_path = target_dir / fname
    target_path.write_bytes(blob)
    os.chmod(target_path, 0o644)

    public_url = f"/uploads/products/{product_id}/{fname}"
    photo = await PhotoService(db).add_photo(product_id=product_id, url=public_url)
    await db.commit()
    return {
        "id": str(photo.id),
        "url": photo.url,
        "is_primary": photo.is_primary,
        "order_index": photo.order_index,
    }


class TransitionRequest(BaseModel):
    to_status: str
    reason: str | None = None
    new_price: float | None = None  # required for markdown transitions


@router.post("/products/{product_id}/transition")
async def transition_product(
    product_id: uuid.UUID,
    request: TransitionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Move a product through its life cycle.

    Validates the transition against the finite-state machine, stamps
    life-cycle anchors (``received_at`` / ``displayed_at``) the first
    time they're entered, appends a row to ``markdown_history`` for
    discount transitions, and emits the matching analytics event.
    """
    try:
        target = ProductStatus(request.to_status)
    except ValueError:
        valid = ", ".join(s.value for s in ProductStatus)
        raise HTTPException(
            status_code=400,
            detail=f"Unknown status. Valid values: {valid}",
        )

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    new_price = (
        Decimal(str(request.new_price)) if request.new_price is not None else None
    )
    await ProductLifecycleService(db).transition(
        product,
        target,
        user_id=current_user.id,
        reason=request.reason,
        new_price=new_price,
    )
    await db.commit()
    return {
        "id": str(product.id),
        "status": product.status.value,
        "received_at": product.received_at.isoformat() if product.received_at else None,
        "displayed_at": product.displayed_at.isoformat() if product.displayed_at else None,
        "sale_price": float(product.sale_price),
        "markdown_history": product.markdown_history or [],
    }


@router.delete(
    "/products/{product_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product_photo(
    product_id: uuid.UUID,
    photo_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await PhotoService(db).delete_photo(product_id, photo_id)
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Intake batches (P2-015) — carton-level traceability
# ---------------------------------------------------------------------------


class BatchCreateRequest(BaseModel):
    source: str  # IntakeSource enum value
    n_items_received: int = 0
    notes: str | None = None


class BatchAssignProductRequest(BaseModel):
    product_id: uuid.UUID


@router.post(
    "/batches",
    status_code=status.HTTP_201_CREATED,
)
async def create_batch(
    request: BatchCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    from app.models.batch import IntakeSource

    try:
        source = IntakeSource(request.source)
    except ValueError:
        valid = ", ".join(s.value for s in IntakeSource)
        raise HTTPException(
            status_code=400,
            detail=f"Unknown intake source. Valid values: {valid}",
        )
    batch = await BatchService(db).create_batch(
        source=source,
        n_items_received=request.n_items_received,
        notes=request.notes,
        recorded_by_user_id=current_user.id,
    )
    await db.commit()
    return {
        "id": str(batch.id),
        "batch_number": batch.batch_number,
        "source": batch.source.value,
        "received_at": batch.received_at.isoformat() if batch.received_at else None,
        "n_items_received": batch.n_items_received,
    }


@router.get("/batches")
async def list_batches(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 50,
):
    return await BatchService(db).list_batches(skip=skip, limit=limit)


@router.get("/batches/{batch_id}")
async def get_batch(
    batch_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await BatchService(db).get_batch(batch_id)


@router.post("/batches/{batch_id}/assign-product")
async def assign_product_to_batch(
    batch_id: uuid.UUID,
    request: BatchAssignProductRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    product = await BatchService(db).assign_product(batch_id, request.product_id)
    await db.commit()
    return {
        "id": str(product.id),
        "intake_batch_id": str(product.intake_batch_id),
    }


# ---------------------------------------------------------------------------
# Bulk import (P3-006) — CSV upload
# ---------------------------------------------------------------------------


@router.post("/products/import-csv")
async def import_products_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    dry_run: bool = False,
):
    """Import products in bulk from a CSV.

    Required columns: ``name``, ``sale_price`` + either ``category_id``
    (UUID) or ``category_name`` (must already exist).
    Optional: ``barcode``, ``brand``, ``color``, ``size``, ``condition``,
    ``purchase_price``, ``week_number``, ``status``, ``description``.

    ``dry_run=true`` validates without persisting.
    """
    from app.services.csv_import import ImportCsvService

    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="File must be a .csv (got " f"{file.filename!r})",
        )
    blob = await file.read()
    if len(blob) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV too large (max 5 MB)")
    if not blob:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        summary = await ImportCsvService(db).import_csv(blob, dry_run=dry_run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not dry_run:
        await db.commit()

    return {
        "dry_run": dry_run,
        "total_rows": summary.total_rows,
        "imported": summary.imported,
        "skipped_existing_barcode": summary.skipped,
        "errors": [
            {"line": e.line, "message": e.message} for e in summary.errors
        ],
        "created_ids": summary.created_ids,
    }


# ---------------------------------------------------------------------------
# Audit history per product (P3-008)
# ---------------------------------------------------------------------------


@router.get("/products/{product_id}/history")
async def get_product_history(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 100,
):
    """Return the chronological audit trail for a single product.

    Reads ``audit_logs`` rows where ``entity = 'product'`` and
    ``entity_id = product_id``. The audit listener (P1-013) populates
    these for create / update / delete with a per-field diff, so this
    endpoint surfaces price changes, status transitions, zone moves,
    etc. — all without a dedicated history table.
    """
    from app.models.audit import AuditLog

    capped = min(max(limit, 1), 500)
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.entity == "product",
            AuditLog.entity_id == product_id,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(capped)
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(row.id),
            "action": row.action,
            "user_id": str(row.user_id) if row.user_id else None,
            "data": row.data,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Merchandising / Booster IA — placement + locate (P2-006 + P2-008)
# ---------------------------------------------------------------------------


@router.get("/products/{product_id}/suggest-zone")
async def suggest_zone_for_product(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Recommend a store zone for a freshly-tagged product (P2-006)."""
    from app.services.merchandising import MerchandisingService

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    suggestion = await MerchandisingService(db).suggest_zone(product)
    return {
        "product_id": str(product.id),
        "primary_zone_id": suggestion.primary_zone_id,
        "primary_zone_name": suggestion.primary_zone_name,
        "alternative_zone_id": suggestion.alternative_zone_id,
        "alternative_zone_name": suggestion.alternative_zone_name,
        "should_go_to_window": suggestion.should_go_to_window,
        "rationale": suggestion.rationale,
    }


@router.get("/locate")
async def locate_product(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(..., min_length=1, max_length=100),
):
    """Find a product on the floor — exact barcode wins, otherwise fuzzy
    name match. Used by Sophie when a customer asks "vous avez encore ce
    trench beige ?" (P2-008)."""
    from app.services.merchandising import MerchandisingService

    return await MerchandisingService(db).locate_product(q)
