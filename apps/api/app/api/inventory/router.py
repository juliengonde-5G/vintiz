import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.inventory import Supplier, Order
from app.models.brand_tier import BrandTier
from app.models.store import StoreZone
from app.models.user import User
from app.services.batch import BatchService
from app.services.photo import PhotoService
from app.services.product_lifecycle import ProductLifecycleService
from app.services import storefront_photo
from app.schemas.product import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/inventory", tags=["inventory"])


# Statuses that mean "physically on the shop floor" (en magasin / en rayon) as
# opposed to held in the back stock. Drives the inventory stock/magasin split
# and the automatic stamping of the shelf date.
FLOOR_STATUSES = {
    ProductStatus.display,
    ProductStatus.displayed,
    ProductStatus.discounted,
    ProductStatus.deep_discounted,
}


def _stamp_lifecycle_dates(product: Product) -> None:
    """Backfill the intake / shelf anchors so the inventory dates are never
    blank for products created or moved through the normal flow.

    - ``received_at`` (entrée en stock) is stamped the first time we see the
      product if it isn't already set.
    - When a product sits on the floor, ``displayed_at`` and ``shelf_date``
      (mise en rayon) are stamped once. ``shelf_date`` is what scoring and
      the labels read, so we keep the two in sync.
    """
    now = datetime.now(timezone.utc)
    if product.received_at is None:
        product.received_at = now
    if product.status in FLOOR_STATUSES:
        if product.displayed_at is None:
            product.displayed_at = now
        if product.shelf_date is None:
            product.shelf_date = now


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
    location: str | None = Query(
        None,
        description="Filtre localisation : 'stock' (réserve) ou 'magasin' (en rayon)",
    ),
    search: str | None = None,
):
    """List products with pagination, filtering, and search.

    ``location`` is a coarse split over the life-cycle statuses: ``stock``
    matches the back-room states, ``magasin`` matches everything physically on
    the floor. It coexists with the finer ``status`` filter.
    """
    query = select(Product)

    if category_id:
        query = query.where(Product.category_id == category_id)
    if status:
        query = query.where(Product.status == status)
    if location == "stock":
        query = query.where(
            Product.status.in_([
                ProductStatus.stock,
                ProductStatus.received,
                ProductStatus.sorted,
                ProductStatus.tagged,
            ])
        )
    elif location == "magasin":
        query = query.where(Product.status.in_(FLOOR_STATUSES))
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

    # Resolve zone names in a single query so the inventory table can show
    # the boutique placement ("Emplacement") without an N+1.
    zone_ids = {p.zone_id for p in products if p.zone_id is not None}
    zone_names: dict = {}
    if zone_ids:
        zrows = await db.execute(
            select(StoreZone.id, StoreZone.name).where(StoreZone.id.in_(zone_ids))
        )
        zone_names = {zid: zname for zid, zname in zrows.all()}
    for p in products:
        # Transient attribute read by ProductResponse (from_attributes).
        p.zone_name = zone_names.get(p.zone_id)

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


def _generate_vintiz_barcode() -> str:
    """Generate a Vintiz-formatted barcode matching the brief spec.

    Format: ``VTZ-YYYY-NNNNNN`` — prefix + current year + 6-digit
    pseudo-random sequence. Same shape as the documented example
    (``VTZ-2026-00142``) so labels printed by the Zebra look familiar.

    The 6-digit space (100 000 … 999 999) gives 900 000 possible codes
    per year; collisions are vanishingly rare at the volume of a single
    boutique (a few hundred items per year). If a collision does occur,
    the unique constraint on ``Product.barcode`` raises an
    ``IntegrityError`` and the caller can retry — kept simple here
    rather than wrapping in a retry loop.
    """
    from datetime import datetime
    import secrets
    seq = secrets.randbelow(900_000) + 100_000  # always 6 digits
    return f"VTZ-{datetime.now().year}-{seq:06d}"


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_in: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new product."""
    barcode_value = product_in.barcode or _generate_vintiz_barcode()

    # Coerce the string status into the enum explicitly. Without this,
    # SQLAlchemy can leave the raw string in the column on some
    # drivers, and the ``Product.status.in_([ProductStatus.stock, …])``
    # filter at /search then fails to match — symptomatic of the
    # "newly created product not found on scan" bug.
    try:
        status_enum = ProductStatus(product_in.status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"status invalide : {product_in.status}. Valeurs autorisées : "
                   f"{[s.value for s in ProductStatus]}",
        )

    product = Product(
        barcode=barcode_value,
        name=product_in.name,
        category_id=product_in.category_id,
        size=product_in.size,
        color=product_in.color,
        brand=product_in.brand,
        condition=product_in.condition,
        purchase_price=product_in.purchase_price,
        sale_price=product_in.sale_price,
        status=status_enum,
        week_number=product_in.week_number,
    )
    # Stamp entrée-stock (and mise-en-rayon when created directly on the floor)
    # so the inventory dates are populated from the very first save.
    _stamp_lifecycle_dates(product)
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
    # Strip aggressively so a scanned barcode with a trailing CR/LF
    # injected by the BCST-35 still resolves on the inventory page's
    # search box (the user types a barcode then hits Enter, or the
    # scanner injects Enter as its suffix — same effect).
    clean = "".join(q.split()) or q.strip()
    pattern = f"%{clean}%"
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
        # Accept the full "vendable" lifecycle, not just the legacy
        # ``stock`` + ``display`` pair. ``displayed`` is what the
        # automated lifecycle uses for products actually on the floor.
        query = query.where(
            Product.status.in_([
                ProductStatus.stock,
                ProductStatus.display,
                ProductStatus.displayed,
                ProductStatus.discounted,
                ProductStatus.deep_discounted,
            ])
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
            # Surface the product photo so the POS can render a
            # thumbnail in the search results — the cashier can then
            # confirm visually before adding the item to the cart.
            "photo_url": getattr(p, "photo_url", None),
        }
        for p in products
    ]


@router.get("/products/by-barcode/{barcode}")
async def get_product_by_barcode(
    barcode: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Exact-match lookup by barcode — used by the POS scan flow.

    Aggressively tolerant : the Inateck BCST-35 scanner sometimes
    sends garbage characters before/after the data depending on its
    keyboard locale and "suffix" config. We strip all whitespace and
    fall back to a case-insensitive match so a CapsLock-flipped scan
    still finds the product. The check on "is this article vendable"
    stays the responsibility of the cart code (it already handles
    non-stock statuses, e.g. refuses to add a ``sold`` item twice).
    """
    import logging
    logger = logging.getLogger("vintiz")
    # Strip all whitespace (including CR/LF/Tab the scanner may inject).
    code = "".join((barcode or "").split())
    if not code:
        raise HTTPException(status_code=400, detail="barcode manquant")

    # Exact match first.
    result = await db.execute(
        select(Product)
        .outerjoin(Category, Product.category_id == Category.id)
        .where(Product.barcode == code)
        .limit(1)
    )
    product = result.scalar_one_or_none()

    # Case-insensitive fallback — handles a CapsLock-flipped scan (the
    # BCST-35 in FR keyboard layout sends "vtz-2026-123456" when caps
    # is engaged, even though the printed Code 128 is uppercase).
    if product is None:
        result = await db.execute(
            select(Product)
            .outerjoin(Category, Product.category_id == Category.id)
            .where(Product.barcode.ilike(code))
            .limit(1)
        )
        product = result.scalar_one_or_none()

    # Keyboard-layout fallback — the Inateck scanner emulates a US-QWERTY
    # keyboard, but the tablet runs French AZERTY, so every hyphen of the
    # printed barcode is typed as "=" ("VTZ-2026-372694" arrives as
    # "VTZ=2026=372694"). Vintiz barcodes never contain "=", so when the
    # scan still misses we map "=" back to "-" and retry (ilike covers the
    # exact + caps cases in one query).
    if product is None and "=" in code:
        alt = code.replace("=", "-")
        result = await db.execute(
            select(Product)
            .outerjoin(Category, Product.category_id == Category.id)
            .where(Product.barcode.ilike(alt))
            .limit(1)
        )
        product = result.scalar_one_or_none()

    # Inventory diagnostic log so the manager can see what was actually
    # scanned when a "not found" report comes in. Logged at INFO so it
    # ends up in the daily journal without spamming WARNING.
    if product is None:
        logger.info(
            "barcode lookup miss : raw=%r normalised=%r — check that the printed label matches Product.barcode in DB",
            barcode, code,
        )
        raise HTTPException(
            status_code=404,
            detail=f"Aucun produit ne porte le code-barres {code}",
        )

    return {
        "id": str(product.id),
        "barcode": product.barcode,
        "name": product.name,
        "sale_price": float(product.sale_price),
        "status": product.status.value,
        "category": product.category.name if product.category else None,
        "photo_url": getattr(product, "photo_url", None),
    }


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


@router.get("/products/{product_id}/score")
async def get_product_score(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Compute and return detailed score for a product."""
    from app.services.brand_tiers import get_brand_score
    from app.services.category_trends import get_category_trend
    from app.services.category_velocity import get_velocity_for_category
    from app.services.market_price_estimator import get_or_refresh_estimate
    from app.services.scoring_config import get_scoring_config
    from app.services.scoring_service import compute_score

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    config = await get_scoring_config(db)
    trend = await get_category_trend(db, product.category_id)
    brand_score = await get_brand_score(db, product.brand)
    velocity = await get_velocity_for_category(db, product.category_id)
    market_estimate = await get_or_refresh_estimate(db, product)

    score = compute_score(
        shelf_date=product.shelf_date,
        sale_price=float(product.sale_price),
        market_price_estimate=market_estimate,
        category_name=product.category.name if product.category else None,
        category_trend=trend,
        category_avg_velocity=velocity,
        brand_score=brand_score,
        condition=getattr(product, "condition", None),
        config=config,
    )
    await db.commit()
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
        # Coerce the incoming status string to the enum so the FLOOR_STATUSES
        # membership test below (and the column itself) compare correctly.
        if field == "status" and isinstance(value, str):
            try:
                value = ProductStatus(value)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"status invalide : {value}",
                )
        setattr(product, field, value)

    # Moving a product onto the floor (mise en rayon) stamps the shelf date
    # automatically when the caller didn't provide one — keeps scoring,
    # labels and the inventory "Mise en rayon" column consistent.
    _stamp_lifecycle_dates(product)

    try:
        await db.flush()
        await db.refresh(product)
    except Exception as exc:
        # Wrap DB errors as explicit HTTP 500 so the client always receives a
        # proper JSON response rather than a dropped connection.
        logging.getLogger("vintiz").error("update_product flush failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur base de données : {type(exc).__name__}",
        )
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
# Brands — autocomplete source for the product-intake form
# ---------------------------------------------------------------------------

# Curated well-known labels so the intake brand field offers sensible
# suggestions even before the catalogue / brand_tiers are populated.
KNOWN_BRANDS = [
    "Sandro", "Maje", "Claudie Pierlot", "Sézane", "ba&sh", "The Kooples",
    "Zadig & Voltaire", "IRO", "Isabel Marant", "Comptoir des Cotonniers",
    "Gérard Darel", "American Vintage", "Sessùn", "Vanessa Bruno", "Bash",
    "COS", "Arket", "& Other Stories", "Massimo Dutti", "Zara", "Mango",
    "Levi's", "Petit Bateau", "Antik Batik", "Bel Air", "Des Petits Hauts",
    "Chanel", "Dior", "Hermès", "Louis Vuitton", "Gucci", "Prada",
    "Saint Laurent", "Céline", "Balenciaga", "Burberry", "Max Mara",
    "Moncler", "Lacoste", "Ralph Lauren", "Tommy Hilfiger", "Nike", "Adidas",
]


@router.get("/brands")
async def list_brands(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Distinct brand names for the intake autocomplete.

    Union of: brands already used in the catalogue, the manager-editable
    ``brand_tiers`` table, and a curated well-known list — deduplicated
    case-insensitively and sorted alphabetically.
    """
    catalog_rows = await db.execute(
        select(Product.brand).where(Product.brand.is_not(None)).distinct()
    )
    catalog = [b for (b,) in catalog_rows.all() if b and b.strip()]

    tier_rows = await db.execute(select(BrandTier.name))
    tiers = [n.title() for (n,) in tier_rows.all() if n and n.strip()]

    seen: dict[str, str] = {}
    for brand in [*catalog, *tiers, *KNOWN_BRANDS]:
        key = brand.strip().lower()
        if key and key not in seen:
            seen[key] = brand.strip()
    return sorted(seen.values(), key=lambda s: s.lower())


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List all categories, alphabetically."""
    result = await db.execute(select(Category).order_by(Category.name))
    categories = result.scalars().all()
    return [CategoryResponse.model_validate(c) for c in categories]


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_in: CategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a category — idempotent on name to avoid duplicate rows.

    Le formulaire (et d'anciens seeds non idempotents) pouvaient créer
    plusieurs fois la même catégorie ("Robes", "robes", "Robes ") d'où la
    liste qui apparaissait en double. On normalise (trim) et on renvoie la
    catégorie existante si le nom correspond déjà (insensible à la casse).
    """
    name = (category_in.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="nom de catégorie manquant")

    existing = await db.execute(
        select(Category).where(Category.name.ilike(name)).order_by(Category.created_at).limit(1)
    )
    found = existing.scalars().first()
    if found is not None:
        return CategoryResponse.model_validate(found)

    category = Category(
        name=name,
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
    # Auto-generate the branded storefront copy here too, so a photo added by
    # URL gets the same background-removed vitrine as a file upload. Best-effort:
    # if the source can't be fetched or no backend is configured, the status
    # records why and the raw photo still serves.
    source = await storefront_photo.fetch_source_bytes(request.url)
    if source is None:
        processed_url, processing_status = None, "failed"
    else:
        blob, media_type = source
        processed_url, processing_status = await storefront_photo.generate_and_persist(
            product_id, blob, media_type
        )

    photo = await PhotoService(db).add_photo(
        product_id=product_id,
        url=request.url,
        ai_analyzed_at=request.ai_analyzed_at,
        ai_confidence=request.ai_confidence,
        processed_url=processed_url,
        processing_status=processing_status,
    )
    await db.commit()
    return {
        "id": str(photo.id),
        "url": photo.url,
        "processed_url": photo.processed_url,
        "processing_status": photo.processing_status,
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
MAX_PHOTO_BYTES = 20 * 1024 * 1024  # 20 MB — safety net; the tablet downscales before upload
_SUFFIX_TO_MEDIA_TYPE = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _media_type_for(suffix: str) -> str:
    return _SUFFIX_TO_MEDIA_TYPE.get(suffix.lower(), "image/jpeg")


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

    # Auto-generate the branded, background-removed storefront copy. Synchronous
    # so the new-product flow can present it on its final screen; best-effort so
    # a missing backend or a processing error never fails the upload.
    processed_url, processing_status = await storefront_photo.generate_and_persist(
        product_id, blob, _media_type_for(suffix)
    )

    photo = await PhotoService(db).add_photo(
        product_id=product_id,
        url=public_url,
        processed_url=processed_url,
        processing_status=processing_status,
    )
    await db.commit()
    return {
        "id": str(photo.id),
        "url": photo.url,
        "processed_url": photo.processed_url,
        "processing_status": photo.processing_status,
        "is_primary": photo.is_primary,
        "order_index": photo.order_index,
    }


@router.post("/products/{product_id}/photos/{photo_id}/storefront")
async def regenerate_storefront_photo(
    product_id: uuid.UUID,
    photo_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """(Re)generate the branded storefront copy of an existing photo.

    Lets the operator retry a failed/skipped generation or refresh the cutout
    for a photo that was added by URL. Sourced from the stored original image.
    """
    result = await db.execute(
        select(ProductPhoto).where(
            ProductPhoto.id == photo_id,
            ProductPhoto.product_id == product_id,
        )
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    source = await storefront_photo.fetch_source_bytes(photo.url)
    if source is None:
        await PhotoService(db).set_processed(product_id, photo_id, None, "failed")
        await db.commit()
        raise HTTPException(status_code=422, detail="Original image unavailable")

    blob, media_type = source
    processed_url, processing_status = await storefront_photo.generate_and_persist(
        product_id, blob, media_type
    )
    updated = await PhotoService(db).set_processed(
        product_id, photo_id, processed_url, processing_status
    )
    await db.commit()
    return {
        "id": str(updated.id),
        "processed_url": updated.processed_url,
        "processing_status": updated.processing_status,
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
