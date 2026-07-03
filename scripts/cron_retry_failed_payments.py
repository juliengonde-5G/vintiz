#!/usr/bin/env python3
"""Cron — réessai automatique des paiements CB échoués.

Rejoue chaque ``FailedPayment`` échu (recouvrable, ``next_retry_at`` passé) en
recréant un checkout **en mode lien de paiement** (jamais un push TPE : personne
n'est à la caisse au moment du réessai). Les succès passent en ``succeeded``,
les rows épuisées en ``exhausted`` ; tout est audité en base.

Le backend planifie déjà ce travail via APScheduler (job ``retry_failed_payments``
toutes les 5 min). Ce script existe pour un déclenchement **externe** (cron
système / one-shot ops) indépendant du process API :

    # crontab — toutes les 5 minutes
    */5 * * * * PYTHONPATH=apps/api python scripts/cron_retry_failed_payments.py \
        >> /var/log/vintiz/retry_failed_payments.log 2>&1

En Docker :
    docker exec -it vintiz-api python scripts/cron_retry_failed_payments.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Rendre ``import app.*`` fonctionnel en dev ET en Docker (même bootstrap que
# go_live_reset.py).
_HERE = Path(__file__).resolve()
for _candidate in (
    _HERE.parents[1] / "apps" / "api",   # layout dev (repo)
    _HERE.parents[1],                    # layout Docker prod (/app)
):
    if (_candidate / "app" / "core" / "database.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:  # pragma: no cover
    raise SystemExit(
        "cron_retry_failed_payments: impossible de localiser le package `app`"
    )

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.database import engine  # noqa: E402
from app.services.failed_payment_service import FailedPaymentService  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
_log = logging.getLogger("retry_failed_payments")


async def main() -> int:
    async with AsyncSession(engine) as db:
        service = FailedPaymentService()
        results = await service.retry_failed_payments(db)

    succeeded = sum(1 for r in results if r.get("status") == "SUCCESS")
    exhausted = sum(1 for r in results if r.get("status") == "EXHAUSTED")
    failed = sum(1 for r in results if r.get("status") == "FAILED")
    if not results:
        _log.info("Aucun paiement échoué à réessayer.")
    else:
        _log.info(
            "Réessai terminé : %d traités (%d réussis, %d encore en échec, %d épuisés)",
            len(results), succeeded, failed, exhausted,
        )
        for r in results:
            if r.get("status") == "SUCCESS":
                _log.info(
                    "  ✓ %s → checkout %s",
                    r["failed_payment_id"], r.get("checkout_id"),
                )
            else:
                _log.warning(
                    "  ✗ %s [%s] %s",
                    r["failed_payment_id"], r.get("status"),
                    r.get("error") or r.get("reason") or "",
                )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
