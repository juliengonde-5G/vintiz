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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RefundError, ResourceNotFound
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
            select(Transaction).where(Transaction.id == original_id).with_for_update()
        )
        original = result.scalar_one_or_none()
        if original is None:
            raise ResourceNotFound("Transaction", original_id)
        if original.transaction_type != TransactionType.sale:
            raise RefundError("Only sales can be refunded")
        return original

    async def _already_refunded_qty(
        self, original_tx_id: uuid.UUID, original_item: TransactionItem
    ) -> int:
        """How many units of ``original_item`` have already been refunded
        under prior refund transactions linked to the original sale.

        Aggregation is by ``original_transaction_item_id`` so two distinct
        lines of the same product on the same sale don't share their refund
        quota. Refund rows created before this column existed
        (``original_transaction_item_id IS NULL``) fall back to the legacy
        product_id match — accurate for the ~99 % of sales that have a
        single line per product.
        """
        # New path: rows that point at this exact item.
        modern_row = await self.db.execute(
            select(func.coalesce(func.sum(TransactionItem.quantity), 0))
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.original_transaction_id == original_tx_id,
                Transaction.transaction_type == TransactionType.refund,
                TransactionItem.original_transaction_item_id == original_item.id,
            )
        )
        modern_qty = int(modern_row.scalar_one() or 0)

        if original_item.product_id is None:
            return modern_qty

        # Legacy path: pre-Sprint-2 refund rows have NULL on the new column.
        # Match by product_id only when the modern column is missing.
        legacy_row = await self.db.execute(
            select(func.coalesce(func.sum(TransactionItem.quantity), 0))
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.original_transaction_id == original_tx_id,
                Transaction.transaction_type == TransactionType.refund,
                TransactionItem.original_transaction_item_id.is_(None),
                TransactionItem.product_id == original_item.product_id,
            )
        )
        legacy_qty = int(legacy_row.scalar_one() or 0)
        return modern_qty + legacy_qty

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
        client_uuid: uuid.UUID | None = None,
    ) -> Transaction:
        method = (refund_method or "").strip().lower()
        if method not in _VALID_REFUND_METHODS:
            raise RefundError(f"Invalid refund method: {refund_method!r}")

        # Idempotence: a retried / double-clicked refund POST replays the
        # same client_uuid. Return the already-created refund instead of
        # issuing a second one (which would double-credit the customer and,
        # for card, fire a second SumUp refund).
        if client_uuid is not None:
            existing = (
                await self.db.execute(
                    select(Transaction).where(
                        Transaction.client_uuid == client_uuid,
                        Transaction.transaction_type == TransactionType.refund,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing

        dialect = self.db.bind.dialect.name if self.db.bind else "postgresql"
        if dialect == "postgresql":
            from sqlalchemy import text

            await self.db.execute(text("SELECT pg_advisory_xact_lock(5252026)"))
            if client_uuid is not None:
                existing = (
                    await self.db.execute(
                        select(Transaction).where(
                            Transaction.client_uuid == client_uuid,
                            Transaction.transaction_type == TransactionType.refund,
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    return existing

        original = await self._load_original(original_tx_id)

        original_items: dict[uuid.UUID, TransactionItem] = {
            item.id: item for item in (original.items or [])
        }
        if not original_items:
            raise RefundError("Original transaction has no refundable items")

        items_list = list(items)
        if not items_list:
            raise RefundError("No items to refund")

        refund_amount_ttc = Decimal("0")
        plan: list[tuple[TransactionItem, int, Decimal]] = []
        for line in items_list:
            if line.quantity <= 0:
                raise RefundError("Refund quantity must be positive")
            original_item = original_items.get(line.transaction_item_id)
            if original_item is None:
                raise RefundError(
                    f"Item {line.transaction_item_id} does not belong to "
                    f"transaction {original_tx_id}"
                )
            already = await self._already_refunded_qty(original_tx_id, original_item)
            remaining = original_item.quantity - already
            if line.quantity > remaining:
                raise RefundError(
                    f"Cannot refund {line.quantity} units of "
                    f"{line.transaction_item_id}: only {remaining} remain"
                )
            # Base du remboursement : le ``line_total`` réellement encaissé.
            # Re-dériver depuis ``discount_percent`` (arrondi à 2 décimales)
            # peut dévier d'un centime — visible sur les prix manuels (ex.
            # étiquette 149 €, prix manuel 100 € → 32.89 % stocké → 99,99 €).
            stored_total = Decimal(str(original_item.line_total or 0))
            if stored_total > 0:
                qty = max(1, int(original_item.quantity))
                per_unit = (stored_total / qty).quantize(Decimal("0.01"))
                if line.quantity == remaining:
                    # Dernier lot : solde exact de la ligne (les lots
                    # précédents ont été facturés ``per_unit`` chacun).
                    line_total = stored_total - per_unit * already
                else:
                    line_total = (per_unit * line.quantity).quantize(
                        Decimal("0.01")
                    )
            else:
                # Repli (lignes legacy sans line_total) : ancien calcul.
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
            raise RefundError("Refund total is zero — nothing to refund")

        if method == "avoir" and original.client_id is None:
            raise RefundError("Avoir refund requires the original sale to have a client")

        # Shared fiscal lock + MAX+1 gives a rollback-safe, gap-free counter.
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
            client_uuid=client_uuid,
            refund_reason=(reason or None),
            total_ht=float(total_ht),
            total_tva=float(total_tva),
            total_ttc=float(refund_amount_ttc),
            hash_chain="",  # FiscalService.sign_transaction sets it
        )
        self.db.add(refund_tx)
        await self.db.flush()

        for original_item, qty, line_total in plan:
            self.db.add(
                TransactionItem(
                    transaction_id=refund_tx.id,
                    product_id=original_item.product_id,
                    product_name=getattr(original_item, "product_name", None),
                    original_transaction_item_id=original_item.id,
                    quantity=qty,
                    unit_price=float(original_item.unit_price),
                    discount_percent=float(original_item.discount_percent or 0),
                    line_total=float(line_total),
                    promotional=bool(original_item.promotional),
                )
            )
            if original_item.product_id is not None:
                product_result = await self.db.execute(
                    select(Product)
                    .where(Product.id == original_item.product_id)
                    .with_for_update()
                )
                product = product_result.scalar_one_or_none()
                if product is not None and product.status == ProductStatus.sold:
                    product.status = ProductStatus.display
                    product.sold_at = None

        if method == "avoir":
            client_result = await self.db.execute(
                select(Client)
                .where(Client.id == original.client_id)
                .with_for_update()
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

        await self._reverse_loyalty_for_refund(original, refund_tx)
        await self.db.flush()
        await self.db.refresh(refund_tx)
        return refund_tx

    async def _reverse_loyalty_for_refund(
        self,
        original: Transaction,
        refund_tx: Transaction,
    ) -> None:
        """Reverse exactly the points no longer justified after this refund.

        The calculation is cumulative across partial refunds, so cent/euro
        rounding cannot be exploited by splitting a return. Unused milestone
        vouchers that are no longer earned are disabled. If one was already
        spent, a points debt postpones the next voucher instead of silently
        granting the benefit twice.
        """
        if original.client_id is None:
            return

        from app.models.client import (
            LoyaltyAccount,
            LoyaltyTransaction,
            LoyaltyTxType,
        )
        from app.models.coupon import Coupon, CouponSource
        from app.services.loyalty_config import get_earning_config
        from app.services.offers_engine import points_to_credit

        account = (
            await self.db.execute(
                select(LoyaltyAccount)
                .where(LoyaltyAccount.client_id == original.client_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if account is None:
            return

        earn = (
            await self.db.execute(
                select(LoyaltyTransaction)
                .where(
                    LoyaltyTransaction.account_id == account.id,
                    LoyaltyTransaction.tx_type == LoyaltyTxType.earn,
                    (
                        (LoyaltyTransaction.transaction_id == original.id)
                        | (
                            (LoyaltyTransaction.transaction_id.is_(None))
                            & (
                                LoyaltyTransaction.description
                                == f"Sale #{original.transaction_number}"
                            )
                        )
                    ),
                )
                .order_by(LoyaltyTransaction.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if earn is None or earn.points <= 0:
            return

        # Flush refund items so the cumulative SQL includes this refund.
        await self.db.flush()
        eligible_item_ids = [
            item.id for item in (original.items or []) if not item.promotional
        ]
        eligible_original = sum(
            Decimal(str(item.line_total or 0))
            for item in (original.items or [])
            if not item.promotional
        )
        refunded_eligible = Decimal("0")
        if eligible_item_ids:
            refunded_result = await self.db.execute(
                select(func.coalesce(func.sum(TransactionItem.line_total), 0))
                .join(Transaction, TransactionItem.transaction_id == Transaction.id)
                .where(
                    Transaction.original_transaction_id == original.id,
                    Transaction.transaction_type == TransactionType.refund,
                    TransactionItem.original_transaction_item_id.in_(eligible_item_ids),
                )
            )
            refunded_eligible = Decimal(str(refunded_result.scalar_one() or 0))

        cfg = await get_earning_config(self.db)
        remaining_eligible = max(Decimal("0"), eligible_original - refunded_eligible)
        justified_points = points_to_credit(
            float(remaining_eligible), cfg.euro_per_point
        )
        total_should_reverse = max(0, int(earn.points) - justified_points)
        reversed_result = await self.db.execute(
            select(func.coalesce(func.sum(LoyaltyTransaction.points), 0)).where(
                LoyaltyTransaction.reversal_of_id == earn.id,
                LoyaltyTransaction.tx_type == LoyaltyTxType.adjust,
            )
        )
        already_reversed = abs(int(reversed_result.scalar_one() or 0))
        to_reverse = max(0, total_should_reverse - already_reversed)
        if to_reverse <= 0:
            return

        before = int(account.points or 0)
        account.points = before - to_reverse
        self.db.add(LoyaltyTransaction(
            account_id=account.id,
            tx_type=LoyaltyTxType.adjust,
            points=-to_reverse,
            description=f"Retour #{refund_tx.transaction_number}",
            transaction_id=refund_tx.id,
            reversal_of_id=earn.id,
        ))

        # Sémantique « débit à l'émission » : les points d'un palier sont
        # consommés quand le chèque est émis. Si l'annulation des points de la
        # vente rend le solde négatif, le déficit correspond à des points déjà
        # convertis en chèque(s) : on révoque les chèques non utilisés (et on
        # re-crédite leur palier). Un chèque déjà dépensé n'est pas révocable —
        # le solde reste alors en dette (négatif), soldée par les prochains
        # achats.
        if account.points >= 0:
            return
        threshold = max(1, int(cfg.voucher_threshold or 100))
        deficit_vouchers = (-account.points + threshold - 1) // threshold
        revocable = (
            await self.db.execute(
                select(Coupon)
                .where(
                    Coupon.client_id == original.client_id,
                    Coupon.source == CouponSource.loyalty_milestone,
                    Coupon.is_active.is_(True),
                    Coupon.redeemed_at.is_(None),
                )
                .order_by(Coupon.created_at.desc())
                .limit(deficit_vouchers)
                .with_for_update()
            )
        ).scalars().all()
        for coupon in revocable:
            coupon.is_active = False
            suffix = f"Annulé suite retour #{refund_tx.transaction_number}"
            coupon.notes = f"{coupon.notes or ''} · {suffix}".strip(" ·")
            account.points += threshold
            # ``reversal_of_id`` reste vide : cette ligne annule l'émission du
            # chèque, pas l'earn de la vente — la lier à l'earn fausserait le
            # cumul ``already_reversed`` (garde d'idempotence ci-dessus).
            self.db.add(LoyaltyTransaction(
                account_id=account.id,
                tx_type=LoyaltyTxType.adjust,
                points=threshold,
                description=(
                    f"Chèque fidélité {coupon.code} révoqué — retour "
                    f"#{refund_tx.transaction_number}"
                ),
                transaction_id=refund_tx.id,
            ))

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
