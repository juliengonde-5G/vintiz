"""Reporting espèces — anticipation COSI TRACFIN (audit C11).

L'article L.561-15-1 du Code monétaire et financier impose à la banque
de Vintiz de déclarer automatiquement (COSI) tout dépôt ou retrait
d'espèces > 10 000 € cumulés sur un mois calendaire. Vintiz doit donc
**anticiper** ces déclarations en :

1. Connaissant son volume mensuel d'encaissements espèces
2. Pouvant fournir un dossier permanent à la banque sur demande
3. Justifiant chaque mois les Z reports + cash_movements (dépôts banque)

Ce service expose un agrégat mensuel des paiements espèces à la frontière
admin uniquement (manager only), sans modifier les données fiscales.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cash_movement import (
    CashMovement,
    CashMovementDirection,
    CashMovementReason,
)
from app.models.pos import Payment, PaymentMethod, Transaction


COSI_THRESHOLD_EUR = Decimal("10000")


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """Borne UTC d'un mois calendaire."""
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


async def cash_volume_for_month(
    db: AsyncSession, *, year: int, month: int
) -> dict:
    """Retourne l'agrégat mensuel des flux espèces.

    Distingue :
    - **encaissements espèces** (Payment.method=cash sur transactions sale)
    - **remboursements espèces** (Payment.method=cash sur refund)
    - **dépôts banque** (CashMovement reason=bank_deposit, direction=outflow)
    - **prélèvements / autres** (cash_movements direction=outflow autres reason)
    - **alimentations fond de caisse** (cash_movements direction=inflow)

    Le **net mensuel** = sales_cash − refunds_cash − bank_deposits.

    Returns :
        {
          "year": ...,
          "month": ...,
          "period": {"from": ISO, "to": ISO},
          "sales_cash_eur": float,
          "refunds_cash_eur": float,
          "bank_deposits_eur": float,
          "other_outflow_eur": float,
          "inflow_eur": float,
          "net_eur": float,
          "cosi_threshold_eur": 10000.0,
          "above_cosi_threshold": bool,
          "alert_message": str | None,
        }
    """
    start, end = _month_bounds(year, month)

    # Sales cash : Payment.method=cash où la transaction parente est sale
    sales_cash_q = (
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Transaction, Transaction.id == Payment.transaction_id)
        .where(
            Payment.method == PaymentMethod.cash,
            Transaction.transaction_type == "sale",
            Transaction.created_at >= start,
            Transaction.created_at < end,
        )
    )
    refunds_cash_q = (
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Transaction, Transaction.id == Payment.transaction_id)
        .where(
            Payment.method == PaymentMethod.cash,
            Transaction.transaction_type == "refund",
            Transaction.created_at >= start,
            Transaction.created_at < end,
        )
    )

    sales_cash = Decimal(str((await db.execute(sales_cash_q)).scalar() or 0))
    refunds_cash = Decimal(str((await db.execute(refunds_cash_q)).scalar() or 0))

    # Cash movements
    deposits_q = select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
        CashMovement.direction == CashMovementDirection.outflow,
        CashMovement.reason == CashMovementReason.bank_deposit,
        CashMovement.created_at >= start,
        CashMovement.created_at < end,
    )
    other_outflow_q = select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
        CashMovement.direction == CashMovementDirection.outflow,
        CashMovement.reason != CashMovementReason.bank_deposit,
        CashMovement.created_at >= start,
        CashMovement.created_at < end,
    )
    inflow_q = select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
        CashMovement.direction == CashMovementDirection.inflow,
        CashMovement.created_at >= start,
        CashMovement.created_at < end,
    )

    deposits = Decimal(str((await db.execute(deposits_q)).scalar() or 0))
    other_outflow = Decimal(str((await db.execute(other_outflow_q)).scalar() or 0))
    inflow = Decimal(str((await db.execute(inflow_q)).scalar() or 0))

    net = sales_cash - refunds_cash - deposits

    # Critère COSI : dépôt mensuel > 10 000 € (le critère de la banque
    # déclencheur). On flag aussi les sales_cash > 10 000 € comme alerte
    # interne — montant à anticiper d'être déposé.
    above_threshold = (
        deposits >= COSI_THRESHOLD_EUR or sales_cash >= COSI_THRESHOLD_EUR
    )
    alert: str | None = None
    if deposits >= COSI_THRESHOLD_EUR:
        alert = (
            f"Dépôts banque {float(deposits):.2f} € ≥ 10 000 € — la banque "
            "déclenchera une COSI TRACFIN automatique. Tenir le dossier "
            "permanent à disposition (Z reports + cash_movements)."
        )
    elif sales_cash >= COSI_THRESHOLD_EUR:
        alert = (
            f"Encaissements espèces {float(sales_cash):.2f} € ≥ 10 000 € sur "
            "le mois. Anticiper les dépôts banque échelonnés et conserver "
            "les Z reports."
        )

    return {
        "year": year,
        "month": month,
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "sales_cash_eur": float(sales_cash),
        "refunds_cash_eur": float(refunds_cash),
        "bank_deposits_eur": float(deposits),
        "other_outflow_eur": float(other_outflow),
        "inflow_eur": float(inflow),
        "net_eur": float(net),
        "cosi_threshold_eur": float(COSI_THRESHOLD_EUR),
        "above_cosi_threshold": above_threshold,
        "alert_message": alert,
    }


async def cash_volume_last_n_months(
    db: AsyncSession, *, n_months: int = 12, today: date | None = None
) -> list[dict]:
    """12 derniers mois par défaut, agrégat mensuel.

    Utile pour le dashboard admin et le dossier permanent banque.
    """
    today = today or datetime.now(timezone.utc).date()
    out: list[dict] = []
    cur_y, cur_m = today.year, today.month
    for _ in range(max(1, n_months)):
        agg = await cash_volume_for_month(db, year=cur_y, month=cur_m)
        out.append(agg)
        # Mois précédent
        if cur_m == 1:
            cur_m = 12
            cur_y -= 1
        else:
            cur_m -= 1
    return list(reversed(out))  # ordre chronologique ascendant
