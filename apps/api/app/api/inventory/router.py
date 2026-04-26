import os
import uuid
from datetime import datetime
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
from app.services.photo import PhotoService
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
    return [
        {
            "id": str(p.id),
            "barcode": p.barcode,
            "name": p.name,
            "sale_price": float(p.sale_price),
            "status": p.status.value,
            "category": p.category.name if p.category else None,
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
    from app.services.label import generate_label
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

    # Generate full label
    label_png = generate_label(
        product_name=product.name,
        category=category_name,
        barcode_data=barcode_data,
        price=f"{float(product.sale_price):.2f} €",
        week=week,
        barcode_image=barcode_png,
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

    score = compute_score(
        shelf_date=product.shelf_date,
        sale_price=float(product.sale_price),
        category_avg_price=float(avg_price),
        condition="tres_bon",
        brand=product.brand,
        photo_url=product.photo_url,
    )
    return score


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
