"""Public storefront endpoints (no auth) for the vintiz.fr site.

Sister of ``app.api.inventory`` mais sans authentification : sert le
catalogue physiquement en boutique (statuts ``FLOOR_STATUSES``) pour le
site vitrine Next.js (``apps/site``).

Sortis dans un sous-router séparé :
- pas d'auth → on garde une frontière claire ; l'inventaire admin reste
  derrière JWT
- pas de pagination ORM-lourde — un boutique a typiquement 200-400
  pièces actives ; on renvoie l'intégralité (cached côté Next ISR)
- on n'expose **que** ce qu'on veut voir publié : pas de prix d'achat,
  pas de codes fiscaux, pas de notes manager

Le ``slug`` utilisé par les URLs du site (``/produits/<slug>``) est le
code-barres : il est unique, stable, et n'expose pas d'identifiant
métier interne (UUID). Si on veut un slug plus joli plus tard (« robe-
sandro-noire-…-VTZ12345 »), il suffit d'extraire le suffixe.
"""
from __future__ import annotations

import unicodedata
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.store import StoreZone

router = APIRouter(prefix="/storefront", tags=["storefront"])


# Statuts visibles publiquement : tout ce qui est physiquement sur le
# rayon. Mirror exact de ``api.inventory.FLOOR_STATUSES`` — dupliqué pour
# éviter une dépendance croisée (le module storefront veut zéro lien
# avec le router admin).
FLOOR_STATUSES = {
    ProductStatus.display,
    ProductStatus.displayed,
    ProductStatus.discounted,
    ProductStatus.deep_discounted,
}


# Mapping catégorie BD → catégorie publique (le site groupe sur 9
# familles éditoriales ; la BD peut avoir 30+ catégories fines selon le
# manager). On normalise en minuscules sans accents pour le matching.
_PUBLIC_CATEGORIES: dict[str, str] = {
    "robe": "robe",
    "robes": "robe",
    "veste": "veste",
    "vestes": "veste",
    "blazer": "veste",
    "manteau": "veste",
    "manteaux": "veste",
    "pantalon": "pantalon",
    "pantalons": "pantalon",
    "jean": "pantalon",
    "jeans": "pantalon",
    "pull": "pull",
    "pulls": "pull",
    "sweat": "pull",
    "sweatshirt": "pull",
    "cardigan": "pull",
    "chemise": "chemise",
    "chemises": "chemise",
    "blouse": "chemise",
    "top": "chemise",
    "jupe": "jupe",
    "jupes": "jupe",
    "chaussure": "chaussures",
    "chaussures": "chaussures",
    "bottes": "chaussures",
    "bottines": "chaussures",
    "baskets": "chaussures",
    "sneakers": "chaussures",
    "escarpins": "chaussures",
    "mocassins": "chaussures",
    "sandales": "chaussures",
    "ballerines": "chaussures",
    "sac": "sac",
    "sacs": "sac",
    "sac a main": "sac",
    "pochette": "sac",
    "accessoire": "accessoire",
    "accessoires": "accessoire",
    "foulard": "accessoire",
    "echarpe": "accessoire",
    "ceinture": "accessoire",
    "bijou": "accessoire",
    "bijoux": "accessoire",
}

PUBLIC_CATEGORY_LABELS: dict[str, str] = {
    "robe": "Robes",
    "veste": "Vestes",
    "pantalon": "Pantalons",
    "pull": "Pulls",
    "chemise": "Chemises",
    "jupe": "Jupes",
    "chaussures": "Chaussures",
    "sac": "Sacs",
    "accessoire": "Accessoires",
}


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text.lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _public_category(db_name: str | None) -> str | None:
    """Map a manager-side category name to one of the 9 public buckets."""
    key = _normalize(db_name)
    if not key:
        return None
    if key in _PUBLIC_CATEGORIES:
        return _PUBLIC_CATEGORIES[key]
    # Fallback substring match (« robe longue », « veste en jean »…)
    for sub, bucket in _PUBLIC_CATEGORIES.items():
        if sub in key:
            return bucket
    return None


class PublicProduct(BaseModel):
    slug: str            # barcode — stable, URL-safe, unique
    name: str
    brand: str | None
    category: str | None         # bucket public (robe, veste…)
    category_label: str | None   # libellé prêt à afficher
    size: str | None
    color: str | None
    condition: str | None        # excellent / tres-bon / bon
    price_eur: float
    photo_url: str | None        # storefront copy (fond détouré) si dispo
    available: bool
    description: str | None
    # Décote vs prix neuf si renseigné dans la fiche.
    retail_price_eur: float | None = None


class PublicProductDetail(PublicProduct):
    """Détail produit + extras pour la fiche /produits/<slug>."""

    photos: list[str]
    related: list["PublicProduct"]


PublicProductDetail.model_rebuild()


def _condition_from_score(score: int | None, status: ProductStatus) -> str:
    """Map score interne → libellé d'état grand public.

    Pas d'attribut explicite « condition » côté Product, on dérive d'un
    proxy : un score élevé = état impeccable, en deep_discounted = très
    bon, sinon bon. C'est volontairement conservateur."""
    if status == ProductStatus.deep_discounted:
        return "bon"
    if score is not None and score >= 75:
        return "excellent"
    return "tres-bon"


def _photo_url(product: Product) -> str | None:
    """Vitrine : storefront_photo_url (détourée) > primary photo > None.

    On préfère la copie « vitrine » (fond off-white + logo) générée par
    ``storefront_photo.generate_and_persist`` ; à défaut on retombe sur
    la photo primaire brute. Pas de placeholder ici — le front gère
    l'absence proprement.
    """
    if product.storefront_photo_url:
        return product.storefront_photo_url
    primary = None
    for ph in (product.photos or []):
        if getattr(ph, "is_primary", False):
            primary = ph
            break
    if primary is None and product.photos:
        primary = product.photos[0]
    if primary is None:
        return None
    return primary.processed_url or primary.url


def _to_public(product: Product) -> PublicProduct:
    cat_name = product.category.name if product.category else None
    bucket = _public_category(cat_name)
    return PublicProduct(
        slug=product.barcode,
        name=product.name or "Pièce sélectionnée",
        brand=product.brand,
        category=bucket,
        category_label=PUBLIC_CATEGORY_LABELS.get(bucket) if bucket else cat_name,
        size=product.size,
        color=product.color,
        condition=_condition_from_score(
            int(getattr(product, "trend_score", 0) or 0), product.status
        ),
        price_eur=float(product.sale_price or 0),
        photo_url=_photo_url(product),
        available=product.status in FLOOR_STATUSES,
        description=product.description,
        retail_price_eur=(
            float(product.purchase_price * 2)
            if product.purchase_price and product.purchase_price > 0
            else None
        ),
    )


@router.get("/products", response_model=list[PublicProduct])
async def list_public_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    categorie: str | None = Query(
        None, description="Filtre catégorie publique (robe, veste, pantalon…)"
    ),
    marque: str | None = Query(None, description="Filtre marque (case-insensitive)"),
    limit: int = Query(120, ge=1, le=500),
):
    """Catalogue public — pièces actuellement sur le rayon.

    Pas de pagination : un boutique vitrine tourne avec 200-400 SKU
    actifs, on renvoie tout. Le front (Next ISR) cache la réponse 5 min."""
    query = (
        select(Product)
        .where(Product.status.in_(FLOOR_STATUSES))
        .order_by(Product.displayed_at.desc().nullslast(), Product.created_at.desc())
    )
    if marque:
        query = query.where(Product.brand.ilike(f"%{marque.strip()}%"))
    query = query.limit(limit)

    products = (await db.execute(query)).scalars().all()
    rendered = [_to_public(p) for p in products]
    if categorie:
        bucket = _public_category(categorie) or categorie.lower()
        rendered = [r for r in rendered if r.category == bucket]
    return rendered


@router.get("/categories")
async def list_public_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Catégories visibles + comptage des pièces disponibles par bucket.

    Sert à construire les chips de filtre sur /produits avec les
    bons compteurs (« Robes (12) »)."""
    rows = (
        await db.execute(
            select(Product.id, Category.name)
            .join(Category, Product.category_id == Category.id, isouter=True)
            .where(Product.status.in_(FLOOR_STATUSES))
        )
    ).all()
    counts: dict[str, int] = {}
    for _pid, cat_name in rows:
        bucket = _public_category(cat_name)
        if not bucket:
            continue
        counts[bucket] = counts.get(bucket, 0) + 1
    return {
        "categories": [
            {"key": k, "label": PUBLIC_CATEGORY_LABELS[k], "count": v}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
        ],
        "total": sum(counts.values()),
    }


@router.get("/products/{slug}", response_model=PublicProductDetail)
async def get_public_product(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Détail d'une pièce identifiée par son code-barres (slug public).

    Renvoie 404 si la pièce n'a jamais été en rayon ; si elle est
    désormais vendue/retournée, on garde la fiche accessible (le front
    affiche « Vendue ») mais ``available=false`` pour permettre la
    désindexation SEO.
    """
    row = await db.execute(
        select(Product).where(Product.barcode == slug.strip())
    )
    product = row.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Pièce introuvable")

    # Suggestions « pourrait aussi vous plaire » : 4 pièces de la même
    # catégorie publique, hors la pièce elle-même, prioritairement
    # disponibles.
    related: list[PublicProduct] = []
    bucket = _public_category(product.category.name if product.category else None)
    if bucket:
        sib_rows = (
            await db.execute(
                select(Product)
                .where(
                    Product.status.in_(FLOOR_STATUSES),
                    Product.id != product.id,
                )
                .order_by(func.random())
                .limit(40)
            )
        ).scalars().all()
        for p in sib_rows:
            if len(related) >= 4:
                break
            cat_name = p.category.name if p.category else None
            if _public_category(cat_name) == bucket:
                related.append(_to_public(p))

    photos: list[str] = []
    sorted_photos = sorted(
        product.photos or [],
        key=lambda ph: (not getattr(ph, "is_primary", False), ph.created_at),
    )
    for ph in sorted_photos:
        url = ph.processed_url or ph.url
        if url and url not in photos:
            photos.append(url)
    # Préfixe vitrine : si on a la copie storefront sur le produit, on la
    # garde en tête (rendu uniformisé).
    if product.storefront_photo_url and product.storefront_photo_url not in photos:
        photos.insert(0, product.storefront_photo_url)

    base = _to_public(product)
    return PublicProductDetail(
        **base.model_dump(),
        photos=photos,
        related=related,
    )
