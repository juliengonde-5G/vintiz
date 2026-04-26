"""Intake batch management (P2-015)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import IntakeBatch, IntakeSource
from app.models.product import Product


class BatchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _generate_batch_number(now: datetime, sequence: int) -> str:
        return f"BATCH-{now:%Y-%m}-{sequence:04d}"

    async def _next_sequence_for_month(self, now: datetime) -> int:
        prefix = f"BATCH-{now:%Y-%m}-"
        result = await self.db.execute(
            select(func.count(IntakeBatch.id)).where(
                IntakeBatch.batch_number.like(f"{prefix}%")
            )
        )
        existing = int(result.scalar_one() or 0)
        return existing + 1

    async def create_batch(
        self,
        *,
        source: IntakeSource,
        n_items_received: int = 0,
        notes: str | None = None,
        recorded_by_user_id: uuid.UUID | None = None,
        received_at: datetime | None = None,
    ) -> IntakeBatch:
        if n_items_received < 0:
            raise HTTPException(
                status_code=400, detail="n_items_received must be ≥ 0"
            )
        now = received_at or datetime.now(timezone.utc)
        sequence = await self._next_sequence_for_month(now)
        batch_number = self._generate_batch_number(now, sequence)
        batch = IntakeBatch(
            batch_number=batch_number,
            source=source,
            received_at=now,
            notes=notes,
            recorded_by_user_id=recorded_by_user_id,
            n_items_received=n_items_received,
        )
        self.db.add(batch)
        await self.db.flush()
        await self.db.refresh(batch)
        return batch

    async def list_batches(self, skip: int = 0, limit: int = 50) -> list[dict]:
        result = await self.db.execute(
            select(
                IntakeBatch,
                func.count(Product.id).label("n_items_tagged"),
            )
            .outerjoin(Product, Product.intake_batch_id == IntakeBatch.id)
            .group_by(IntakeBatch.id)
            .order_by(desc(IntakeBatch.received_at))
            .offset(max(skip, 0))
            .limit(min(max(limit, 1), 200))
        )
        return [
            {
                "id": str(batch.id),
                "batch_number": batch.batch_number,
                "source": batch.source.value,
                "received_at": batch.received_at.isoformat()
                if batch.received_at
                else None,
                "notes": batch.notes,
                "n_items_received": batch.n_items_received,
                "n_items_tagged": int(n_tagged or 0),
                "recorded_by_user_id": str(batch.recorded_by_user_id)
                if batch.recorded_by_user_id
                else None,
            }
            for batch, n_tagged in result.all()
        ]

    async def get_batch(self, batch_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(IntakeBatch).where(IntakeBatch.id == batch_id)
        )
        batch = result.scalar_one_or_none()
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")

        products_result = await self.db.execute(
            select(Product).where(Product.intake_batch_id == batch_id)
        )
        products = products_result.scalars().all()

        return {
            "id": str(batch.id),
            "batch_number": batch.batch_number,
            "source": batch.source.value,
            "received_at": batch.received_at.isoformat() if batch.received_at else None,
            "notes": batch.notes,
            "n_items_received": batch.n_items_received,
            "n_items_tagged": len(products),
            "recorded_by_user_id": str(batch.recorded_by_user_id)
            if batch.recorded_by_user_id
            else None,
            "products": [
                {
                    "id": str(p.id),
                    "barcode": p.barcode,
                    "name": p.name,
                    "status": p.status.value,
                    "sale_price": float(p.sale_price),
                }
                for p in products
            ],
        }

    async def assign_product(
        self, batch_id: uuid.UUID, product_id: uuid.UUID
    ) -> Product:
        """Attach an existing product to a batch (idempotent)."""
        batch_result = await self.db.execute(
            select(IntakeBatch).where(IntakeBatch.id == batch_id)
        )
        batch = batch_result.scalar_one_or_none()
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")

        product_result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = product_result.scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")

        product.intake_batch_id = batch_id
        await self.db.flush()
        return product
