from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import CashDrawer, Payment, PaymentMethod, Transaction


class CashDrawerService:
    """Helpers for cash-drawer management and reporting."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def calculate_expected(self, drawer: CashDrawer) -> Decimal:
        """Compute the expected cash amount in the drawer.

        expected = opening_amount + sum(cash payments while drawer was open)
        """
        result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .join(Transaction, Payment.transaction_id == Transaction.id)
            .where(
                Payment.method == PaymentMethod.cash,
                Transaction.created_at >= drawer.opened_at,
            )
        )
        cash_total = Decimal(str(result.scalar_one()))
        return Decimal(str(drawer.opening_amount)) + cash_total

    async def get_summary(self, drawer: CashDrawer) -> dict:
        """Return a summary dict for a cash drawer.

        Keys: opening, expected, closing, difference.
        """
        expected = await self.calculate_expected(drawer)
        closing = Decimal(str(drawer.closing_amount)) if drawer.closing_amount is not None else None
        difference = (closing - expected) if closing is not None else None

        return {
            "drawer_id": str(drawer.id),
            "opening": float(drawer.opening_amount),
            "expected": float(expected),
            "closing": float(closing) if closing is not None else None,
            "difference": float(difference) if difference is not None else None,
            "is_open": drawer.is_open,
        }
