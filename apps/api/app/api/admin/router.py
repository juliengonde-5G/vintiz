from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.security import RoleChecker, get_current_user, hash_password
from app.models.base import Base
from app.models.inventory import Supplier
from app.models.product import Category, Gender, PriceGrid
from app.models.store import StoreZone
from app.models.user import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])

manager_only = RoleChecker(["manager"])


@router.post("/seed")
async def seed_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(manager_only),
):
    """Run seed logic: create admin user, categories, price grids, supplier, zones."""
    messages: list[str] = []

    # --- Admin user ---
    result = await db.execute(select(User).where(User.username == "admin"))
    if result.scalar_one_or_none():
        messages.append("[skip] Manager user 'admin' already exists.")
    else:
        user = User(
            username="admin",
            email="admin@vintiz.fr",
            password_hash=hash_password("vintiz2026"),
            role=UserRole.manager,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        messages.append("[done] Created manager user: admin / vintiz2026")

    # --- Categories ---
    cat_result = await db.execute(select(Category).limit(1))
    if cat_result.scalar_one_or_none():
        messages.append("[skip] Categories already exist.")
        cat_all = await db.execute(select(Category))
        categories = list(cat_all.scalars().all())
    else:
        categories: list[Category] = []

        enfants_types = [
            "Pantalon / Jean",
            "Haut (T-shirt, Pull, Sweat)",
            "Robe / Jupe",
            "Manteau / Veste",
            "Ensemble / Combinaison",
            "Accessoire",
            "Chaussures",
        ]
        for name in enfants_types:
            cat = Category(name=name, gender=Gender.enfant)
            db.add(cat)
            categories.append(cat)

        femme_types = [
            "Pantalon / Jean",
            "Haut (T-shirt, Blouse, Pull)",
            "Robe",
            "Jupe",
            "Manteau / Veste",
            "Accessoire",
            "Chaussures",
            "Sac",
        ]
        for name in femme_types:
            cat = Category(name=name, gender=Gender.femme)
            db.add(cat)
            categories.append(cat)

        homme_types = [
            "Pantalon / Jean",
            "Haut (T-shirt, Chemise, Pull)",
            "Manteau / Veste",
            "Accessoire",
            "Chaussures",
        ]
        for name in homme_types:
            cat = Category(name=name, gender=Gender.homme)
            db.add(cat)
            categories.append(cat)

        await db.flush()
        messages.append(f"[done] Created {len(categories)} categories.")

    # --- Price grids ---
    pg_result = await db.execute(select(PriceGrid).limit(1))
    if pg_result.scalar_one_or_none():
        messages.append("[skip] Price grids already exist.")
    else:
        brackets = [
            (0.00, 2.00, 5.00),
            (2.01, 5.00, 10.00),
            (5.01, 10.00, 19.00),
            (10.01, 20.00, 29.00),
            (20.01, 40.00, 49.00),
            (40.01, 80.00, 79.00),
            (80.01, 150.00, 119.00),
        ]
        count = 0
        for cat in categories:
            for min_p, max_p, sale_p in brackets:
                grid = PriceGrid(
                    category_id=cat.id,
                    min_purchase=min_p,
                    max_purchase=max_p,
                    sale_price=sale_p,
                )
                db.add(grid)
                count += 1
        await db.flush()
        messages.append(f"[done] Created {count} price grid entries.")

    # --- Supplier ---
    sup_result = await db.execute(
        select(Supplier).where(Supplier.name == "Frip and Co")
    )
    if sup_result.scalar_one_or_none():
        messages.append("[skip] Supplier 'Frip and Co' already exists.")
    else:
        supplier = Supplier(
            name="Frip and Co",
            contact_name="Contact Frip and Co",
            email="contact@fripandco.fr",
            phone="02 32 00 00 00",
            address="France",
            notes="Fournisseur principal de fripe",
        )
        db.add(supplier)
        await db.flush()
        messages.append("[done] Created supplier: Frip and Co")

    # --- Store zones ---
    zone_result = await db.execute(select(StoreZone).limit(1))
    if zone_result.scalar_one_or_none():
        messages.append("[skip] Store zones already exist.")
    else:
        zones = [
            ("Vitrine", "Zone vitrine avant du magasin", 20),
            ("Femme - Hauts", "Espace hauts femme", 60),
            ("Femme - Bas", "Espace bas et jupes femme", 50),
            ("Femme - Robes & Manteaux", "Robes et manteaux femme", 40),
            ("Homme", "Espace homme complet", 50),
            ("Enfants", "Espace enfants", 40),
            ("Accessoires & Chaussures", "Accessoires, sacs et chaussures", 30),
        ]
        for name, description, capacity in zones:
            zone = StoreZone(
                name=name,
                description=description,
                capacity=capacity,
            )
            db.add(zone)
        await db.flush()
        messages.append(f"[done] Created {len(zones)} store zones.")

    await db.commit()
    return {"status": "ok", "messages": messages}


@router.post("/create-tables")
async def create_tables(
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
):
    """Create all database tables. Protected by X-Admin-Key header matching SECRET_KEY."""
    if x_admin_key != settings.SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key",
        )

    # Import all models to ensure they are registered with Base.metadata
    import app.models.user  # noqa: F401
    import app.models.product  # noqa: F401
    import app.models.pos  # noqa: F401
    import app.models.client  # noqa: F401
    import app.models.inventory  # noqa: F401
    import app.models.store  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return {"status": "ok", "message": "All database tables created."}
