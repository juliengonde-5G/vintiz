"""Admin — grille tarifaire de référence (manager only).

Édition de la grille de référence : pour chaque catégorie, un prix plancher
``standard`` (marques standards) et un prix plancher ``premium`` (marques
premium/luxe, "à partir de"). Le 1ᵉʳ appel pré-remplit la grille depuis la
charte Vintiz pour les catégories dont le nom correspond.

La grille est consultative : l'alerte « prix sous la grille » est affichée à la
création/réévaluation d'un article, elle ne bloque rien.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker
from app.services import price_reference as svc

router = APIRouter(tags=["admin"])

manager_only = RoleChecker(["manager"])


class PriceReferenceIn(BaseModel):
    standard_price: float | None = None
    premium_price: float | None = None
    note: str | None = None


@router.get("/price-reference", dependencies=[Depends(manager_only)])
async def list_price_reference(db: Annotated[AsyncSession, Depends(get_db)]):
    """Grille de référence par catégorie (+ valeurs par défaut Vintiz).

    Pré-remplit la grille depuis la charte au tout premier appel (comme les
    templates de messages) pour que l'écran ne soit jamais vide."""
    if not await svc.has_any(db):
        seeded = await svc.seed_defaults(db)
        if seeded:
            await db.commit()
    rows = await svc.list_for_admin(db)
    return {"rows": rows, "defaults": svc.REFERENCE_GRID_DEFAULTS and True}


@router.put("/price-reference/{category_id}", dependencies=[Depends(manager_only)])
async def set_price_reference(
    category_id: uuid.UUID,
    body: PriceReferenceIn,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    for label, value in (("standard_price", body.standard_price), ("premium_price", body.premium_price)):
        if value is not None and value < 0:
            raise HTTPException(status_code=400, detail=f"{label} doit être positif")
    ref = await svc.upsert(
        db,
        category_id,
        standard_price=body.standard_price,
        premium_price=body.premium_price,
        note=(body.note or None),
    )
    await db.commit()
    return {
        "category_id": str(ref.category_id),
        "standard_price": float(ref.standard_price) if ref.standard_price is not None else None,
        "premium_price": float(ref.premium_price) if ref.premium_price is not None else None,
        "note": ref.note,
    }


@router.delete("/price-reference/{category_id}", dependencies=[Depends(manager_only)])
async def clear_price_reference(
    category_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    deleted = await svc.delete_reference(db, category_id)
    await db.commit()
    return {"deleted": deleted, "category_id": str(category_id)}


@router.post("/price-reference/seed-defaults", dependencies=[Depends(manager_only)])
async def seed_price_reference(
    db: Annotated[AsyncSession, Depends(get_db)],
    overwrite: bool = Query(False, description="Écraser les valeurs déjà saisies"),
):
    """(Re)pré-remplir la grille depuis la charte Vintiz pour les catégories
    dont le nom correspond."""
    written = await svc.seed_defaults(db, overwrite=overwrite)
    await db.commit()
    return {"written": written, "overwrite": overwrite}
