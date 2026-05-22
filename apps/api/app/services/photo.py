"""Multi-photo management for products (P1-008).

Maintains the invariants:
- Each Product has at most one ``ProductPhoto`` with ``is_primary=True``.
- ``Product.photo_url`` always equals the URL of the primary photo (or NULL
  if there are no photos), so callers that read photo_url keep working.
- ``order_index`` is contiguous (0..N-1) per product.

The service does not handle binary uploads; callers pass already-hosted
URLs. A future ticket (Scaleway Object Storage) will plug a real upload
endpoint in front of ``add_photo``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductPhoto


class PhotoService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _load_product(self, product_id: uuid.UUID) -> Product:
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    async def _list_photos_sorted(
        self, product_id: uuid.UUID
    ) -> list[ProductPhoto]:
        result = await self.db.execute(
            select(ProductPhoto)
            .where(ProductPhoto.product_id == product_id)
            .order_by(ProductPhoto.order_index.asc(), ProductPhoto.created_at.asc())
        )
        return list(result.scalars().all())

    async def _resync_primary(self, product: Product) -> None:
        """Pick the lowest-order photo as primary and mirror to Product.photo_url.

        Called after any mutation. Resets order_index to be contiguous and
        mirrors the primary's storefront copy onto Product.storefront_photo_url.
        """
        photos = await self._list_photos_sorted(product.id)
        if not photos:
            product.photo_url = None
            product.storefront_photo_url = None
            return
        explicit_primary = next((p for p in photos if p.is_primary), None)
        primary = explicit_primary or photos[0]
        # Re-pack order indices and flip primary flags.
        for idx, photo in enumerate(photos):
            photo.order_index = idx
            photo.is_primary = photo is primary
        product.photo_url = primary.url
        product.storefront_photo_url = primary.processed_url

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_photos(self, product_id: uuid.UUID) -> list[dict]:
        photos = await self._list_photos_sorted(product_id)
        return [_serialize(p) for p in photos]

    async def add_photo(
        self,
        product_id: uuid.UUID,
        url: str,
        ai_analyzed_at: datetime | None = None,
        ai_confidence: float | None = None,
        processed_url: str | None = None,
        processing_status: str | None = None,
    ) -> ProductPhoto:
        if not url or not url.strip():
            raise HTTPException(status_code=400, detail="url is required")

        product = await self._load_product(product_id)
        existing = await self._list_photos_sorted(product_id)
        next_order = len(existing)
        photo = ProductPhoto(
            product_id=product_id,
            url=url.strip(),
            order_index=next_order,
            is_primary=(next_order == 0),
            ai_analyzed_at=ai_analyzed_at,
            ai_confidence=ai_confidence,
            processed_url=processed_url,
            processing_status=processing_status,
        )
        self.db.add(photo)
        await self.db.flush()
        await self._resync_primary(product)
        await self.db.flush()
        await self.db.refresh(photo)
        return photo

    async def set_processed(
        self,
        product_id: uuid.UUID,
        photo_id: uuid.UUID,
        processed_url: str | None,
        processing_status: str,
    ) -> ProductPhoto:
        """Attach (or clear) the storefront copy of a photo.

        Used after asynchronous / retried background removal. Re-mirrors the
        primary's processed_url onto Product.storefront_photo_url.
        """
        product = await self._load_product(product_id)
        result = await self.db.execute(
            select(ProductPhoto).where(
                ProductPhoto.id == photo_id,
                ProductPhoto.product_id == product_id,
            )
        )
        photo = result.scalar_one_or_none()
        if photo is None:
            raise HTTPException(status_code=404, detail="Photo not found")
        photo.processed_url = processed_url
        photo.processing_status = processing_status
        await self.db.flush()
        await self._resync_primary(product)
        await self.db.flush()
        await self.db.refresh(photo)
        return photo

    async def delete_photo(
        self, product_id: uuid.UUID, photo_id: uuid.UUID
    ) -> None:
        product = await self._load_product(product_id)
        result = await self.db.execute(
            select(ProductPhoto).where(
                ProductPhoto.id == photo_id,
                ProductPhoto.product_id == product_id,
            )
        )
        photo = result.scalar_one_or_none()
        if photo is None:
            raise HTTPException(status_code=404, detail="Photo not found")
        await self.db.delete(photo)
        await self.db.flush()
        await self._resync_primary(product)
        await self.db.flush()

    async def set_primary(
        self, product_id: uuid.UUID, photo_id: uuid.UUID
    ) -> ProductPhoto:
        product = await self._load_product(product_id)
        result = await self.db.execute(
            select(ProductPhoto).where(
                ProductPhoto.id == photo_id,
                ProductPhoto.product_id == product_id,
            )
        )
        photo = result.scalar_one_or_none()
        if photo is None:
            raise HTTPException(status_code=404, detail="Photo not found")

        # Move the chosen photo to order 0 then resync.
        for sibling in await self._list_photos_sorted(product_id):
            sibling.is_primary = False
        photo.is_primary = True
        photo.order_index = -1  # ensures it sorts first before resync packs indices
        await self.db.flush()
        await self._resync_primary(product)
        await self.db.flush()
        await self.db.refresh(photo)
        return photo

    async def reorder(
        self, product_id: uuid.UUID, ordered_ids: Iterable[uuid.UUID]
    ) -> list[dict]:
        product = await self._load_product(product_id)
        ids = list(ordered_ids)
        existing = await self._list_photos_sorted(product_id)
        if len(ids) != len(existing) or set(ids) != {p.id for p in existing}:
            raise HTTPException(
                status_code=400,
                detail="ordered_ids must be a permutation of the product's photo ids",
            )
        # Apply requested order (the resync below is a no-op since we set
        # order_index ourselves, but we still reuse it to keep primary in sync).
        by_id = {p.id: p for p in existing}
        for idx, pid in enumerate(ids):
            by_id[pid].order_index = idx
            by_id[pid].is_primary = idx == 0
        await self.db.flush()
        await self._resync_primary(product)
        await self.db.flush()
        return [_serialize(p) for p in await self._list_photos_sorted(product_id)]


def _serialize(photo: ProductPhoto) -> dict:
    return {
        "id": str(photo.id),
        "product_id": str(photo.product_id),
        "url": photo.url,
        "processed_url": photo.processed_url,
        "processing_status": photo.processing_status,
        "order_index": photo.order_index,
        "is_primary": photo.is_primary,
        "ai_analyzed_at": photo.ai_analyzed_at.isoformat() if photo.ai_analyzed_at else None,
        "ai_confidence": photo.ai_confidence,
        "created_at": photo.created_at.isoformat() if photo.created_at else None,
    }
