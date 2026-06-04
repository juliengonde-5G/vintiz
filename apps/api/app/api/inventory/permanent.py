"""Articles Permanents — CRUD + historique de ventes.

Catalogue à quantité illimitée distinct de Product. Un même code-barres se
scanne autant de fois qu'on veut au POS. Toutes les ventes sont attribuées
à la zone virtuelle « Vente Caisse » pour le reporting.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker, get_current_user
from app.models.permanent_item import PermanentItem
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category
from app.models.user import User
from app.services import storefront_photo

router = APIRouter(prefix="/inventory/permanent", tags=["permanent-items"])

manager_only = RoleChecker(["manager"])

# Stockage des images sur disque. Une arborescence séparée
# (``uploads/permanent/...``) garde les actifs des articles permanents
# distincts des produits seconde main.
_UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "uploads" / "permanent"
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_BYTES = 20 * 1024 * 1024
_SUFFIX_MEDIA = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PermanentItemCreate(BaseModel):
    name: str
    barcode: str | None = None
    category_id: uuid.UUID
    sale_price: float
    # Le taux de TVA n'est PAS personnalisable côté article permanent : il
    # est figé au taux normal (20 %) via le défaut du modèle. Pas de champ
    # d'entrée — voir la demande métier « jamais modifiable ».
    photo_url: str | None = None
    available_from: datetime | None = None
    description: str | None = None
    is_active: bool = True


class PermanentItemUpdate(BaseModel):
    name: str | None = None
    category_id: uuid.UUID | None = None
    sale_price: float | None = None
    available_from: datetime | None = None
    description: str | None = None
    is_active: bool | None = None


class PermanentItemPriceUpdate(BaseModel):
    sale_price: float


def _serialize(item: PermanentItem, category_name: str | None = None) -> dict:
    return {
        "id": str(item.id),
        "name": item.name,
        "barcode": item.barcode,
        "category_id": str(item.category_id),
        "category": category_name,
        "sale_price": float(item.sale_price),
        "tva_rate": float(item.tva_rate),
        "photo_url": item.photo_url,
        "storefront_photo_url": item.storefront_photo_url,
        "available_from": item.available_from.isoformat() if item.available_from else None,
        "is_active": item.is_active,
        "description": item.description,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _generate_barcode() -> str:
    """Format Vintiz dédié aux articles permanents : ``VTZP-{year}-{6 digits}``.

    Le préfixe ``VTZP`` distingue ces codes des produits seconde main
    (``VTZ-...``), pour qu'un agent comptable repère vite la nature de la
    ligne sur un export."""
    import secrets
    year = datetime.now().year
    suffix = f"{secrets.randbelow(1_000_000):06d}"
    return f"VTZP-{year}-{suffix}"


# ---------------------------------------------------------------------------
# Stats — zone « Vente Caisse »
# ---------------------------------------------------------------------------

@router.get("/stats/zone")
async def zone_performance(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    period_days: int = 30,
):
    """Performance agrégée de la zone virtuelle Vente Caisse.

    Sommée sur l'ensemble des articles permanents : CA / unités / panier moyen
    / Top 5 articles par CA sur la période. Volontairement séparé des KPIs
    retail (sell-through, GMROI) qui n'ont pas de sens sur un stock infini.
    """
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=max(1, period_days))

    # Totaux période
    agg = await db.execute(
        select(
            func.coalesce(func.sum(TransactionItem.quantity), 0),
            func.coalesce(func.sum(TransactionItem.line_total), 0),
            func.count(func.distinct(TransactionItem.transaction_id)),
        )
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .where(
            TransactionItem.permanent_item_id.is_not(None),
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= since,
        )
    )
    units, revenue, tx_count = agg.one()

    # Top 5 articles par CA
    top_rows = await db.execute(
        select(
            PermanentItem.id,
            PermanentItem.name,
            func.coalesce(func.sum(TransactionItem.quantity), 0).label("units"),
            func.coalesce(func.sum(TransactionItem.line_total), 0).label("revenue"),
        )
        .join(TransactionItem, TransactionItem.permanent_item_id == PermanentItem.id)
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= since,
        )
        .group_by(PermanentItem.id, PermanentItem.name)
        .order_by(func.sum(TransactionItem.line_total).desc())
        .limit(5)
    )
    top_items = [
        {
            "id": str(row.id),
            "name": row.name,
            "units": int(row.units or 0),
            "revenue": float(row.revenue or 0),
        }
        for row in top_rows.all()
    ]

    return {
        "period_days": period_days,
        "zone_name": "Vente Caisse",
        "units_sold": int(units or 0),
        "total_revenue": float(revenue or 0),
        "transaction_count": int(tx_count or 0),
        "avg_basket_per_tx": (
            float(revenue) / int(tx_count) if tx_count and revenue else 0.0
        ),
        "top_items": top_items,
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("")
async def list_permanent_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    include_inactive: bool = True,
):
    """Liste tous les articles permanents avec leur catégorie."""
    query = (
        select(PermanentItem, Category.name)
        .outerjoin(Category, PermanentItem.category_id == Category.id)
        .order_by(PermanentItem.is_active.desc(), PermanentItem.name)
    )
    if not include_inactive:
        query = query.where(PermanentItem.is_active.is_(True))
    result = await db.execute(query)
    return [_serialize(item, cat_name) for item, cat_name in result.all()]


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(manager_only)])
async def create_permanent_item(
    payload: PermanentItemCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Crée un article permanent. Génère le code-barres si non fourni."""
    barcode = (payload.barcode or "").strip() or _generate_barcode()

    # Empêcher la collision avec les produits seconde main : barcode global unique
    # côté UX (la résolution au POS interroge les deux tables).
    from app.models.product import Product
    existing_prod = await db.execute(
        select(Product.id).where(Product.barcode == barcode).limit(1)
    )
    if existing_prod.scalar_one_or_none():
        raise HTTPException(409, f"Code-barres {barcode} déjà utilisé par un produit seconde main")

    existing = await db.execute(
        select(PermanentItem).where(PermanentItem.barcode == barcode).limit(1)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Code-barres {barcode} déjà utilisé")

    item = PermanentItem(
        name=payload.name.strip(),
        barcode=barcode,
        category_id=payload.category_id,
        sale_price=payload.sale_price,
        # tva_rate non fourni → défaut modèle 20 % (jamais personnalisable).
        photo_url=payload.photo_url,
        available_from=payload.available_from,
        description=payload.description,
        is_active=payload.is_active,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)

    cat_row = await db.execute(select(Category.name).where(Category.id == item.category_id))
    return _serialize(item, cat_row.scalar_one_or_none())


@router.get("/{item_id}")
async def get_permanent_item(
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Fiche détaillée d'un article permanent."""
    result = await db.execute(select(PermanentItem).where(PermanentItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Article permanent introuvable")
    cat_row = await db.execute(select(Category.name).where(Category.id == item.category_id))
    return _serialize(item, cat_row.scalar_one_or_none())


@router.patch("/{item_id}", dependencies=[Depends(manager_only)])
async def update_permanent_item(
    item_id: uuid.UUID,
    payload: PermanentItemUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Édite un article permanent (champs partiels)."""
    result = await db.execute(select(PermanentItem).where(PermanentItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Article permanent introuvable")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(item, field, value)
    await db.flush()
    await db.refresh(item)
    cat_row = await db.execute(select(Category.name).where(Category.id == item.category_id))
    return _serialize(item, cat_row.scalar_one_or_none())


@router.put("/{item_id}/price", dependencies=[Depends(manager_only)])
async def update_price(
    item_id: uuid.UUID,
    payload: PermanentItemPriceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Raccourci dédié pour la modification du tarif depuis la fiche."""
    result = await db.execute(select(PermanentItem).where(PermanentItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Article permanent introuvable")
    if payload.sale_price < 0:
        raise HTTPException(400, "Prix de vente négatif refusé")
    item.sale_price = payload.sale_price
    await db.flush()
    await db.refresh(item)
    cat_row = await db.execute(select(Category.name).where(Category.id == item.category_id))
    return _serialize(item, cat_row.scalar_one_or_none())


@router.post("/{item_id}/toggle-active", dependencies=[Depends(manager_only)])
async def toggle_active(
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Bascule activation/désactivation. Un article désactivé n'est plus scannable."""
    result = await db.execute(select(PermanentItem).where(PermanentItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Article permanent introuvable")
    item.is_active = not item.is_active
    await db.flush()
    return {"id": str(item.id), "is_active": item.is_active}


@router.delete("/{item_id}", dependencies=[Depends(manager_only)])
async def delete_permanent_item(
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Supprime définitivement un article permanent. Bloqué s'il a déjà été vendu
    (la FK transaction_items.permanent_item_id préserve l'historique). Préférer
    désactiver pour les articles déjà passés en caisse."""
    sale = await db.execute(
        select(TransactionItem.id).where(TransactionItem.permanent_item_id == item_id).limit(1)
    )
    if sale.scalar_one_or_none():
        raise HTTPException(
            409,
            "Article déjà vendu — désactivez-le plutôt que de le supprimer.",
        )
    result = await db.execute(select(PermanentItem).where(PermanentItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Article permanent introuvable")
    await db.delete(item)
    await db.flush()
    return {"deleted": str(item_id)}


# ---------------------------------------------------------------------------
# Photo upload + storefront generation
# ---------------------------------------------------------------------------

@router.post("/{item_id}/photo", dependencies=[Depends(manager_only)])
async def upload_photo(
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    """Upload de la photo + génération best-effort de la copie vitrine détourée."""
    result = await db.execute(select(PermanentItem).where(PermanentItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Article permanent introuvable")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Extension non supportée: {sorted(_ALLOWED_EXTENSIONS)}")

    blob = await file.read(_MAX_BYTES + 1)
    if len(blob) > _MAX_BYTES:
        raise HTTPException(413, f"Fichier trop volumineux (max {_MAX_BYTES // (1024 * 1024)} Mo)")
    if not blob:
        raise HTTPException(400, "Fichier vide")

    target_dir = _UPLOAD_ROOT / str(item_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{uuid.uuid4().hex}{suffix}"
    target_path = target_dir / fname
    target_path.write_bytes(blob)
    os.chmod(target_path, 0o644)
    item.photo_url = f"/uploads/permanent/{item_id}/{fname}"

    # Détourage best-effort. ``storefront_photo.generate`` est backend-agnostique
    # (Photoroom > rembg > skip), pas couplé aux products. On compose
    # ensuite l'image processed sur la même arborescence permanent/.
    media_type = _SUFFIX_MEDIA.get(suffix, "image/jpeg")
    try:
        gen = await storefront_photo.generate(blob, media_type)
        if gen.status == "done" and gen.image is not None:
            processed_fname = f"{uuid.uuid4().hex}_storefront.png"
            processed_path = target_dir / processed_fname
            processed_path.write_bytes(gen.image)
            os.chmod(processed_path, 0o644)
            item.storefront_photo_url = f"/uploads/permanent/{item_id}/{processed_fname}"
    except Exception:
        # Backend indisponible / image illisible — on garde la photo brute.
        pass

    await db.flush()
    await db.refresh(item)
    return {
        "id": str(item.id),
        "photo_url": item.photo_url,
        "storefront_photo_url": item.storefront_photo_url,
    }


@router.post("/{item_id}/storefront-regenerate", dependencies=[Depends(manager_only)])
async def regenerate_storefront(
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Recalcule la copie vitrine à partir de la photo brute existante."""
    result = await db.execute(select(PermanentItem).where(PermanentItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Article permanent introuvable")
    if not item.photo_url:
        raise HTTPException(400, "Aucune photo brute à détourer")

    # Réutilise fetch_source_bytes (gère /uploads/ + http) puis génère.
    source = await storefront_photo.fetch_source_bytes(item.photo_url)
    if source is None:
        raise HTTPException(422, "Image brute introuvable")
    blob, media_type = source
    gen = await storefront_photo.generate(blob, media_type)
    if gen.status == "done" and gen.image is not None:
        target_dir = _UPLOAD_ROOT / str(item_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        processed_fname = f"{uuid.uuid4().hex}_storefront.png"
        processed_path = target_dir / processed_fname
        processed_path.write_bytes(gen.image)
        os.chmod(processed_path, 0o644)
        item.storefront_photo_url = f"/uploads/permanent/{item_id}/{processed_fname}"
        await db.flush()
    return {"storefront_photo_url": item.storefront_photo_url, "status": gen.status}


# ---------------------------------------------------------------------------
# Sales history
# ---------------------------------------------------------------------------

@router.get("/{item_id}/sales")
async def list_sales(
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 200,
):
    """Liste les ventes (ligne par ligne) liées à cet article permanent.

    Renvoie chaque ligne de transaction avec son prix unitaire, sa quantité,
    sa remise et la date — utilisé par la fiche article pour afficher le
    timeline des ventes + un agrégat (CA total, unités vendues, dernière
    vente).
    """
    item_check = await db.execute(select(PermanentItem.id).where(PermanentItem.id == item_id))
    if item_check.scalar_one_or_none() is None:
        raise HTTPException(404, "Article permanent introuvable")

    result = await db.execute(
        select(TransactionItem, Transaction)
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .where(TransactionItem.permanent_item_id == item_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    )
    rows = result.all()

    sales = [
        {
            "transaction_id": str(t.id),
            "transaction_number": t.transaction_number,
            "transaction_type": t.transaction_type.value,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "quantity": int(ti.quantity),
            "unit_price": float(ti.unit_price),
            "discount_percent": float(ti.discount_percent or 0),
            "line_total": float(ti.line_total),
        }
        for ti, t in rows
    ]

    # Agrégats sur l'ensemble (pas seulement la fenêtre récupérée)
    agg = await db.execute(
        select(
            func.coalesce(func.sum(TransactionItem.quantity), 0),
            func.coalesce(func.sum(TransactionItem.line_total), 0),
            func.max(Transaction.created_at),
        )
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .where(
            TransactionItem.permanent_item_id == item_id,
            Transaction.transaction_type == TransactionType.sale,
        )
    )
    units, revenue, last_at = agg.one()

    return {
        "sales": sales,
        "summary": {
            "units_sold": int(units or 0),
            "total_revenue": float(revenue or 0),
            "last_sold_at": last_at.isoformat() if last_at else None,
        },
    }


# ---------------------------------------------------------------------------
# Étiquette Zebra (réutilise le pipeline ZPL des produits seconde main)
# ---------------------------------------------------------------------------

async def _load_label_data(db: AsyncSession, item_id: uuid.UUID):
    """Charge l'article + construit le LabelData (sans taille/genre/semaine).

    Un article permanent n'a ni taille, ni genre, ni numéro de semaine : on
    n'imprime que le nom, la catégorie, le code-barres et le prix — le même
    gabarit Zebra que les produits seconde main, qui ignore proprement les
    champs absents.
    """
    from app.services.zebra_zpl import LabelData

    result = await db.execute(select(PermanentItem).where(PermanentItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Article permanent introuvable")
    cat_row = await db.execute(select(Category.name).where(Category.id == item.category_id))
    category_name = cat_row.scalar_one_or_none() or "Article"
    data = LabelData(
        product_name=item.name,
        category=category_name,
        size=None,
        condition=None,
        sale_price=float(item.sale_price),
        barcode=item.barcode,
        # L'ancre de date (libellé « Semaine ») retombe sur la mise en vente
        # puis la création — un article permanent n'a pas de date de rayon.
        shelf_date=item.available_from,
        location=None,
        entry_date=item.created_at,
        week_number=None,
        gender=None,
    )
    return item, data


@router.post("/{item_id}/label/print", dependencies=[Depends(manager_only)])
async def print_label(
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    copies: int = 1,
):
    """Imprime le jeu d'étiquettes (info + prix) de l'article sur la Zebra.

    Transports réseau / cloud : le backend pousse le ZPL. Le mode Bluetooth
    est rejeté ici (la tablette imprime via ``/label/zpl`` + Web Bluetooth),
    exactement comme pour les produits seconde main.
    """
    from app.api.labels.router import (
        _dispatch_zpl,
        _label_config,
        _validate_transport,
    )
    from app.services import zebra_printer
    from app.services.zebra_zpl import build_label_set_zpl

    _item, data = await _load_label_data(db, item_id)
    cfg = _label_config()
    _validate_transport(cfg)
    zpl = build_label_set_zpl(data, copies=max(copies, 1))
    try:
        target = await _dispatch_zpl(cfg, zpl)
    except zebra_printer.PrinterUnreachable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "status": "printed",
        "permanent_item_id": str(item_id),
        "printer_ip": target,
        "copies": max(copies, 1),
    }


@router.get("/{item_id}/label/preview", dependencies=[Depends(manager_only)])
async def preview_label(
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Aperçu PNG (Labelary) du jeu d'étiquettes — identique au rendu physique."""
    from app.api.labels.router import _stack_pngs_vertically
    from app.services.label_preview import PreviewUnavailable, render_zpl_to_png
    from app.services.zebra_zpl import build_label_zpl, build_price_label_zpl

    _item, data = await _load_label_data(db, item_id)
    try:
        product_png = await render_zpl_to_png(build_label_zpl(data))
        price_png = await render_zpl_to_png(build_price_label_zpl(data))
    except PreviewUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(
        content=_stack_pngs_vertically([product_png, price_png]),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{item_id}/label/zpl", dependencies=[Depends(manager_only)])
async def label_zpl(
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    copies: int = 1,
):
    """ZPL brut du jeu d'étiquettes — consommé par le transport Bluetooth
    (la tablette l'écrit sur le service BLE Parser de la Zebra)."""
    from app.services.zebra_zpl import build_label_set_zpl

    _item, data = await _load_label_data(db, item_id)
    zpl = build_label_set_zpl(data, copies=max(copies, 1))
    return Response(
        content=zpl,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )
