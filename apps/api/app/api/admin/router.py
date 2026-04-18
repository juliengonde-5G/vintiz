import asyncio
import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, List

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.security import RoleChecker, get_current_user, hash_password
from app.models.base import Base
from app.models.client import Client, LoyaltyAccount, LoyaltyTransaction, LoyaltyTxType
from app.models.inventory import Supplier
from app.models.pos import (
    CashDrawer,
    Payment,
    PaymentMethod,
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.models.product import Category, Gender, PriceGrid, Product, ProductStatus
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

    # --- Store zones (aligned with ai_mapping DEFAULT_ZONES + floor plan) ---
    from app.services.ai_mapping import DEFAULT_ZONES
    zone_result = await db.execute(select(StoreZone).limit(1))
    if zone_result.scalar_one_or_none():
        messages.append("[skip] Store zones already exist.")
    else:
        for zone_data in DEFAULT_ZONES:
            db.add(StoreZone(**zone_data))
        await db.flush()
        messages.append(f"[done] Created {len(DEFAULT_ZONES)} store zones.")

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


# ---------------------------------------------------------------------------
# Test data generation
# ---------------------------------------------------------------------------

# Realistic product catalog for a seconde main premium boutique
TEST_PRODUCTS = [
    # Robes
    {"name": "Robe midi fleurie Sandro", "brand": "Sandro", "color": "Rose", "size": "36", "purchase": 18, "sale": 49, "gender": "femme", "cat_kw": "Robe"},
    {"name": "Robe noire Claudie Pierlot", "brand": "Claudie Pierlot", "color": "Noir", "size": "38", "purchase": 22, "sale": 59, "gender": "femme", "cat_kw": "Robe"},
    {"name": "Robe chemise Ba&sh", "brand": "Ba&sh", "color": "Bleu marine", "size": "S", "purchase": 15, "sale": 45, "gender": "femme", "cat_kw": "Robe"},
    {"name": "Robe longue Maje kaki", "brand": "Maje", "color": "Kaki", "size": "40", "purchase": 25, "sale": 65, "gender": "femme", "cat_kw": "Robe"},
    {"name": "Robe de soiree Zadig & Voltaire", "brand": "Zadig & Voltaire", "color": "Noir", "size": "36", "purchase": 30, "sale": 79, "gender": "femme", "cat_kw": "Robe"},
    {"name": "Robe ete COS lin", "brand": "COS", "color": "Beige", "size": "M", "purchase": 12, "sale": 35, "gender": "femme", "cat_kw": "Robe"},
    # Hauts
    {"name": "Blouse soie Isabel Marant", "brand": "Isabel Marant", "color": "Ivoire", "size": "38", "purchase": 28, "sale": 69, "gender": "femme", "cat_kw": "Haut"},
    {"name": "Pull cachemire Comptoir", "brand": "Comptoir des Cotonniers", "color": "Gris", "size": "M", "purchase": 20, "sale": 55, "gender": "femme", "cat_kw": "Haut"},
    {"name": "T-shirt IRO noir destroy", "brand": "IRO", "color": "Noir", "size": "S", "purchase": 10, "sale": 29, "gender": "femme", "cat_kw": "Haut"},
    {"name": "Chemisier Sandro imprime", "brand": "Sandro", "color": "Multicolore", "size": "36", "purchase": 16, "sale": 45, "gender": "femme", "cat_kw": "Haut"},
    {"name": "Pull col roule The Kooples", "brand": "The Kooples", "color": "Noir", "size": "M", "purchase": 18, "sale": 49, "gender": "femme", "cat_kw": "Haut"},
    {"name": "Top dentelle Maje", "brand": "Maje", "color": "Blanc", "size": "38", "purchase": 14, "sale": 39, "gender": "femme", "cat_kw": "Haut"},
    {"name": "Sweat American Vintage", "brand": "American Vintage", "color": "Rose pale", "size": "L", "purchase": 8, "sale": 25, "gender": "femme", "cat_kw": "Haut"},
    # Pantalons
    {"name": "Jean slim Sandro brut", "brand": "Sandro", "color": "Bleu brut", "size": "38", "purchase": 15, "sale": 39, "gender": "femme", "cat_kw": "Pantalon"},
    {"name": "Pantalon large Maje noir", "brand": "Maje", "color": "Noir", "size": "36", "purchase": 20, "sale": 49, "gender": "femme", "cat_kw": "Pantalon"},
    {"name": "Jean mom COS delave", "brand": "COS", "color": "Bleu clair", "size": "40", "purchase": 10, "sale": 29, "gender": "femme", "cat_kw": "Pantalon"},
    {"name": "Pantalon tailleur Ba&sh", "brand": "Ba&sh", "color": "Marine", "size": "38", "purchase": 18, "sale": 45, "gender": "femme", "cat_kw": "Pantalon"},
    # Jupes
    {"name": "Jupe plissee Claudie Pierlot", "brand": "Claudie Pierlot", "color": "Bordeaux", "size": "36", "purchase": 16, "sale": 42, "gender": "femme", "cat_kw": "Jupe"},
    {"name": "Jupe cuir Maje", "brand": "Maje", "color": "Noir", "size": "38", "purchase": 25, "sale": 59, "gender": "femme", "cat_kw": "Jupe"},
    # Manteaux & Vestes
    {"name": "Blazer oversize Isabel Marant", "brand": "Isabel Marant", "color": "Noir", "size": "38", "purchase": 40, "sale": 89, "gender": "femme", "cat_kw": "Manteau"},
    {"name": "Trench Comptoir des Cotonniers", "brand": "Comptoir des Cotonniers", "color": "Beige", "size": "40", "purchase": 30, "sale": 69, "gender": "femme", "cat_kw": "Manteau"},
    {"name": "Veste en jean Zadig & Voltaire", "brand": "Zadig & Voltaire", "color": "Bleu", "size": "S", "purchase": 22, "sale": 55, "gender": "femme", "cat_kw": "Manteau"},
    {"name": "Manteau laine The Kooples", "brand": "The Kooples", "color": "Camel", "size": "M", "purchase": 45, "sale": 99, "gender": "femme", "cat_kw": "Manteau"},
    {"name": "Perfecto cuir Sandro", "brand": "Sandro", "color": "Noir", "size": "36", "purchase": 55, "sale": 129, "gender": "femme", "cat_kw": "Manteau"},
    # Accessoires
    {"name": "Sac bandouliere Vanessa Bruno", "brand": "Vanessa Bruno", "color": "Camel", "size": "TU", "purchase": 20, "sale": 49, "gender": "femme", "cat_kw": "Sac"},
    {"name": "Cabas lin Vanessa Bruno", "brand": "Vanessa Bruno", "color": "Bleu", "size": "TU", "purchase": 15, "sale": 39, "gender": "femme", "cat_kw": "Sac"},
    {"name": "Ceinture cuir Gerard Darel", "brand": "Gerard Darel", "color": "Marron", "size": "85", "purchase": 8, "sale": 22, "gender": "femme", "cat_kw": "Accessoire"},
    {"name": "Echarpe laine Sandro", "brand": "Sandro", "color": "Gris", "size": "TU", "purchase": 10, "sale": 29, "gender": "femme", "cat_kw": "Accessoire"},
    # Chaussures
    {"name": "Bottines cuir Sandro", "brand": "Sandro", "color": "Noir", "size": "38", "purchase": 25, "sale": 65, "gender": "femme", "cat_kw": "Chaussures"},
    {"name": "Escarpins Claudie Pierlot", "brand": "Claudie Pierlot", "color": "Nude", "size": "37", "purchase": 18, "sale": 45, "gender": "femme", "cat_kw": "Chaussures"},
    {"name": "Baskets Veja", "brand": "Veja", "color": "Blanc", "size": "39", "purchase": 20, "sale": 49, "gender": "femme", "cat_kw": "Chaussures"},
    # Homme
    {"name": "Chemise Oxford Massimo Dutti", "brand": "Massimo Dutti", "color": "Bleu ciel", "size": "L", "purchase": 10, "sale": 29, "gender": "homme", "cat_kw": "Haut"},
    {"name": "Pull merinos COS", "brand": "COS", "color": "Marine", "size": "M", "purchase": 12, "sale": 35, "gender": "homme", "cat_kw": "Haut"},
    {"name": "Jean Sandro homme", "brand": "Sandro", "color": "Noir", "size": "42", "purchase": 15, "sale": 39, "gender": "homme", "cat_kw": "Pantalon"},
    {"name": "Blouson cuir The Kooples", "brand": "The Kooples", "color": "Noir", "size": "L", "purchase": 50, "sale": 119, "gender": "homme", "cat_kw": "Manteau"},
    # Enfant
    {"name": "Robe Liberty Bonpoint", "brand": "Bonpoint", "color": "Floral", "size": "6A", "purchase": 12, "sale": 29, "gender": "enfant", "cat_kw": "Robe"},
    {"name": "Jean Petit Bateau", "brand": "Petit Bateau", "color": "Bleu", "size": "8A", "purchase": 5, "sale": 15, "gender": "enfant", "cat_kw": "Pantalon"},
    {"name": "Pull Jacadi laine", "brand": "Jacadi", "color": "Gris", "size": "10A", "purchase": 8, "sale": 22, "gender": "enfant", "cat_kw": "Haut"},
]

TEST_CLIENTS = [
    {"first_name": "Marie", "last_name": "Dupont", "email": "marie.dupont@email.fr", "phone": "06 12 34 56 78", "notes": "Vernon"},
    {"first_name": "Sophie", "last_name": "Martin", "email": "sophie.martin@email.fr", "phone": "06 23 45 67 89", "notes": "Vernon - cliente reguliere"},
    {"first_name": "Isabelle", "last_name": "Bernard", "email": "isabelle.bernard@email.fr", "phone": "06 34 56 78 90", "notes": "Giverny"},
    {"first_name": "Claire", "last_name": "Petit", "email": "claire.petit@email.fr", "phone": "06 45 67 89 01", "notes": "Vernon centre"},
    {"first_name": "Nathalie", "last_name": "Robert", "email": "nathalie.robert@email.fr", "phone": "06 56 78 90 12", "notes": "Pacy-sur-Eure"},
    {"first_name": "Valerie", "last_name": "Moreau", "email": "valerie.moreau@email.fr", "phone": "06 67 89 01 23", "notes": "Vernon - VIP"},
    {"first_name": "Catherine", "last_name": "Leroy", "email": "catherine.leroy@email.fr", "phone": "06 78 90 12 34", "notes": "Les Andelys"},
    {"first_name": "Sandrine", "last_name": "Simon", "email": "sandrine.simon@email.fr", "phone": "06 89 01 23 45", "notes": "Evreux"},
    {"first_name": "Christine", "last_name": "Laurent", "email": "christine.laurent@email.fr", "phone": "06 90 12 34 56", "notes": "Vernon"},
    {"first_name": "Pauline", "last_name": "Garcia", "email": "pauline.garcia@email.fr", "phone": "07 01 23 45 67", "notes": "Gaillon"},
    {"first_name": "Emilie", "last_name": "Fournier", "email": "emilie.fournier@email.fr", "phone": "07 12 34 56 78", "notes": "Vernon - nouvelle cliente"},
    {"first_name": "Audrey", "last_name": "Girard", "email": "audrey.girard@email.fr", "phone": "07 23 45 67 89", "notes": "Bizy"},
]


@router.post("/test-data")
async def generate_test_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(manager_only),
):
    """Generate realistic test data: products, clients, loyalty, transactions."""
    import traceback as tb

    try:
        return await _generate_test_data_impl(db)
    except Exception as e:
        await db.rollback()
        error_detail = tb.format_exc()
        logger = __import__("logging").getLogger("vintiz.admin")
        logger.error("test-data failed: %s", error_detail)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur generation donnees: {type(e).__name__}: {str(e)}",
        )


async def _generate_test_data_impl(db: AsyncSession):
    """Internal implementation of test data generation."""
    messages: list[str] = []
    now = datetime.now(timezone.utc)

    # 1. Ensure categories exist
    cat_result = await db.execute(select(Category))
    all_cats = {(c.gender.value, c.name): c for c in cat_result.scalars().all()}
    if not all_cats:
        return {"status": "error", "message": "Lancez d'abord /api/admin/seed pour creer les categories"}

    # Helper to find best matching category
    def find_category(gender: str, keyword: str) -> Category | None:
        for (g, name), cat in all_cats.items():
            if g == gender and keyword.lower() in name.lower():
                return cat
        # Fallback: first category of that gender
        for (g, _), cat in all_cats.items():
            if g == gender:
                return cat
        return None

    # 2. Get admin user for transactions
    admin_result = await db.execute(select(User).where(User.username == "admin"))
    admin_user = admin_result.scalar_one_or_none()
    if not admin_user:
        return {"status": "error", "message": "Utilisateur admin introuvable"}

    # 3. Check if test data already exists
    prod_count_result = await db.execute(select(func.count(Product.id)))
    existing_products = prod_count_result.scalar_one()
    if existing_products >= 30:
        return {
            "status": "skip",
            "message": f"Deja {existing_products} produits en base. Supprimez les donnees avant de regenerer.",
        }

    # 4. Create products with varied dates (simulating 6 weeks of activity)
    created_products: list[Product] = []
    week_num = now.isocalendar()[1]

    for i, p_data in enumerate(TEST_PRODUCTS):
        cat = find_category(p_data["gender"], p_data["cat_kw"])
        if not cat:
            continue

        # Spread creation dates over last 6 weeks
        days_ago = random.randint(0, 42)
        created_at = now - timedelta(days=days_ago, hours=random.randint(0, 12))

        # Generate barcode: VTZ-SEMXX-XXXX
        product_week = (now - timedelta(days=days_ago)).isocalendar()[1]
        barcode = f"VTZ-S{product_week:02d}-{i+1:04d}"

        product = Product(
            barcode=barcode,
            name=p_data["name"],
            category_id=cat.id,
            size=p_data["size"],
            color=p_data["color"],
            brand=p_data["brand"],
            purchase_price=p_data["purchase"],
            sale_price=p_data["sale"],
            status=ProductStatus.stock,
            week_number=product_week,
        )
        # Manually set created_at for varied dates
        product.created_at = created_at
        product.updated_at = created_at
        db.add(product)
        await db.flush()
        await db.refresh(product)
        created_products.append(product)

    messages.append(f"[done] {len(created_products)} produits crees")

    # 5. Set some products as "display" and assign zone_ids
    zone_result = await db.execute(select(StoreZone))
    zones = zone_result.scalars().all()
    if zones:
        display_products = random.sample(
            created_products, min(15, len(created_products))
        )
        for p in display_products:
            p.status = ProductStatus.display
            p.zone_id = random.choice(zones).id
        await db.flush()
        messages.append(f"[done] {len(display_products)} produits en vitrine")

    # 6. Create clients
    created_clients: list[Client] = []
    for c_data in TEST_CLIENTS:
        # Check if email already exists
        existing = await db.execute(
            select(Client).where(Client.email == c_data["email"])
        )
        if existing.scalar_one_or_none():
            continue

        client = Client(**c_data)
        days_ago = random.randint(1, 60)
        client.created_at = now - timedelta(days=days_ago)
        client.updated_at = client.created_at
        db.add(client)
        await db.flush()
        await db.refresh(client)
        created_clients.append(client)

    messages.append(f"[done] {len(created_clients)} clients crees")

    # 7. Activate loyalty for 8 clients
    loyalty_clients = created_clients[:8] if len(created_clients) >= 8 else created_clients
    for i, client in enumerate(loyalty_clients):
        tier = "gold" if i < 2 else ("silver" if i < 5 else "bronze")
        base_points = {"gold": 450, "silver": 200, "bronze": 50}[tier]
        points = base_points + random.randint(-20, 80)

        account = LoyaltyAccount(
            client_id=client.id,
            points=points,
            tier=tier,
        )
        db.add(account)
        await db.flush()
        await db.refresh(account)

        # Add some loyalty history
        earned = points + random.randint(20, 100)
        lt_earn = LoyaltyTransaction(
            account_id=account.id,
            tx_type=LoyaltyTxType.earn,
            points=earned,
            description="Achats cumules en boutique",
        )
        db.add(lt_earn)

        if earned > points:
            lt_redeem = LoyaltyTransaction(
                account_id=account.id,
                tx_type=LoyaltyTxType.redeem,
                points=earned - points,
                description="Bon de reduction utilise",
            )
            db.add(lt_redeem)

    await db.flush()
    messages.append(f"[done] {len(loyalty_clients)} comptes fidelite actives")

    # 8. Simulate transactions over the last 3 weeks
    # Pick some products to mark as "sold"
    available_for_sale = [p for p in created_products if p.status in (ProductStatus.stock, ProductStatus.display)]
    products_to_sell = random.sample(available_for_sale, min(18, len(available_for_sale)))

    # Get next transaction number
    max_tx_result = await db.execute(
        select(func.coalesce(func.max(Transaction.transaction_number), 0))
    )
    next_tx_num = max_tx_result.scalar_one() + 1

    previous_hash = "0"
    tx_count = 0
    total_revenue = 0.0

    for idx, product in enumerate(products_to_sell):
        # Each product = 1 transaction, spread over 3 weeks
        days_ago = random.randint(0, 21)
        tx_time = now - timedelta(days=days_ago, hours=random.randint(10, 18), minutes=random.randint(0, 59))

        # Some transactions have a client
        client_id = None
        if created_clients and random.random() < 0.6:
            client_id = random.choice(created_clients).id

        sale_price = float(product.sale_price)
        discount = random.choice([0, 0, 0, 5, 10, 15])  # Most have no discount
        if discount > 0:
            line_total = round(sale_price * (1 - discount / 100), 2)
        else:
            line_total = sale_price

        total_ht = round(line_total / 1.20, 2)
        total_tva = round(line_total - total_ht, 2)
        total_ttc = line_total

        tx = Transaction(
            transaction_number=next_tx_num + idx,
            transaction_type=TransactionType.sale,
            user_id=admin_user.id,
            client_id=client_id,
            total_ht=total_ht,
            total_tva=total_tva,
            total_ttc=total_ttc,
            hash_chain="pending",
        )
        tx.created_at = tx_time
        tx.updated_at = tx_time
        db.add(tx)
        await db.flush()
        await db.refresh(tx)

        # Hash chain
        hash_data = f"{tx.transaction_number}|{float(tx.total_ttc):.2f}|{tx.created_at.isoformat()}|{previous_hash}"
        tx.hash_chain = hashlib.sha256(hash_data.encode("utf-8")).hexdigest()
        previous_hash = tx.hash_chain

        # Transaction item
        item = TransactionItem(
            transaction_id=tx.id,
            product_id=product.id,
            quantity=1,
            unit_price=sale_price,
            discount_percent=discount,
            line_total=line_total,
        )
        db.add(item)

        # Payment (random method)
        method = random.choices(
            [PaymentMethod.card, PaymentMethod.cash, PaymentMethod.cheque],
            weights=[60, 30, 10],
        )[0]
        payment = Payment(
            transaction_id=tx.id,
            method=method,
            amount=total_ttc,
        )
        db.add(payment)

        # Mark product as sold
        product.status = ProductStatus.sold
        product.sold_at = tx_time.isoformat()

        tx_count += 1
        total_revenue += total_ttc

    await db.flush()
    messages.append(f"[done] {tx_count} transactions creees ({total_revenue:.2f} EUR)")

    # 9. Compute trend scores for remaining active products
    active = [p for p in created_products if p.status in (ProductStatus.stock, ProductStatus.display)]
    for p in active:
        ca = p.created_at
        if ca.tzinfo is None:
            ca = ca.replace(tzinfo=timezone.utc)
        days_old = (now - ca).days
        freshness = max(0, 25 - days_old)
        p.trend_score = round(random.uniform(20, 80) + freshness * 0.5, 1)
    await db.flush()
    messages.append(f"[done] Scores tendance calcules pour {len(active)} produits actifs")

    await db.commit()

    return {
        "status": "ok",
        "summary": {
            "products": len(created_products),
            "clients": len(created_clients),
            "loyalty_accounts": len(loyalty_clients),
            "transactions": tx_count,
            "revenue": round(total_revenue, 2),
        },
        "messages": messages,
    }


@router.post("/reset-data")
async def reset_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(manager_only),
):
    """Delete all test data (products, clients, transactions, zones) to allow re-seeding."""
    import traceback as tb

    try:
        return await _reset_data_impl(db)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur reset: {type(e).__name__}: {str(e)}",
        )


async def _reset_data_impl(db: AsyncSession):
    from app.models.store import AIRecommendation, StoreArrangement, ZoneProduct

    counts: dict[str, int] = {}

    # Order matters for FK constraints
    for model, label in [
        (Payment, "paiements"),
        (TransactionItem, "lignes transaction"),
        (Transaction, "transactions"),
        (LoyaltyTransaction, "transactions fidelite"),
        (LoyaltyAccount, "comptes fidelite"),
        (Client, "clients"),
        (AIRecommendation, "recommandations IA"),
        (StoreArrangement, "arrangements"),
        (ZoneProduct, "zone_products"),
        (Product, "produits"),
        (StoreZone, "zones"),
        (CashDrawer, "caisses"),
    ]:
        result = await db.execute(select(func.count()).select_from(model))
        count = result.scalar_one()
        if count > 0:
            await db.execute(model.__table__.delete())
            counts[label] = count

    await db.commit()

    return {
        "status": "ok",
        "message": "Donnees reinitialisees",
        "deleted": counts,
    }


# ---------------------------------------------------------------------------
# Weather endpoint
# ---------------------------------------------------------------------------

@router.get("/weather")
async def get_weather(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get current weather and forecast for Vernon. Saves snapshot to history."""
    from app.services.weather_service import get_current_weather, get_weather_forecast
    from app.models.audit import Settings

    current, forecast = await asyncio.gather(get_current_weather(), get_weather_forecast())

    # Save weather snapshot to history (stored in Settings as JSON array)
    import json as _json
    from datetime import date as _date

    weather_data = {"current": current, "forecast": forecast}

    try:
        # Load existing history
        history_setting = await db.execute(select(Settings).where(Settings.key == "weather_history"))
        setting = history_setting.scalar_one_or_none()

        today_str = str(_date.today())
        snapshot = {
            "date": today_str,
            "temp": current.get("temp", 0),
            "description": current.get("description", ""),
            "icon": current.get("icon", "01d"),
            "temp_min": current.get("temp_min", current.get("temp", 0)),
            "temp_max": current.get("temp_max", current.get("temp", 0)),
            "humidity": current.get("humidity", 0),
            "wind_speed": current.get("wind_speed", 0),
        }

        if setting:
            history = _json.loads(setting.value or "[]")
            # Update today's snapshot or append
            history = [h for h in history if h.get("date") != today_str]
            history.append(snapshot)
            # Keep last 30 days
            history = sorted(history, key=lambda x: x["date"])[-30:]
            setting.value = _json.dumps(history)
        else:
            db.add(Settings(key="weather_history", value=_json.dumps([snapshot])))

        await db.commit()
    except Exception:
        pass  # History storage is non-critical

    return weather_data


@router.get("/weather/history")
async def get_weather_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get historical weather snapshots for Vernon (last 30 days)."""
    import json as _json
    from app.models.audit import Settings

    setting_result = await db.execute(select(Settings).where(Settings.key == "weather_history"))
    setting = setting_result.scalar_one_or_none()

    if not setting or not setting.value:
        return {"history": []}

    try:
        history = _json.loads(setting.value)
        return {"history": history}
    except Exception:
        return {"history": []}


# ---------------------------------------------------------------------------
# Zones CRUD
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
    }
    if product_count is not None:
        out["product_count"] = product_count
    return out


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
                  "sales_target_monthly", "display_order"):
        if field in data:
            setattr(zone, field, data[field])
    if "product_types" in data and data["product_types"] is not None:
        zone.product_types = json.dumps(data["product_types"])

    await db.flush()
    await db.refresh(zone)
    await db.commit()
    return _serialize_zone(zone)


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

    # Active products in zone (stock or display)
    active_res = await db.execute(
        select(func.count(Product.id)).where(
            Product.zone_id == zone_id,
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
        )
    )
    active_count = active_res.scalar_one() or 0

    # Products sold from this zone in last 30 days
    sold_30 = await db.execute(
        select(
            func.count(TransactionItem.id),
            func.coalesce(func.sum(TransactionItem.price), 0),
        )
        .join(Product, Product.id == TransactionItem.product_id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Product.zone_id == zone_id,
            Transaction.created_at >= start_30,
            Transaction.type == TransactionType.sale,
        )
    )
    sold_count, sold_revenue = sold_30.one()

    # Previous 30 days (30 → 60) for delta
    sold_prev = await db.execute(
        select(
            func.count(TransactionItem.id),
            func.coalesce(func.sum(TransactionItem.price), 0),
        )
        .join(Product, Product.id == TransactionItem.product_id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Product.zone_id == zone_id,
            Transaction.created_at >= start_60,
            Transaction.created_at < start_30,
            Transaction.type == TransactionType.sale,
        )
    )
    prev_count, prev_revenue = sold_prev.one()

    # Top 5 products sold from zone
    top_res = await db.execute(
        select(
            Product.id,
            Product.name,
            Product.brand,
            func.count(TransactionItem.id).label("units"),
            func.coalesce(func.sum(TransactionItem.price), 0).label("revenue"),
        )
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(
            Product.zone_id == zone_id,
            Transaction.created_at >= start_30,
            Transaction.type == TransactionType.sale,
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

    # Alerts
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
    stale_cutoff = now - timedelta(days=60)
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

    # 30-day revenue sparkline (one value per day)
    spark: list[float] = []
    for day_offset in range(30, 0, -1):
        day_start = now - timedelta(days=day_offset)
        day_end = day_start + timedelta(days=1)
        day_res = await db.execute(
            select(func.coalesce(func.sum(TransactionItem.price), 0))
            .join(Transaction, Transaction.id == TransactionItem.transaction_id)
            .join(Product, Product.id == TransactionItem.product_id)
            .where(
                Product.zone_id == zone_id,
                Transaction.created_at >= day_start,
                Transaction.created_at < day_end,
                Transaction.type == TransactionType.sale,
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
# Monthly scoring automation
# ---------------------------------------------------------------------------

@router.post("/scoring/monthly-update")
async def monthly_scoring_update(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Recompute trend score for all active products. Triggered on the 1st Wednesday of each month."""
    from app.services.scoring_service import compute_score

    result = await db.execute(
        select(Product).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display])
        )
    )
    products = result.scalars().all()
    updated = 0
    for product in products:
        # Get category average price for context
        avg_result = await db.execute(
            select(func.avg(Product.sale_price)).where(Product.category_id == product.category_id)
        )
        avg_price = float(avg_result.scalar_one_or_none() or product.sale_price)

        score_data = compute_score(
            shelf_date=product.shelf_date,
            sale_price=float(product.sale_price),
            category_avg_price=avg_price,
            condition=getattr(product, "condition", "tres_bon") or "tres_bon",
            brand=product.brand,
            photo_url=product.photo_url,
        )
        product.trend_score = score_data["total_score"]
        updated += 1

    await db.commit()
    return {
        "updated": updated,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"Scores recalcules pour {updated} produits actifs",
    }


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

    # Unassign products from this zone
    products_result = await db.execute(
        select(Product).where(Product.zone_id == zone_id)
    )
    for product in products_result.scalars().all():
        product.zone_id = None
    await db.flush()

    await db.delete(zone)
    await db.flush()
    await db.commit()
