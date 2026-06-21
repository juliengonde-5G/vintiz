"""Message templates + communication log (client comms personalisation).

Two additive tables:

- ``MessageTemplate`` — admin-editable subject/body for the *automated*
  client-facing messages (anniversary, weekly new arrivals, trend alert,
  consent confirmation). Rendered with ``{variable}`` substitution; the code
  keeps a hard-coded fallback so a missing/disabled template never blocks a
  send. Distinct from ``ReceiptTemplate`` (POS tickets/invoices, NF525-bound).

- ``CommunicationLog`` — one row per message actually sent to (or attempted
  for) a client, surfaced on the admin client fiche. Written at the sender
  call sites (the email/SMS gateways are stateless, no db), so every automated
  send is traceable: channel, kind, subject, delivery status + backend.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MessageChannel(str, enum.Enum):
    email = "email"
    sms = "sms"


class MessageTemplate(Base):
    __tablename__ = "message_templates"

    # Stable key the code looks up (e.g. "anniversary", "new_arrivals",
    # "trend_alert", "consent_confirmation"). Unique per row.
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    channel: Mapped[MessageChannel] = mapped_column(
        String(10), nullable=False, default=MessageChannel.email.value
    )
    # Human label + the list of available {variables} shown in the admin.
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Email: subject + HTML (+ optional text). SMS: only body_text is used.
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Disabled → the sender uses its hard-coded fallback.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CommunicationLog(Base):
    __tablename__ = "communication_logs"

    # Nullable: magic-link can fire before a Client row exists; we still log
    # the attempt keyed by the address.
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(10), nullable=False)  # email | sms
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    to_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    # sent | simulated | failed | skipped — mirrors the gateway result status.
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    backend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Rendered HTML actually sent — lets the manager re-open the exact email from
    # the client fiche. Populated for the rich emails (trend alert, personal
    # shopper…) ; null for the lightweight ones (magic-link, SMS).
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
