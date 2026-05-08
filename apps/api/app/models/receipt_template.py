"""Receipt / invoice templates — configurable from the back-office.

Lets the manager personalise the printed ticket without touching the code.
Each template targets a *kind* (``ticket`` for everyday sales, ``invoice``
for B2B with SIRET / detailed VAT). At least one ``is_default=True``
template per kind exists at all times — that's the one
``ReceiptService.generate_receipt_text`` falls back to when the POS
doesn't pick a specific one.

NF525 note: the body of a *signed* transaction is bound to a snapshot of
the template at the time of the sale (via ``transactions.template_id``);
editing the template afterwards does not retro-actively change the
historical receipt.
"""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReceiptKind(str, enum.Enum):
    ticket = "ticket"     # consumer receipt (B2C)
    invoice = "invoice"   # commercial invoice (B2B, SIRET, VAT detail)


class ReceiptTemplate(Base):
    __tablename__ = "receipt_templates"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[ReceiptKind] = mapped_column(
        Enum(ReceiptKind, name="receipt_kind"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    footer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conditions_retour: Mapped[str | None] = mapped_column(Text, nullable=True)
    show_tva_breakdown: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    show_loyalty_footer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
