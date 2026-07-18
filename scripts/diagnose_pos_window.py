#!/usr/bin/env python3
"""Diagnostic read-only : reconstitue tout ce qui s'est passé côté POS/CB
dans une fenêtre horaire donnée (heure de Paris).

Croise 5 sources et imprime une chronologie fusionnée :
  - ``payment_attempts``   chaque paiement initié (CB, espèces…), son statut,
                           son erreur et s'il a fini rattaché à une vente
  - ``sumup_exchanges``    chaque appel HTTP vers api.sumup.com (payload rédigé)
  - ``transactions``       les ventes réellement commitées (+ moyens de paiement)
  - ``audit_logs``         créations/updates tracées (dont cash_cap_override)
  - ``events_log``         events analytics (product.sold, customer.visited…)

Termine par un verdict : les tentatives CB payées/initiées qui n'ont JAMAIS
été rattachées à une transaction (= paiement OK, vente non validée).

Usage (heure locale Europe/Paris) :
    PYTHONPATH=apps/api python scripts/diagnose_pos_window.py \
        --from "2026-07-17 11:00" --to "2026-07-17 11:35"

    # En prod
    docker exec -it vintiz-api python scripts/diagnose_pos_window.py \
        --from "2026-07-17 11:00" --to "2026-07-17 11:35"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Rendre ``import app.core...`` fonctionnel en dev ET en Docker (/app).
_HERE = Path(__file__).resolve()
for _candidate in (
    _HERE.parents[1] / "apps" / "api",   # layout dev (repo)
    _HERE.parents[1],                    # layout Docker prod (/app)
):
    if (_candidate / "app" / "core" / "database.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    raise SystemExit(
        "diagnose_pos_window: package `app` introuvable — vérifié "
        f"{_HERE.parents[1] / 'apps' / 'api'} et {_HERE.parents[1]}"
    )

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402
from app.models.events import EventLog  # noqa: E402
from app.models.payment_attempt import PaymentAttempt  # noqa: E402
from app.models.pos import Payment, Transaction  # noqa: E402
from app.models.sumup_exchange import SumUpExchange  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
UTC = ZoneInfo("UTC")


def _parse_local(value: str, label: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=PARIS)
        except ValueError:
            continue
    raise SystemExit(f"--{label} : format attendu 'YYYY-MM-DD HH:MM' (heure de Paris)")


def _local(dt: datetime | None) -> str:
    if dt is None:
        return "        ?       "
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(PARIS).strftime("%H:%M:%S")


async def run(start_local: datetime, end_local: datetime) -> None:
    start, end = start_local.astimezone(UTC), end_local.astimezone(UTC)
    print(
        f"Fenêtre : {start_local:%d/%m/%Y %H:%M} → {end_local:%H:%M} (Paris) "
        f"= {start:%H:%M} → {end:%H:%M} UTC\n"
    )

    timeline: list[tuple[datetime, str]] = []

    async with async_session() as db:
        attempts = (
            (
                await db.execute(
                    select(PaymentAttempt)
                    .where(
                        PaymentAttempt.created_at >= start,
                        PaymentAttempt.created_at <= end,
                    )
                    .order_by(PaymentAttempt.created_at)
                )
            )
            .scalars()
            .all()
        )
        for a in attempts:
            linked = f"→ vente {a.transaction_id}" if a.transaction_id else "→ AUCUNE VENTE"
            timeline.append((
                a.created_at,
                f"[TENTATIVE] {a.method.value:>7} {float(a.amount):8.2f} €  "
                f"statut={a.status.value:<9} {linked}"
                + (f"  checkout={a.sumup_checkout_id}" if a.sumup_checkout_id else "")
                + (f"  intent={a.foreign_transaction_id}" if a.foreign_transaction_id else "")
                + (f"\n              erreur: {a.error_detail}" if a.error_detail else "")
                + (f"\n              annulée: {a.cancelled_reason}" if a.cancelled_reason else ""),
            ))

        exchanges = (
            (
                await db.execute(
                    select(SumUpExchange)
                    .where(
                        SumUpExchange.created_at >= start,
                        SumUpExchange.created_at <= end,
                    )
                    .order_by(SumUpExchange.created_at)
                )
            )
            .scalars()
            .all()
        )
        for x in exchanges:
            flag = "OK " if x.ok else "ERR"
            timeline.append((
                x.created_at,
                f"[SUMUP {flag}] {x.operation:<20} http={x.http_status} "
                + (f"type={x.error_type} " if x.error_type else "")
                + (f"mode={x.mode} " if getattr(x, 'mode', None) else "")
                + (f"checkout={x.checkout_id} " if x.checkout_id else "")
                + (f"retries={x.retry_count} " if getattr(x, 'retry_count', 0) else "")
                + (f"\n              réponse: {x.response_summary}" if x.response_summary else "")
                + (f"\n              erreur: {x.error}" if getattr(x, 'error', None) else ""),
            ))

        txs = (
            (
                await db.execute(
                    select(Transaction)
                    .where(
                        Transaction.created_at >= start,
                        Transaction.created_at <= end,
                    )
                    .order_by(Transaction.created_at)
                )
            )
            .scalars()
            .all()
        )
        for t in txs:
            pays = (
                (
                    await db.execute(
                        select(Payment).where(Payment.transaction_id == t.id)
                    )
                )
                .scalars()
                .all()
            )
            pay_str = ", ".join(f"{p.method.value} {float(p.amount):.2f} €" for p in pays)
            timeline.append((
                t.created_at,
                f"[VENTE OK ] #{t.transaction_number}  {float(t.total_ttc):8.2f} €  "
                f"({t.transaction_type.value})  paiements: {pay_str or '—'}  id={t.id}",
            ))

        audits = (
            (
                await db.execute(
                    select(AuditLog)
                    .where(AuditLog.created_at >= start, AuditLog.created_at <= end)
                    .order_by(AuditLog.created_at)
                )
            )
            .scalars()
            .all()
        )
        for g in audits:
            timeline.append((
                g.created_at,
                f"[AUDIT    ] {g.action} {g.entity} id={g.entity_id} data={g.data}",
            ))

        events = (
            (
                await db.execute(
                    select(EventLog)
                    .where(EventLog.occurred_at >= start, EventLog.occurred_at <= end)
                    .order_by(EventLog.occurred_at)
                )
            )
            .scalars()
            .all()
        )
        for e in events:
            timeline.append((
                e.occurred_at,
                f"[EVENT    ] {e.event_type.value} (source={e.source.value}) "
                f"tx={e.transaction_id} produit={e.product_id}",
            ))

    if not timeline:
        print("Aucune activité trouvée dans cette fenêtre.")
        return

    def _key(item: tuple[datetime, str]) -> datetime:
        dt = item[0]
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

    print("─" * 100)
    for dt, line in sorted(timeline, key=_key):
        print(f"{_local(dt)}  {line}")
    print("─" * 100)

    orphans = [
        a for a in attempts
        if a.transaction_id is None and a.status.value in ("pending", "succeeded")
    ]
    if orphans:
        print("\n⚠️  Tentatives de paiement SANS vente rattachée (paiement initié/OK, vente non validée) :")
        for a in orphans:
            print(
                f"  - {_local(a.created_at)}  {a.method.value} {float(a.amount):.2f} € "
                f"statut={a.status.value} checkout={a.sumup_checkout_id} "
                f"intent={a.foreign_transaction_id}"
            )
        print(
            "\n  → Pour chacune : chercher dans la chronologie ci-dessus le get_checkout_status"
            "\n    SumUp au même moment, puis la ligne de log API (docker logs vintiz-api)"
            "\n    autour de la même seconde pour lire le 400/409 exact renvoyé à la caisse."
        )
    else:
        print("\nAucune tentative orpheline : tous les paiements de la fenêtre sont rattachés à une vente.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chronologie POS/CB sur une fenêtre horaire (read-only)"
    )
    parser.add_argument("--from", dest="start", required=True, help="Début, heure de Paris (YYYY-MM-DD HH:MM)")
    parser.add_argument("--to", dest="end", required=True, help="Fin, heure de Paris (YYYY-MM-DD HH:MM)")
    args = parser.parse_args()
    asyncio.run(run(_parse_local(args.start, "from"), _parse_local(args.end, "to")))


if __name__ == "__main__":
    main()
