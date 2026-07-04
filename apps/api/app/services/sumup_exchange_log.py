"""Persist + prune the SumUp API exchange diagnostic log.

``SumUpService`` buffers a redacted record for every HTTP call it makes
(see ``SumUpService._send``). The CB endpoints call
:func:`persist_sumup_exchanges` right after talking to SumUp to flush that
buffer into the ``sumup_exchanges`` table — giving the back-office an
authoritative, server-side view of what happened on the wire (independent of
whether the browser managed to log a ``PaymentAttempt``).

Design notes
------------
* **Best-effort, never fatal.** The write runs inside a SAVEPOINT
  (``begin_nested``) so a logging failure rolls back *only* the log insert,
  leaving the surrounding work (e.g. the authoritative ``PaymentAttempt``)
  intact. ``get_db`` issues the final ``COMMIT`` at the end of the request.
* **Bounded growth.** Rows older than ``MAX_EXCHANGE_AGE_DAYS`` are pruned —
  always on ``prune=True`` (passed from the low-frequency *initiate* path),
  and opportunistically (~5 %) elsewhere so polling endpoints don't run a
  DELETE on every call.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sumup_exchange import MAX_EXCHANGE_AGE_DAYS, SumUpExchange

_log = logging.getLogger("vintiz")

# Keys produced by ``SumUpService._send`` that map 1:1 to model columns.
_ALLOWED_KEYS = {
    "operation",
    "method",
    "url",
    "mode",
    "checkout_id",
    "reader_id",
    "foreign_transaction_id",
    "environment",
    "request_summary",
    "http_status",
    "ok",
    "is_error",
    "error_type",
    "retry_count",
    "latency_ms",
    "response_summary",
    "error",
}


async def persist_sumup_exchanges(
    db: AsyncSession,
    svc,
    *,
    prune: bool = False,
) -> int:
    """Flush ``svc``'s buffered exchanges into the log table.

    Returns the number of rows written (0 if nothing buffered). Swallows all
    errors — diagnostic logging must never break a payment.
    """
    records = svc.drain_exchanges()
    if not records:
        return 0
    try:
        async with db.begin_nested():
            for r in records:
                fields = {k: v for k, v in r.items() if k in _ALLOWED_KEYS}
                # ``is_error`` mirrors ``not ok`` — derive it when a record
                # predates the field so the indexed failure filter stays correct.
                if "is_error" not in fields:
                    fields["is_error"] = not fields.get("ok", False)
                db.add(SumUpExchange(**fields))
            if prune or random.random() < 0.05:
                cutoff = datetime.now(timezone.utc) - timedelta(
                    days=MAX_EXCHANGE_AGE_DAYS
                )
                await db.execute(
                    delete(SumUpExchange).where(SumUpExchange.created_at < cutoff)
                )
        return len(records)
    except Exception:  # noqa: BLE001 — protect the checkout
        _log.warning("Failed to persist SumUp exchange log", exc_info=True)
        return 0
