"""Top clients par chiffre d'affaires — page Clients du back-office.

Classement des meilleures clientes sur une période calendaire boutique
(jour / semaine / mois / année, bornée en Europe/Paris comme le cahier du
jour). Le CA d'une cliente = somme des ventes rattachées à sa fiche moins
les remboursements de la période (mêmes conventions que /api/reports/daily :
les refunds sont des transactions séparées à total positif). Les ventes
anonymes (client_id NULL) et les transactions ``void`` sont hors classement.

Partagé par les deux endpoints CRM (tableau JSON + export CSV) pour que le
fichier téléchargé soit toujours identique à l'écran.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, LoyaltyAccount
from app.models.pos import Transaction, TransactionType
from app.services.cahier_service import EUROPE_PARIS

PERIODS = ("day", "week", "month", "year")


def period_start(period: str, *, now: datetime | None = None) -> datetime:
    """Début (aware Europe/Paris) de la période calendaire courante.

    day = aujourd'hui 00:00 ; week = lundi 00:00 ; month = le 1er 00:00 ;
    year = 1er janvier 00:00. asyncpg convertit l'aware en UTC pour la
    comparaison à ``Transaction.created_at`` (TIMESTAMPTZ).
    """
    if period not in PERIODS:
        raise ValueError(f"Période inconnue: {period!r}")
    now = now.astimezone(EUROPE_PARIS) if now else datetime.now(EUROPE_PARIS)
    today = now.date()
    if period == "day":
        start_date = today
    elif period == "week":
        start_date = today - timedelta(days=today.weekday())
    elif period == "month":
        start_date = today.replace(day=1)
    else:  # year
        start_date = today.replace(month=1, day=1)
    return datetime.combine(start_date, time.min, tzinfo=EUROPE_PARIS)


async def top_clients(
    db: AsyncSession,
    *,
    period: str = "month",
    limit: int = 10,
    now: datetime | None = None,
) -> dict:
    """Classement des ``limit`` plus grosses clientes de la période."""
    start = period_start(period, now=now)

    revenue = func.coalesce(
        func.sum(
            case(
                (
                    Transaction.transaction_type == TransactionType.sale,
                    Transaction.total_ttc,
                ),
                (
                    Transaction.transaction_type == TransactionType.refund,
                    -Transaction.total_ttc,
                ),
                else_=0,
            )
        ),
        0,
    ).label("revenue")
    sales_count = func.sum(
        case((Transaction.transaction_type == TransactionType.sale, 1), else_=0)
    ).label("sales_count")

    stmt = (
        select(
            Client.id,
            Client.first_name,
            Client.last_name,
            LoyaltyAccount.points,
            LoyaltyAccount.membership_number,
            revenue,
            sales_count,
        )
        .join(Transaction, Transaction.client_id == Client.id)
        .outerjoin(LoyaltyAccount, LoyaltyAccount.client_id == Client.id)
        .where(
            Transaction.transaction_type.in_(
                [TransactionType.sale, TransactionType.refund]
            ),
            Transaction.created_at >= start,
        )
        .group_by(
            Client.id,
            Client.first_name,
            Client.last_name,
            LoyaltyAccount.points,
            LoyaltyAccount.membership_number,
        )
        .order_by(desc("revenue"), Client.last_name.asc(), Client.first_name.asc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    return {
        "period": period,
        "start": start.isoformat(),
        "limit": limit,
        "count": len(rows),
        "results": [
            {
                "rank": i,
                "client_id": str(r.id),
                "membership_number": r.membership_number,
                "loyalty_active": r.points is not None,
                "loyalty_points": r.points or 0,
                "first_name": r.first_name,
                "last_name": r.last_name,
                "revenue": round(float(r.revenue or 0), 2),
                "transactions_count": int(r.sales_count or 0),
            }
            for i, r in enumerate(rows, start=1)
        ],
    }
