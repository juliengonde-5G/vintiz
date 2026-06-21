"""Personal Shopper messages — persisted selections sent to a client.

The Personal Shopper recommendation itself is computed on the fly (no stored
recommendation set). This table records the moments a manager *sent* a curated
selection to a client ("le personal shopper a envoyé un message") so the client
fiche can show the history and the actual products proposed, even after they
sell or change price (hence the ``products_snapshot``).

One row per send. A parallel ``CommunicationLog`` row (kind="personal_shopper")
is also written so the selection shows up in the Communications tab like every
other client message.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONType


class PersonalShopperMessage(Base):
    __tablename__ = "personal_shopper_messages"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # The narrative shown/sent to the client (manager-editable before sending).
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Selected product ids (["uuid", …]) and a snapshot of each so the history
    # renders even once the items have sold or moved.
    product_ids: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    products_snapshot: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    # email | sms | none ("présentée en boutique", no send).
    channel: Mapped[str] = mapped_column(String(10), nullable=False, default="email")
    # sent | simulated | failed | draft — mirrors the gateway result.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="sent")
    backend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    algo_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    sent_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
