"""SumUp API exchange log — every HTTP call Vintiz makes to SumUp.

Why this exists
---------------
Until now the only trace of a CB payment was the ``PaymentAttempt`` row that
the **browser** POSTs to ``/payment-attempts``. When a checkout silently
fell through to *payment-link* mode (no reader resolved) or SumUp answered a
403/422, there was **no server-side record of what SumUp actually returned** —
making "les transactions ne passent plus vers le terminal" impossible to
debug from the back-office.

``SumUpExchange`` is an append-only diagnostic ledger : one row per HTTP
request the backend sends to ``api.sumup.com`` (create checkout, push to
reader, poll status, cancel, terminate, refund, ping…). It records the
operation, the (redacted) URL, the HTTP status, the latency, and a
**redacted** request/response summary so the manager can see, from
``/settings > Système``, exactly what happened on the wire.

Security
--------
Every free-text field is passed through :func:`redact_sumup_error` before
persistence : no Bearer token, API key, affiliate key, PAN or CVV is ever
stored. The ``Authorization`` header is never logged (it lives in
``_headers`` and is not part of the recorded payload). PCI-DSS req. 3 +
RGPD minimisation compliant — same redaction the ``PaymentAttempt.error_detail``
already relies on.

Retention
---------
Pruned to the last :data:`MAX_EXCHANGE_AGE_DAYS` days on insert (cheap indexed
delete) and clearable on demand from the UI — this is a rolling debug buffer,
not a fiscal record (the NF525 chain lives on ``Transaction``).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

#: Rows older than this are pruned automatically when a new exchange is logged.
MAX_EXCHANGE_AGE_DAYS = 30


class SumUpExchange(Base):
    __tablename__ = "sumup_exchanges"

    # Logical operation — create_checkout | reader_push | get_status |
    # reader_status | cancel_peek | cancel_delete | terminate | refund |
    # ping | ping_status | sync | get_transaction | receipt
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    # Redacted target URL (merchant code may appear — it is an identifier, not
    # a secret; the Bearer key never appears here).
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # True for a 2xx response. A network error or non-2xx leaves it False.
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "reader" (push to Solo) | "checkout" (payment link) | None (other calls).
    # The whole point of the debug log: a CB sale that records mode="checkout"
    # did NOT ring the terminal.
    mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    checkout_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reader_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    foreign_transaction_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    # Redacted JSON summary of the request body / query params we sent.
    request_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Redacted (and truncated) response body.
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Redacted exception text on a network/transport error.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # --- Fast error triage (indexed) ------------------------------------
    # ``is_error`` mirrors ``not ok`` but is indexed so the back-office can
    # filter failures directly (``ok`` was only ever scanned). ``error_type``
    # is the classified cause — a SumUp ``error_code`` (READER_OFFLINE…), an
    # ``http_<status>`` bucket, or a transport exception name (ConnectError…).
    # ``retry_count`` = number of automatic retries this call went through
    # before the recorded outcome (0 = succeeded/failed first shot).
    is_error: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    error_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
