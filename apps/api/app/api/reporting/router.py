from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Product, ProductStatus
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["reporting"])


@router.get("/daily")
async def daily_report(
    report_date: date = Query(default=None, alias="date", description="Date YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Daily report: revenue, transaction count, avg basket, top products."""
    if report_date is None:
        report_date = date.today()

    day_start = datetime.combine(report_date, datetime.min.time())
    day_end = datetime.combine(report_date + timedelta(days=1), datetime.min.time())

    # Revenue and count
    result = await db.execute(
        select(
            func.coalesce(func.sum(Transaction.total_ttc), 0),
            func.count(Transaction.id),
        ).where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    row = result.one()
    total_revenue = float(row[0])
    transaction_count = row[1]
    avg_basket = total_revenue / transaction_count if transaction_count > 0 else 0

    # Refunds
    refund_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.total_ttc), 0)).where(
            Transaction.transaction_type == TransactionType.refund,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    total_refunds = float(refund_result.scalar_one())

    # Top products (by number of times sold)
    top_result = await db.execute(
        select(
            Product.name,
            func.sum(TransactionItem.quantity).label("qty"),
            func.sum(TransactionItem.line_total).label("revenue"),
        )
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .where(
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
            Transaction.transaction_type == TransactionType.sale,
        )
        .group_by(Product.id, Product.name)
        .order_by(func.sum(TransactionItem.line_total).desc())
        .limit(10)
    )
    top_products = [
        {"name": r[0], "quantity": int(r[1]), "revenue": float(r[2])}
        for r in top_result.all()
    ]

    return {
        "date": report_date.isoformat(),
        "total_revenue": total_revenue,
        "total_refunds": total_refunds,
        "net_revenue": total_revenue - total_refunds,
        "transaction_count": transaction_count,
        "avg_basket": round(avg_basket, 2),
        "top_products": top_products,
    }


@router.get("/weekly")
async def weekly_report(
    week: int = Query(..., ge=1, le=53, description="ISO week number"),
    year: int = Query(..., ge=2020, description="Year"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Weekly summary report."""
    # Compute the Monday of the given ISO week
    jan4 = date(year, 1, 4)
    start_of_week1 = jan4 - timedelta(days=jan4.weekday())
    week_start = start_of_week1 + timedelta(weeks=week - 1)
    week_end = week_start + timedelta(days=7)

    day_start = datetime.combine(week_start, datetime.min.time())
    day_end = datetime.combine(week_end, datetime.min.time())

    result = await db.execute(
        select(
            func.coalesce(func.sum(Transaction.total_ttc), 0),
            func.count(Transaction.id),
        ).where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    row = result.one()
    total_revenue = float(row[0])
    transaction_count = row[1]
    avg_basket = total_revenue / transaction_count if transaction_count > 0 else 0

    refund_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.total_ttc), 0)).where(
            Transaction.transaction_type == TransactionType.refund,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    total_refunds = float(refund_result.scalar_one())

    return {
        "week": week,
        "year": year,
        "week_start": week_start.isoformat(),
        "week_end": (week_end - timedelta(days=1)).isoformat(),
        "total_revenue": total_revenue,
        "total_refunds": total_refunds,
        "net_revenue": total_revenue - total_refunds,
        "transaction_count": transaction_count,
        "avg_basket": round(avg_basket, 2),
    }


@router.get("/monthly")
async def monthly_report(
    month: int = Query(..., ge=1, le=12, description="Month number"),
    year: int = Query(..., ge=2020, description="Year"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Monthly summary report."""
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)

    day_start = datetime.combine(month_start, datetime.min.time())
    day_end = datetime.combine(month_end, datetime.min.time())

    result = await db.execute(
        select(
            func.coalesce(func.sum(Transaction.total_ttc), 0),
            func.count(Transaction.id),
        ).where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    row = result.one()
    total_revenue = float(row[0])
    transaction_count = row[1]
    avg_basket = total_revenue / transaction_count if transaction_count > 0 else 0

    refund_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.total_ttc), 0)).where(
            Transaction.transaction_type == TransactionType.refund,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    total_refunds = float(refund_result.scalar_one())

    return {
        "month": month,
        "year": year,
        "total_revenue": total_revenue,
        "total_refunds": total_refunds,
        "net_revenue": total_revenue - total_refunds,
        "transaction_count": transaction_count,
        "avg_basket": round(avg_basket, 2),
    }


@router.get("/stock-value")
async def stock_value_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current stock valuation at purchase price and at sale price."""
    # Products in stock or on display (not sold/returned)
    result = await db.execute(
        select(
            func.count(Product.id),
            func.coalesce(func.sum(Product.purchase_price), 0),
            func.coalesce(func.sum(Product.sale_price), 0),
        ).where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display])
        )
    )
    row = result.one()
    product_count = row[0]
    total_purchase_value = float(row[1])
    total_sale_value = float(row[2])

    # Breakdown by status
    stock_result = await db.execute(
        select(
            func.count(Product.id),
            func.coalesce(func.sum(Product.purchase_price), 0),
            func.coalesce(func.sum(Product.sale_price), 0),
        ).where(Product.status == ProductStatus.stock)
    )
    stock_row = stock_result.one()

    display_result = await db.execute(
        select(
            func.count(Product.id),
            func.coalesce(func.sum(Product.purchase_price), 0),
            func.coalesce(func.sum(Product.sale_price), 0),
        ).where(Product.status == ProductStatus.display)
    )
    display_row = display_result.one()

    return {
        "total_products": product_count,
        "total_purchase_value": total_purchase_value,
        "total_sale_value": total_sale_value,
        "potential_margin": total_sale_value - total_purchase_value,
        "breakdown": {
            "stock": {
                "count": stock_row[0],
                "purchase_value": float(stock_row[1]),
                "sale_value": float(stock_row[2]),
            },
            "display": {
                "count": display_row[0],
                "purchase_value": float(display_row[1]),
                "sale_value": float(display_row[2]),
            },
        },
    }
