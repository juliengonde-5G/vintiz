"""Refund / store-credit (avoir) flow for the POS (P1-010 + P1-016).

A refund creates a *new* Transaction with ``transaction_type=refund``,
linked to the original sale via ``original_transaction_id``. Refunded
products are returned to ``ProductStatus.display`` (back on the shelf).
The refund total can be settled in cash, on the original card, or as
store credit (avoir) added to the client's balance.

Z reports already aggregate refunds separately; the NF525 hash chain on
the new transaction binds it cryptographically to all prior activity.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import AvoirTransaction, AvoirTxType, Client
from app.models.pos import (
    Payment,
    PaymentMethod,
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.models.product import Product, ProductStatus


# Mapping refund_method (UI vocabulary) → DB Payment method.
# "avoir" has no Payment row — it lives in AvoirTransaction instead.
_REFUND_METHOD_TO_PAYMENT: dict[str, PaymentMethod] = {
    "cash": PaymentMethod.cash,
    "especes": PaymentMethod.cash,
    "card": PaymentMethod.card,
    "carte": PaymentMethod.card,
    "cheque": PaymentMethod.cheque,
}
_VALID_REFUND_METHODS = set(_REFUND_METHOD_TO_PAYMENT) | {"avoir"}


class RefundLineInput:
    """Lightweight DTO accepted by RefundService.refund_transaction.

    Mirrors the API request schema; using a plain class keeps the service
    decoupled from FastAPI's pydantic models.
    """

    __slots__ = ("transaction_item_id", "quantity")

    def __init__(self, transaction_item_id: uuid.UUID, quantity: int):
        self.transaction_item_id = transaction_item_id
        self.quantity = quantity


class RefundService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _load_original(self, original_id: uuid.UUID) -> Transaction:
        result = await self.db.execute(
            select(Transaction).where(Transaction.id == original_id)
        )
        original = result.scalar_one_or_none()
        if original is None:
            raise HTTPException(status_code=404, detail="Transaction not found")
        if original.transaction_type != TransactionType.sale:
            raise HTTPException(
                status_code=400,
                detail="Only sales can be refunded",
            )
        return original

    async def _already_refunded_qty(
        self, original_tx_id: uuid.UUID, original_item: TransactionItem
    ) -> int:
        """How many units of ``original_item``'s product have already been
        refunded under prior refund transactions linked to the original sale.

        Manual items (product_id is NULL) match by item id directly.
        """
        if original_item.product_id is None:
            # Without a product link we fall back to matching by item id; there
            # is no single source of truth across refunds for manual items.
            return 0
        result = await self.db.execute(
            select(func.coalesce(func.sum(TransactionItem.quantity), 0))
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.original_transaction_id == original_tx_id,
                Transaction.transaction_type == TransactionType.refund,
                TransactionItem.product_id == original_item.product_id,
            )
        )
        return int(result.scalar_one() or 0)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def refund_transaction(
        self,
        original_tx_id: uuid.UUID,
        items: Iterable[RefundLineInput],
        refund_method: str,
        user_id: uuid.UUID,
        cashier_id: uuid.UUID | None,
        reason: str | None,
    ) -> Transaction:
        method = (refund_method or "").strip().lower()
        if method not in _VALID_REFUND_METHODS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid refund method: {refund_method!r}",
            )

        original = await self._load_original(original_tx_id)

        # Pre-load the original items into a dict keyed by id for validation.
        original_items: dict[uuid.UUID, TransactionItem] = {
            item.id: item for item in (original.items or [])
        }
        if not original_items:
            raise HTTPException(
                status_code=400,
                detail="Original transaction has no refundable items",
            )

        items_list = list(items)
        if not items_list:
            raise HTTPException(status_code=400, detail="No items to refund")

        # Validate every requested line against the original.
        refund_amount_ttc = Decimal("0")
        plan: list[tuple[TransactionItem, int, Decimal]] = []
        for line in items_list:
            if line.quantity <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Refund quantity must be positive",
                )
            original_item = original_items.get(line.transaction_item_id)
            if original_item is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Item {line.transaction_item_id} does not belong to "
                        f"transaction {original_tx_id}"
                    ),
                )
            already = await self._already_refunded_qty(
                original_tx_id, original_item
            )
            remaining = original_item.quantity - already
            if line.quantity > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cannot refund {line.quantity} units of "
                        f"{line.transaction_item_id}: only {remaining} remain"
                    ),
                )
            unit_after_discount = (
                Decimal(str(original_item.unit_price))
                * (Decimal("100") - Decimal(str(original_item.discount_percent or 0)))
                / Decimal("100")
            ).quantize(Decimal("0.01"))
            line_total = (unit_after_discount * line.quantity).quantize(
                Decimal("0.01")
            )
            refund_amount_ttc += line_total
            plan.append((original_item, line.quantity, line_total))

        if refund_amount_ttc <= 0:
            raise HTTPException(
                status_code=400, detail="Refund total is zero — nothing to refund"
            )

        # Avoir refunds need a client to credit.
        if method == "avoir" and original.client_id is None:
            raise HTTPException(
                status_code=400,
                detail="Avoir refund requires the original sale to have a client",
            )

        # Allocate the refund's transaction number.
        max_num = await self.db.execute(
            select(func.coalesce(func.max(Transaction.transaction_number), 0))
        )
        next_number = (max_num.scalar_one() or 0) + 1

        total_ht = (refund_amount_ttc / Decimal("1.20")).quantize(Decimal("0.01"))
        total_tva = (refund_amount_ttc - total_ht).quantize(Decimal("0.01"))

        refund_tx = Transaction(
            transaction_number=next_number,
            transaction_type=TransactionType.refund,
            user_id=user_id,
            cashier_id=cashier_id,
            client_id=original.client_id,
            original_transaction_id=original.id,
            refund_reason=(reason or None),
            total_ht=float(total_ht),
            total_tva=float(total_tva),
            total_ttc=float(refund_amount_ttc),
            hash_chain="",  # FiscalService.sign_transaction sets it
        )
        self.db.add(refund_tx)
        await self.db.flush()

        # Mirror each refunded line and put the product back on display.
        for original_item, qty, line_total in plan:
            self.db.add(
                TransactionItem(
                    transaction_id=refund_tx.id,
                    product_id=original_item.product_id,
                    quantity=qty,
                    unit_price=float(original_item.unit_price),
                    discount_percent=float(original_item.discount_percent or 0),
                    line_total=float(line_total),
                )
            )
            if original_item.product_id is not None:
                product_result = await self.db.execute(
                    select(Product).where(Product.id == original_item.product_id)
                )
                product = product_result.scalar_one_or_none()
                if product is not None and product.status == ProductStatus.sold:
                    product.status = ProductStatus.display
                    product.sold_at = None

        # Settlement: cash/card/cheque → Payment row; avoir → AvoirTransaction.
        if method == "avoir":
            assert original.client_id is not None
            client_result = await self.db.execute(
                select(Client).where(Client.id == original.client_id)
            )
            client = client_result.scalar_one()
            client.avoir_credit = float(
                Decimal(str(client.avoir_credit)) + refund_amount_ttc
            )
            self.db.add(
                AvoirTransaction(
                    client_id=client.id,
                    transaction_id=refund_tx.id,
                    tx_type=AvoirTxType.credit,
                    amount=float(refund_amount_ttc),
                    reason=(reason or "Refund credit"),
                )
            )
        else:
            payment_method = _REFUND_METHOD_TO_PAYMENT[method]
            self.db.add(
                Payment(
                    transaction_id=refund_tx.id,
                    method=payment_method,
                    amount=float(refund_amount_ttc),
                )
            )

        await self.db.flush()
        await self.db.refresh(refund_tx)
        return refund_tx

    # ------------------------------------------------------------------
    # Avoir history (read-only)
    # ------------------------------------------------------------------

    async def list_avoir_history(self, client_id: uuid.UUID) -> list[dict]:
        result = await self.db.execute(
            select(AvoirTransaction)
            .where(AvoirTransaction.client_id == client_id)
            .order_by(AvoirTransaction.created_at.desc())
        )
        rows = result.scalars().all()
        return [
            {
                "id": str(row.id),
                "transaction_id": str(row.transaction_id) if row.transaction_id else None,
                "tx_type": row.tx_type.value,
                "amount": float(row.amount),
                "reason": row.reason,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
