"""Seed script for Vintiz V2.

Creates initial data:
- Manager user (admin / vintiz2026)
- Product categories (ENFANTS + ADULTES)
- Price grid entries
- Default supplier "Frip and Co"
- 7 store zones
- 50 clients with loyalty accounts
- 300 products (varied brands, categories, prices, statuses)
- Transaction history (last 12 months)

Usage:
    cd apps/api && python -m scripts.seed_data
    # or from project root:
    PYTHONPATH=apps/api python scripts/seed_data.py
"""

import asyncio
import sys
import random
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure the api app is importable
api_root = Path(__file__).resolve().parent.parent / "apps" / "api"
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session, engine
from app.core.security import hash_password
from app.models.base import Base
from app.models.user import User, UserRole
from app.models.product import Category, Gender, PriceGrid, Product, ProductStatus
from app.models.inventory import Supplier
from app.models.store import StoreZone
from app.models.client import Client, LoyaltyAccount
from app.models.pos import Transaction, TransactionItem, Payment, PaymentMethod, TransactionType

rng = random.Random(42)  # deterministic seed


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

BRANDS_PREMIUM = ["Sandro", "Maje", "Ba&sh", "Isabel Marant", "A.P.C.", "Jacquemus",
                   "See by Chloé", "Claudie Pierlot", "The Kooples", "Vanessa Bruno"]
BRANDS_STANDARD = ["Zara", "H&M", "Mango", "Cos", "Uniqlo", "Massimo Dutti",
                    "&Other Stories", "Arket", "Monki", "Pull&Bear"]
BRANDS_SPORTSWEAR = ["Nike", "Adidas", "New Balance", "Levi's", "Tommy Hilfiger", "Ralph Lauren"]
BRANDS_KIDS = ["Petit Bateau", "Bonpoint", "Jacadi", "Catimini", "Sergent Major", "Zara Kids",
               "H&M Kids", "Cyrillus"]

COLORS_FEMME = ["Blanc cassé", "Noir", "Camel", "Bleu marine", "Rose poudré",
                "Vert sauge", "Beige", "Bordeaux", "Corail", "Lavande",
                "Gris perle", "Jaune moutarde", "Terracotta", "Kaki", "Bleu ciel"]
COLORS_HOMME = ["Bleu marine", "Blanc", "Gris", "Noir", "Kaki", "Beige", "Bordeaux", "Vert"]
COLORS_KIDS = ["Rouge", "Bleu", "Rose", "Vert", "Jaune", "Blanc", "Marine", "Multicolore"]
SIZES_FEMME = ["XS", "S", "M", "L", "XL", "36", "38", "40", "42", "44"]
SIZES_HOMME = ["S", "M", "L", "XL", "XXL", "44", "46", "48", "50", "52"]
SIZES_KIDS = ["3 ans", "4 ans", "5 ans", "6 ans", "7 ans", "8 ans", "10 ans", "12 ans", "14 ans"]
CONDITIONS = ["Excellent", "Très bon état", "Bon état", "Correct"]
CONDITION_WEIGHTS = [0.20, 0.40, 0.30, 0.10]

FIRST_NAMES_F = ["Sophie", "Emma", "Claire", "Marie", "Lucie", "Camille", "Julie", "Laure",
                 "Alice", "Charlotte", "Mathilde", "Elise", "Isabelle", "Nathalie", "Aurore",
                 "Céline", "Vanessa", "Laura", "Pauline", "Margot"]
FIRST_NAMES_M = ["Thomas", "Paul", "Lucas", "Nicolas", "Antoine", "Julien", "Pierre",
                 "François", "David", "Romain", "Stéphane", "Maxime", "Alexis", "Baptiste", "Hugo"]
LAST_NAMES = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand",
              "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel", "Garcia",
              "David", "Bertrand", "Roux", "Vincent", "Fournier",
              "Morel", "Girard", "André", "Lefèvre", "Mercier", "Dupont", "Lambert",
              "Bonnet", "François", "Martinez"]


def random_barcode() -> str:
    return "VTZ" + str(rng.randint(100000, 999999))


def random_date(days_ago_max: int, days_ago_min: int = 0) -> datetime:
    delta = rng.randint(days_ago_min, days_ago_max)
    return datetime.now(timezone.utc) - timedelta(days=delta)


# ---------------------------------------------------------------------------
# Base seed functions (unchanged)
# ---------------------------------------------------------------------------

async def seed_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.username == "admin"))
    existing = result.scalar_one_or_none()
    if existing:
        print("[skip] Manager user 'admin' already exists.")
        return existing
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
    return user


async def seed_categories(db: AsyncSession) -> list[Category]:
    result = await db.execute(select(Category).limit(1))
    if result.scalar_one_or_none():
        print("[skip] Categories already exist.")
        result = await db.execute(select(Category))
        return list(result.scalars().all())

    categories: list[Category] = []

    enfants_types = ["Pantalon / Jean", "Haut (T-shirt, Pull, Sweat)", "Robe / Jupe",
                     "Manteau / Veste", "Ensemble / Combinaison", "Accessoire", "Chaussures"]
    for name in enfants_types:
        cat = Category(name=name, gender=Gender.enfant)
        db.add(cat)
        categories.append(cat)

    femme_types = ["Pantalon / Jean", "Haut (T-shirt, Blouse, Pull)", "Robe",
                   "Jupe", "Manteau / Veste", "Accessoire", "Chaussures", "Sac"]
    for name in femme_types:
        cat = Category(name=name, gender=Gender.femme)
        db.add(cat)
        categories.append(cat)

    homme_types = ["Pantalon / Jean", "Haut (T-shirt, Chemise, Pull)",
                   "Manteau / Veste", "Accessoire", "Chaussures"]
    for name in homme_types:
        cat = Category(name=name, gender=Gender.homme)
        db.add(cat)
        categories.append(cat)

    await db.flush()
    print(f"[done] Created {len(categories)} categories.")
    return categories


async def seed_price_grids(db: AsyncSession, categories: list[Category]) -> None:
    result = await db.execute(select(PriceGrid).limit(1))
    if result.scalar_one_or_none():
        print("[skip] Price grids already exist.")
        return
    brackets = [(0.00, 2.00, 5.00), (2.01, 5.00, 10.00), (5.01, 10.00, 19.00),
                (10.01, 20.00, 29.00), (20.01, 40.00, 49.00), (40.01, 80.00, 79.00),
                (80.01, 150.00, 119.00)]
    count = 0
    for cat in categories:
        for min_p, max_p, sale_p in brackets:
            db.add(PriceGrid(category_id=cat.id, min_purchase=min_p,
                             max_purchase=max_p, sale_price=sale_p))
            count += 1
    await db.flush()
    print(f"[done] Created {count} price grid entries.")


async def seed_supplier(db: AsyncSession) -> None:
    result = await db.execute(select(Supplier).where(Supplier.name == "Frip and Co"))
    if result.scalar_one_or_none():
        print("[skip] Supplier 'Frip and Co' already exists.")
        return
    db.add(Supplier(name="Frip and Co", contact_name="Contact Frip and Co",
                    email="contact@fripandco.fr", phone="02 32 00 00 00",
                    address="France", notes="Fournisseur principal de fripe"))
    await db.flush()
    print("[done] Created supplier: Frip and Co")


async def seed_store_zones(db: AsyncSession) -> list[StoreZone]:
    result = await db.execute(select(StoreZone).limit(1))
    if result.scalar_one_or_none():
        print("[skip] Store zones already exist.")
        result = await db.execute(select(StoreZone))
        return list(result.scalars().all())

    zones_data = [
        ("Vitrine gauche", "Zone vitrine avant gauche", 15, '["Robe", "Haut femme", "Accessoire"]', "#E8F4F8"),
        ("Podium entree", "Podium d'entrée avec les nouvelles arrivées", 20, '["Tout type"]', "#F0E8F8"),
        ("Mur gauche", "Mur gauche — hauts et robes", 60, '["Haut femme", "Robe", "Jupe"]', "#E8F8EC"),
        ("Mur droit / Caisse", "Zone caisse et accessoires", 30, '["Accessoire", "Sac", "Chaussures"]', "#F8F0E8"),
        ("Zone centrale", "Portants centraux — mixte", 80, '["Manteau", "Veste", "Pantalon"]', "#F8E8E8"),
        ("Mur fond", "Mur du fond — hommes et enfants", 60, '["Homme", "Enfant"]', "#E8EAF8"),
        ("Cabine essayage", "Espace cabines d'essayage", 5, '["Réservé essayage"]', "#F5F5F5"),
    ]

    result_zones = []
    for name, desc, cap, ptypes, color in zones_data:
        zone = StoreZone(name=name, description=desc, capacity=cap,
                         product_types=ptypes, color_code=color)
        db.add(zone)
        result_zones.append(zone)
        print(f"  [+] Zone: {name}")

    await db.flush()
    print(f"[done] Created {len(result_zones)} store zones.")
    return result_zones


# ---------------------------------------------------------------------------
# Clients seed (50 clients)
# ---------------------------------------------------------------------------

async def seed_clients(db: AsyncSession) -> list[Client]:
    result = await db.execute(select(Client).limit(1))
    if result.scalar_one_or_none():
        print("[skip] Clients already exist.")
        result = await db.execute(select(Client))
        return list(result.scalars().all())

    clients: list[Client] = []

    all_first_names = FIRST_NAMES_F + FIRST_NAMES_M
    all_first_names_shuffled = all_first_names.copy()
    rng.shuffle(all_first_names_shuffled)
    last_names_shuffled = LAST_NAMES.copy()
    rng.shuffle(last_names_shuffled)

    for i in range(50):
        first_name = all_first_names_shuffled[i % len(all_first_names_shuffled)]
        last_name = last_names_shuffled[i % len(last_names_shuffled)]
        email = f"{first_name.lower().replace('é', 'e').replace('è', 'e').replace('ê', 'e').replace('ç', 'c')}.{last_name.lower().replace(' ', '-')}{i}@email.fr"
        has_phone = rng.random() > 0.3
        phone = f"06{rng.randint(10000000, 99999999)}" if has_phone else None

        client = Client(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            notes=rng.choice([None, None, None, "Cliente régulière", "Préfère les pièces colorées",
                               "Fan de marques françaises", "Taille S uniquement", "Budget max 30€"]),
        )
        db.add(client)
        clients.append(client)

    await db.flush()

    # Create loyalty accounts for 60% of clients
    loyalty_count = 0
    for client in clients:
        if rng.random() < 0.60:
            points = rng.randint(0, 350)
            if points >= 200:
                tier = "gold"
            elif points >= 100:
                tier = "silver"
            else:
                tier = "bronze"
            acc = LoyaltyAccount(client_id=client.id, points=points, tier=tier)
            db.add(acc)
            loyalty_count += 1

    await db.flush()
    print(f"[done] Created 50 clients ({loyalty_count} with loyalty).")
    return clients


# ---------------------------------------------------------------------------
# Products seed (300 products)
# ---------------------------------------------------------------------------

def _product_name(cat_name: str, brand: str, color: str) -> str:
    cat_short = (cat_name.split(" / ")[0].split(" (")[0].split(" -")[0]).strip()
    return f"{cat_short} {brand} — {color}"


async def seed_products(
    db: AsyncSession,
    categories: list[Category],
    zones: list[StoreZone],
    target: int = 300,
) -> list[Product]:
    result = await db.execute(select(func.count(Product.id)))
    count = result.scalar_one() or 0
    if count >= target:
        print(f"[skip] Products already exist ({count} products).")
        result = await db.execute(select(Product))
        return list(result.scalars().all())

    existing = count
    to_create = target - existing
    print(f"[info] Creating {to_create} products (currently {existing})...")

    enfant_cats = [c for c in categories if c.gender == Gender.enfant]
    femme_cats = [c for c in categories if c.gender == Gender.femme]
    homme_cats = [c for c in categories if c.gender == Gender.homme]

    # Zone assignment weights
    zone_map = {z.name: z for z in zones}
    zone_names = [z.name for z in zones if z.name != "Cabine essayage"]

    products: list[Product] = []
    status_weights = [
        (ProductStatus.stock, 0.40),
        (ProductStatus.display, 0.30),
        (ProductStatus.sold, 0.25),
        (ProductStatus.returned, 0.05),
    ]

    for i in range(to_create):
        # Pick gender / category
        gender_choice = rng.choices(["femme", "homme", "enfant"], weights=[0.55, 0.25, 0.20])[0]
        if gender_choice == "femme":
            cat = rng.choice(femme_cats)
            colors = COLORS_FEMME
            sizes = SIZES_FEMME
            brands = rng.choices([BRANDS_PREMIUM, BRANDS_STANDARD, BRANDS_SPORTSWEAR],
                                  weights=[0.30, 0.50, 0.20])[0]
            brand = rng.choice(brands)
            purchase_min, purchase_max = (5, 40) if brand in BRANDS_STANDARD else (10, 80)
        elif gender_choice == "homme":
            cat = rng.choice(homme_cats)
            colors = COLORS_HOMME
            sizes = SIZES_HOMME
            brands = rng.choices([BRANDS_STANDARD, BRANDS_SPORTSWEAR, BRANDS_PREMIUM],
                                  weights=[0.45, 0.35, 0.20])[0]
            brand = rng.choice(brands)
            purchase_min, purchase_max = (5, 50)
        else:
            cat = rng.choice(enfant_cats)
            colors = COLORS_KIDS
            sizes = SIZES_KIDS
            brand = rng.choice(BRANDS_KIDS)
            purchase_min, purchase_max = (2, 20)

        color = rng.choice(colors)
        size = rng.choice(sizes)
        condition = rng.choices(CONDITIONS, weights=CONDITION_WEIGHTS)[0]

        # Pricing
        purchase_price = round(rng.uniform(purchase_min, purchase_max), 2)
        # Sale price: typically 2.5x-4x purchase for premium, 2x-3x for standard
        multiplier = rng.uniform(2.2, 4.5) if brand in BRANDS_PREMIUM else rng.uniform(1.8, 3.5)
        sale_price = round(purchase_price * multiplier, 2)
        # Round to .00 or .50 or .99
        sale_price = round(sale_price / 0.5) * 0.5

        # Score
        trend_score = None
        if rng.random() > 0.15:  # 85% have a score
            base_score = rng.randint(20, 95)
            # Premium brands get higher scores
            if brand in BRANDS_PREMIUM:
                base_score = min(100, base_score + rng.randint(5, 20))
            trend_score = base_score

        # Status with shelf date
        status = rng.choices(
            [s for s, _ in status_weights],
            weights=[w for _, w in status_weights]
        )[0]

        shelf_days_ago = rng.randint(1, 180)
        shelf_date = random_date(shelf_days_ago, shelf_days_ago)

        # Zone assignment
        zone = None
        if status in (ProductStatus.stock, ProductStatus.display) and zone_names:
            zone_name = rng.choice(zone_names)
            zone = zone_map.get(zone_name)

        name = _product_name(cat.name, brand, color)

        product = Product(
            barcode=random_barcode(),
            name=name,
            category_id=cat.id,
            brand=brand,
            color=color,
            size=size,
            condition=condition,
            purchase_price=purchase_price,
            sale_price=sale_price,
            status=status,
            trend_score=trend_score,
            shelf_date=shelf_date,
            zone_id=zone.id if zone else None,
            description=f"{condition} — {color} — {size}",
        )
        db.add(product)
        products.append(product)

    await db.flush()
    print(f"[done] Created {len(products)} products.")
    return products


# ---------------------------------------------------------------------------
# Transactions seed (realistic 12-month history)
# ---------------------------------------------------------------------------

async def seed_transactions(
    db: AsyncSession,
    user: User,
    clients: list[Client],
    products: list[Product],
    target_count: int = 200,
) -> None:
    result = await db.execute(select(func.count(Transaction.id)))
    tx_count = result.scalar_one() or 0
    if tx_count >= 50:
        print(f"[skip] Transactions already exist ({tx_count}).")
        return

    print(f"[info] Creating {target_count} transactions over 12 months...")

    # Get max transaction number
    max_num_result = await db.execute(
        select(func.coalesce(func.max(Transaction.transaction_number), 0))
    )
    next_number = max_num_result.scalar_one() + 1

    # Only use sold products for transaction items
    sold_products = [p for p in products if p.status == ProductStatus.sold]
    # Also use stock products (simulate sold without changing status)
    available_for_history = sold_products + [p for p in products
                                              if p.status in (ProductStatus.stock, ProductStatus.display)]

    if not available_for_history:
        print("[skip] No products available for transactions.")
        return

    created = 0
    for i in range(target_count):
        # Date spread over 12 months (more recent = more transactions)
        if rng.random() < 0.4:
            tx_date = random_date(30, 1)  # last 30 days
        elif rng.random() < 0.6:
            tx_date = random_date(90, 31)  # 1-3 months ago
        else:
            tx_date = random_date(365, 90)  # 3-12 months ago

        client = rng.choice(clients) if rng.random() < 0.55 else None

        # 1-3 items per transaction
        num_items = rng.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
        item_products = rng.sample(available_for_history, min(num_items, len(available_for_history)))

        total_ttc = 0.0
        for prod in item_products:
            discount = rng.choices([0, 10, 20], weights=[0.75, 0.15, 0.10])[0]
            line_total = round(float(prod.sale_price) * (1 - discount / 100), 2)
            total_ttc += line_total

        total_ttc = round(total_ttc, 2)
        total_ht = round(total_ttc / 1.20, 2)
        total_tva = round(total_ttc - total_ht, 2)

        # Payment method
        method = rng.choices(
            [PaymentMethod.cash, PaymentMethod.card, PaymentMethod.cheque],
            weights=[0.45, 0.48, 0.07]
        )[0]

        import hashlib
        tx = Transaction(
            transaction_number=next_number,
            transaction_type=TransactionType.sale,
            user_id=user.id,
            client_id=client.id if client else None,
            total_ht=total_ht,
            total_tva=total_tva,
            total_ttc=total_ttc,
            hash_chain=hashlib.sha256(f"{next_number}{total_ttc}".encode()).hexdigest(),
            created_at=tx_date,
        )
        db.add(tx)
        await db.flush()

        for prod in item_products:
            discount = rng.choices([0, 10, 20], weights=[0.75, 0.15, 0.10])[0]
            line_total = round(float(prod.sale_price) * (1 - discount / 100), 2)
            item = TransactionItem(
                transaction_id=tx.id,
                product_id=prod.id,
                quantity=1,
                unit_price=float(prod.sale_price),
                discount_percent=float(discount),
                line_total=line_total,
            )
            db.add(item)

        payment = Payment(
            transaction_id=tx.id,
            method=method,
            amount=total_ttc,
            created_at=tx_date,
        )
        db.add(payment)

        next_number += 1
        created += 1

    await db.flush()
    print(f"[done] Created {created} transactions.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    print("=" * 55)
    print("  Vintiz V2 — Extended Seed Data (300 products / 50 clients)")
    print("=" * 55)
    print()

    async with async_session() as db:
        try:
            user = await seed_user(db)
            categories = await seed_categories(db)
            await seed_price_grids(db, categories)
            await seed_supplier(db)
            zones = await seed_store_zones(db)
            clients = await seed_clients(db)
            products = await seed_products(db, categories, zones, target=300)
            await seed_transactions(db, user, clients, products, target_count=200)
            await db.commit()
            print()
            print("All seed data created successfully!")
            print(f"  → Login: admin / vintiz2026")
        except Exception as e:
            await db.rollback()
            print(f"\nError during seeding: {e}")
            import traceback
            traceback.print_exc()
            raise

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
