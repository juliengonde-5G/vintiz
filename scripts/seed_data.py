"""Seed script for Vintiz V2.

Creates initial data:
- Manager user (admin / vintiz2026)
- Product categories (ENFANTS + ADULTES)
- Price grid entries
- Default supplier "Frip and Co"
- 7 store zones

Usage:
    cd apps/api && python -m scripts.seed_data
    # or from project root:
    PYTHONPATH=apps/api python scripts/seed_data.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure the api app is importable
api_root = Path(__file__).resolve().parent.parent / "apps" / "api"
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session, engine
from app.core.security import hash_password
from app.models.base import Base
from app.models.user import User, UserRole
from app.models.product import Category, Gender, PriceGrid
from app.models.inventory import Supplier
from app.models.store import StoreZone


async def seed_user(db: AsyncSession) -> None:
    """Create the default manager user."""
    result = await db.execute(select(User).where(User.username == "admin"))
    if result.scalar_one_or_none():
        print("[skip] Manager user 'admin' already exists.")
        return

    user = User(
        username="admin",
        email="admin@vintiz.fr",
        password_hash=hash_password("vintiz2026"),
        role=UserRole.manager,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    print("[done] Created manager user: admin / vintiz2026")


async def seed_categories(db: AsyncSession) -> list[Category]:
    """Create product categories from the Excel grille (ENFANTS + ADULTES)."""
    result = await db.execute(select(Category).limit(1))
    if result.scalar_one_or_none():
        print("[skip] Categories already exist.")
        result = await db.execute(select(Category))
        return list(result.scalars().all())

    categories: list[Category] = []

    # ENFANTS categories
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
        print(f"  [+] Category ENFANT: {name}")

    # ADULTES FEMME categories
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
        print(f"  [+] Category FEMME: {name}")

    # ADULTES HOMME categories
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
        print(f"  [+] Category HOMME: {name}")

    await db.flush()
    print(f"[done] Created {len(categories)} categories.")
    return categories


async def seed_price_grids(db: AsyncSession, categories: list[Category]) -> None:
    """Create price grid entries for categories."""
    result = await db.execute(select(PriceGrid).limit(1))
    if result.scalar_one_or_none():
        print("[skip] Price grids already exist.")
        return

    # Default price brackets (purchase range -> sale price)
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
    print(f"[done] Created {count} price grid entries.")


async def seed_supplier(db: AsyncSession) -> None:
    """Create the default supplier."""
    result = await db.execute(select(Supplier).where(Supplier.name == "Frip and Co"))
    if result.scalar_one_or_none():
        print("[skip] Supplier 'Frip and Co' already exists.")
        return

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
    print("[done] Created supplier: Frip and Co")


async def seed_store_zones(db: AsyncSession) -> None:
    """Create the 7 store zones."""
    result = await db.execute(select(StoreZone).limit(1))
    if result.scalar_one_or_none():
        print("[skip] Store zones already exist.")
        return

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
        print(f"  [+] Zone: {name} (capacity: {capacity})")

    await db.flush()
    print(f"[done] Created {len(zones)} store zones.")


async def main() -> None:
    print("=" * 50)
    print("  Vintiz V2 - Seed Data")
    print("=" * 50)
    print()

    async with async_session() as db:
        try:
            await seed_user(db)
            categories = await seed_categories(db)
            await seed_price_grids(db, categories)
            await seed_supplier(db)
            await seed_store_zones(db)
            await db.commit()
            print()
            print("All seed data created successfully!")
        except Exception as e:
            await db.rollback()
            print(f"\nError during seeding: {e}")
            raise

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
