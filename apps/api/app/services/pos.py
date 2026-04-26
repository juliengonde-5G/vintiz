import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import (
    CashDrawer,
    Payment,
    PaymentMethod,
    Transaction,
    TransactionItem,
    TransactionType,
)
from app.models.product import Product, ProductStatus


class PosService:
    """Business logic for point-of-sale operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    async def create_transaction(
        self,
        user_id: uuid.UUID,
        items: list,
        payments: list,
        client_id: uuid.UUID | None = None,
        cashier_id: uuid.UUID | None = None,
    ) -> Transaction:
        """Create a sale transaction.

        Supports two kinds of cart items:
        - Product items: have product_id → validates product, marks as sold
        - Manual items: no product_id, just name + unit_price (e.g. sac)

        Applies discount_percent per item if provided.
        """
        if not items:
            raise HTTPException(status_code=400, detail="Cart is empty")

        total_ttc = Decimal("0")
        # (product | None, quantity, unit_price, discount_percent, item_name)
        line_rows: list[tuple[Product | None, int, Decimal, float, str]] = []

        for cart_item in items:
            if cart_item.product_id:
                result = await self.db.execute(
                    select(Product).where(Product.id == cart_item.product_id)
                )
                product = result.scalar_one_or_none()
                if product is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Product {cart_item.product_id} not found",
                    )
                if product.status not in (ProductStatus.display, ProductStatus.stock):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Product {product.name} is not available for sale (status: {product.status.value})",
                    )
                unit_price = Decimal(str(cart_item.unit_price)) if cart_item.unit_price else Decimal(str(product.sale_price))
                discount = cart_item.discount_percent or 0
                line_total = (unit_price * cart_item.quantity * (Decimal("100") - Decimal(str(discount))) / Decimal("100")).quantize(Decimal("0.01"))
                total_ttc += line_total
                line_rows.append((product, cart_item.quantity, unit_price, discount, product.name))
            else:
                # Manual item (e.g. sac)
                if not cart_item.name or not cart_item.unit_price:
                    raise HTTPException(
                        status_code=400,
                        detail="Manual items require name and unit_price",
                    )
                unit_price = Decimal(str(cart_item.unit_price))
                discount = cart_item.discount_percent or 0
                line_total = (unit_price * cart_item.quantity * (Decimal("100") - Decimal(str(discount))) / Decimal("100")).quantize(Decimal("0.01"))
                total_ttc += line_total
                line_rows.append((None, cart_item.quantity, unit_price, discount, cart_item.name))

        # TVA 20 %: HT = TTC / 1.20, TVA = TTC - HT
        total_ht = (total_ttc / Decimal("1.20")).quantize(Decimal("0.01"))
        total_tva = (total_ttc - total_ht).quantize(Decimal("0.01"))

        # Validate payments
        total_paid = sum(Decimal(str(p.amount)) for p in payments)
        if total_paid < total_ttc:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient payment: {total_paid} < {total_ttc}",
            )

        # Generate transaction number
        max_num_result = await self.db.execute(
            select(func.coalesce(func.max(Transaction.transaction_number), 0))
        )
        next_number = max_num_result.scalar_one() + 1

        transaction = Transaction(
            transaction_number=next_number,
            transaction_type=TransactionType.sale,
            user_id=user_id,
            cashier_id=cashier_id,
            client_id=client_id,
            total_ht=float(total_ht),
            total_tva=float(total_tva),
            total_ttc=float(total_ttc),
            hash_chain="",  # will be set by FiscalService
        )
        self.db.add(transaction)
        await self.db.flush()

        # Create transaction items
        for product, quantity, unit_price, discount, _name in line_rows:
            line_total = (unit_price * quantity * (Decimal("100") - Decimal(str(discount))) / Decimal("100")).quantize(Decimal("0.01"))
            item = TransactionItem(
                transaction_id=transaction.id,
                product_id=product.id if product else None,
                quantity=quantity,
                unit_price=float(unit_price),
                discount_percent=discount,
                line_total=float(line_total),
            )
            self.db.add(item)

            # Mark product as sold (only real products)
            if product:
                product.status = ProductStatus.sold
                product.sold_at = datetime.now(timezone.utc).isoformat()

        # Create payment records
        method_map = {"especes": "cash", "carte": "card", "cheque": "cheque",
                      "cash": "cash", "card": "card"}
        for pay in payments:
            method_str = method_map.get(pay.method, pay.method)
            payment = Payment(
                transaction_id=transaction.id,
                method=PaymentMethod(method_str),
                amount=float(pay.amount),
            )
            self.db.add(payment)

        await self.db.flush()
        await self.db.refresh(transaction)
        return transaction

    async def list_transactions(
        self, skip: int = 0, limit: int = 50
    ) -> list[dict]:
        """Return a paginated list of transactions."""
        result = await self.db.execute(
            select(Transaction)
            .order_by(Transaction.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        transactions = result.scalars().all()
        return [
            {
                "id": str(t.id),
                "transaction_number": t.transaction_number,
                "transaction_type": t.transaction_type.value,
                "total_ttc": float(t.total_ttc),
                "total_ht": float(t.total_ht),
                "total_tva": float(t.total_tva),
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "item_count": len(t.items) if t.items else 0,
            }
            for t in transactions
        ]

    async def get_transaction(self, transaction_id: uuid.UUID) -> dict | None:
        """Return a single transaction with items, payments, and client info."""
        from app.models.client import Client
        result = await self.db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        t = result.scalar_one_or_none()
        if t is None:
            return None

        # Build product name map for items that have a product_id
        product_ids = [item.product_id for item in (t.items or []) if item.product_id]
        product_names: dict[str, str] = {}
        if product_ids:
            prod_result = await self.db.execute(
                select(Product.id, Product.name).where(Product.id.in_(product_ids))
            )
            for pid, pname in prod_result.all():
                product_names[str(pid)] = pname

        # Load client if present
        client_data = None
        if t.client_id:
            c_result = await self.db.execute(
                select(Client).where(Client.id == t.client_id)
            )
            client = c_result.scalar_one_or_none()
            if client:
                client_data = {
                    "id": str(client.id),
                    "first_name": client.first_name,
                    "last_name": client.last_name,
                    "email": client.email,
                    "phone": client.phone,
                }

        return {
            "id": str(t.id),
            "transaction_number": t.transaction_number,
            "type": t.transaction_type.value,
            "total_ttc": float(t.total_ttc),
            "total_ht": float(t.total_ht),
            "tax_amount": float(t.total_tva),
            "hash_chain": t.hash_chain,
            "cashier_id": str(t.cashier_id) if t.cashier_id else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "client": client_data,
            "items": [
                {
                    "id": str(item.id),
                    "product_id": str(item.product_id) if item.product_id else None,
                    "name": product_names.get(str(item.product_id), "Article") if item.product_id else "Article",
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price),
                    "discount_percent": float(item.discount_percent),
                    "line_total": float(item.line_total),
                }
                for item in (t.items or [])
            ],
            "payments": [
                {
                    "id": str(p.id),
                    "method": p.method.value,
                    "amount": float(p.amount),
                }
                for p in (t.payments or [])
            ],
        }

    # ------------------------------------------------------------------
    # Cash Drawer
    # ------------------------------------------------------------------

    async def open_drawer(
        self,
        user_id: uuid.UUID,
        opening_amount: Decimal,
        cashier_id: uuid.UUID | None = None,
    ) -> CashDrawer:
        """Open a new cash drawer. Raises if one is already open."""
        existing = await self.get_open_drawer()
        if existing:
            raise HTTPException(
                status_code=400, detail="A cash drawer is already open"
            )
        drawer = CashDrawer(
            user_id=user_id,
            cashier_id=cashier_id,
            opened_at=datetime.now(timezone.utc),
            opening_amount=float(opening_amount),
            is_open=True,
        )
        self.db.add(drawer)
        await self.db.flush()
        await self.db.refresh(drawer)
        return drawer

    async def close_drawer(
        self,
        user_id: uuid.UUID,
        closing_amount: Decimal,
        cashier_id: uuid.UUID | None = None,
    ) -> CashDrawer:
        """Close the currently open drawer.

        Computes *expected_amount* as opening_amount + sum of cash payments
        made while the drawer was open. If a cashier_id is supplied, it
        replaces the one set at opening (e.g. shift handover).
        """
        drawer = await self.get_open_drawer()
        if not drawer:
            raise HTTPException(
                status_code=400, detail="No open cash drawer found"
            )
        if cashier_id is not None:
            drawer.cashier_id = cashier_id

        # Sum cash payments during the drawer period
        cash_sum_result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .join(Transaction, Payment.transaction_id == Transaction.id)
            .where(
                Payment.method == PaymentMethod.cash,
                Transaction.created_at >= drawer.opened_at,
            )
        )
        cash_total = Decimal(str(cash_sum_result.scalar_one()))

        drawer.closing_amount = float(closing_amount)
        drawer.expected_amount = float(
            Decimal(str(drawer.opening_amount)) + cash_total
        )
        drawer.closed_at = datetime.now(timezone.utc)
        drawer.is_open = False

        await self.db.flush()
        await self.db.refresh(drawer)
        return drawer

    async def get_open_drawer(self) -> CashDrawer | None:
        """Return the currently open cash drawer, or None."""
        result = await self.db.execute(
            select(CashDrawer).where(CashDrawer.is_open.is_(True)).limit(1)
        )
        return result.scalar_one_or_none()
