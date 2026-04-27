"""Admin seeding, table bootstrap, test-data generation, and data reset endpoints."""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.security import RoleChecker, hash_password
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

router = APIRouter(tags=["admin"])

manager_only = RoleChecker(["manager"])

# ---------------------------------------------------------------------------
# Seed endpoint
# ---------------------------------------------------------------------------


@router.post("/seed")
async def seed_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(manager_only),
):
    """Run seed logic: create admin user, categories, price grids, supplier, zones."""
    messages: list[str] = []

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


# ---------------------------------------------------------------------------
# Bootstrap endpoint (protected by dedicated header key)
# ---------------------------------------------------------------------------


@router.post("/create-tables")
async def create_tables(
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
):
    """Create all database tables. Protected by a dedicated X-Admin-Key header.

    Reads the expected key from the ADMIN_BOOTSTRAP_KEY environment variable.
    Refuses to run in production unless ADMIN_BOOTSTRAP_KEY is explicitly set
    (we no longer alias SECRET_KEY here, which would have allowed anyone with
    the JWT signing key to forge admin operations).
    """
    import hmac
    import os

    expected = os.getenv("ADMIN_BOOTSTRAP_KEY", "") or settings.ADMIN_BOOTSTRAP_KEY
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_BOOTSTRAP_KEY is not configured on the server.",
        )
    if not hmac.compare_digest(x_admin_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key",
        )

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
# Test data constants
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Test data generation
# ---------------------------------------------------------------------------


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

    cat_result = await db.execute(select(Category))
    all_cats = {(c.gender.value, c.name): c for c in cat_result.scalars().all()}
    if not all_cats:
        return {"status": "error", "message": "Lancez d'abord /api/admin/seed pour creer les categories"}

    def find_category(gender: str, keyword: str) -> Category | None:
        for (g, name), cat in all_cats.items():
            if g == gender and keyword.lower() in name.lower():
                return cat
        for (g, _), cat in all_cats.items():
            if g == gender:
                return cat
        return None

    admin_result = await db.execute(select(User).where(User.username == "admin"))
    admin_user = admin_result.scalar_one_or_none()
    if not admin_user:
        return {"status": "error", "message": "Utilisateur admin introuvable"}

    prod_count_result = await db.execute(select(func.count(Product.id)))
    existing_products = prod_count_result.scalar_one()
    if existing_products >= 30:
        return {
            "status": "skip",
            "message": f"Deja {existing_products} produits en base. Supprimez les donnees avant de regenerer.",
        }

    created_products: list[Product] = []

    for i, p_data in enumerate(TEST_PRODUCTS):
        cat = find_category(p_data["gender"], p_data["cat_kw"])
        if not cat:
            continue

        days_ago = random.randint(0, 42)
        created_at = now - timedelta(days=days_ago, hours=random.randint(0, 12))
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
        product.created_at = created_at
        product.updated_at = created_at
        db.add(product)
        await db.flush()
        await db.refresh(product)
        created_products.append(product)

    messages.append(f"[done] {len(created_products)} produits crees")

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

    created_clients: list[Client] = []
    for c_data in TEST_CLIENTS:
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

    available_for_sale = [p for p in created_products if p.status in (ProductStatus.stock, ProductStatus.display)]
    products_to_sell = random.sample(available_for_sale, min(18, len(available_for_sale)))

    max_tx_result = await db.execute(
        select(func.coalesce(func.max(Transaction.transaction_number), 0))
    )
    next_tx_num = max_tx_result.scalar_one() + 1

    previous_hash = "0"
    tx_count = 0
    total_revenue = 0.0

    for idx, product in enumerate(products_to_sell):
        days_ago = random.randint(0, 21)
        tx_time = now - timedelta(days=days_ago, hours=random.randint(10, 18), minutes=random.randint(0, 59))

        client_id = None
        if created_clients and random.random() < 0.6:
            client_id = random.choice(created_clients).id

        sale_price = float(product.sale_price)
        discount = random.choices([0, 0, 0, 5, 10, 15], weights=[60, 30, 10, 60, 30, 10])[0]
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

        hash_data = f"{tx.transaction_number}|{float(tx.total_ttc):.2f}|{tx.created_at.isoformat()}|{previous_hash}"
        tx.hash_chain = hashlib.sha256(hash_data.encode("utf-8")).hexdigest()
        previous_hash = tx.hash_chain

        item = TransactionItem(
            transaction_id=tx.id,
            product_id=product.id,
            quantity=1,
            unit_price=sale_price,
            discount_percent=discount,
            line_total=line_total,
        )
        db.add(item)

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

        product.status = ProductStatus.sold
        product.sold_at = tx_time

        tx_count += 1
        total_revenue += total_ttc

    await db.flush()
    messages.append(f"[done] {tx_count} transactions creees ({total_revenue:.2f} EUR)")

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


# ---------------------------------------------------------------------------
# Reset endpoint
# ---------------------------------------------------------------------------


@router.post("/reset-data")
async def reset_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(manager_only),
):
    """Delete all test data (products, clients, transactions, zones) to allow re-seeding."""
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
# Purge test data
# ---------------------------------------------------------------------------


class PurgeTestDataRequest(BaseModel):
    dry_run: bool = True


@router.post("/test-data/purge", dependencies=[Depends(manager_only)])
async def purge_test_data(
    payload: PurgeTestDataRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete every Product and Client row marked ``is_test=True``.

    The pre-opening real base (rows with the default ``is_test=False``) is
    untouched. Cascade through SQLAlchemy relationships removes attached
    photos, embeddings, transactions, taste profiles, consents.

    ``dry_run=True`` (default) returns the counts that *would* be deleted
    without actually deleting anything. Pass ``dry_run=False`` to commit.
    """
    product_count_q = await db.execute(
        select(func.count()).select_from(Product).where(Product.is_test.is_(True))
    )
    product_count = int(product_count_q.scalar() or 0)

    client_count_q = await db.execute(
        select(func.count()).select_from(Client).where(Client.is_test.is_(True))
    )
    client_count = int(client_count_q.scalar() or 0)

    if payload.dry_run:
        return {
            "dry_run": True,
            "would_delete": {
                "products": product_count,
                "clients": client_count,
            },
        }

    products_res = await db.execute(
        select(Product).where(Product.is_test.is_(True))
    )
    for prod in products_res.scalars().all():
        await db.delete(prod)

    clients_res = await db.execute(
        select(Client).where(Client.is_test.is_(True))
    )
    for cli in clients_res.scalars().all():
        await db.delete(cli)

    await db.commit()

    return {
        "dry_run": False,
        "deleted": {
            "products": product_count,
            "clients": client_count,
        },
    }
