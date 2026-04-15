import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.product import Category, Product, ProductStatus
from app.models.inventory import Supplier, Order
from app.models.user import User
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
    return ProductResponse.model_validate(product)


@router.get("/products/search")
async def search_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(..., min_length=1, description="Search query"),
):
    """Search products by name, barcode, or category. Returns max 20 results. Used by POS for quick product lookup."""
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
        .limit(20)
    )
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
