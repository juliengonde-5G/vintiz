"""Tests for the refund-aware receipt template (P1-010 follow-up)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.models.pos import PaymentMethod, TransactionType
from app.services.receipt import ReceiptService


def _mock_item(name: str, qty: int, unit_price: float, line_total: float):
    item = MagicMock()
    item.product = MagicMock(name=name)
    item.product.name = name
    item.quantity = qty
    item.unit_price = unit_price
    item.discount_percent = 0
    item.line_total = line_total
    return item


def _mock_payment(method: PaymentMethod, amount: float):
    pay = MagicMock()
    pay.method = method
    pay.amount = amount
    return pay


_DEFAULT = object()


def _mock_refund_tx(
    *,
    items=_DEFAULT,
    payments=_DEFAULT,
    refund_reason: str | None = "Mauvaise taille",
    original_id=None,
):
    tx = MagicMock()
    tx.transaction_number = 42
    tx.transaction_type = TransactionType.refund
    tx.created_at = datetime(2026, 4, 26, 10, 30, 0, tzinfo=timezone.utc)
    tx.total_ht = 40.83
    tx.total_tva = 8.17
    tx.total_ttc = 49.00
    tx.hash_chain = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    tx.original_transaction_id = original_id or uuid.uuid4()
    tx.refund_reason = refund_reason
    tx.items = items if items is not _DEFAULT else [_mock_item("Robe noire", 1, 49.00, 49.00)]
    tx.payments = payments if payments is not _DEFAULT else [_mock_payment(PaymentMethod.cash, 49.00)]
    return tx


def test_refund_receipt_uses_dedicated_header():
    text = ReceiptService().generate_receipt_text(_mock_refund_tx())
    assert "TICKET DE RETOUR" in text
    # Sale receipts say "Ticket #" — refund template uses "Retour #"
    assert "Retour #42" in text
    assert "Ticket #42" not in text


def test_refund_receipt_shows_negative_totals():
    text = ReceiptService().generate_receipt_text(_mock_refund_tx())
    # Total HT and TTC must be displayed as negatives so the audit trail
    # makes the direction unambiguous.
    assert "-40.83 EUR" in text
    assert "-49.00 EUR" in text


def test_refund_receipt_includes_original_link_and_reason():
    original = uuid.UUID("12345678-1234-5678-1234-567812345678")
    text = ReceiptService().generate_receipt_text(
        _mock_refund_tx(original_id=original, refund_reason="Défaut visible")
    )
    assert "Ref. vente d'origine: 12345678" in text
    assert "Motif: Défaut visible" in text


def test_refund_receipt_shows_payment_method_as_rendu():
    text = ReceiptService().generate_receipt_text(
        _mock_refund_tx(payments=[_mock_payment(PaymentMethod.cash, 49.00)])
    )
    assert "CASH (rendu)" in text


def test_refund_receipt_with_no_payment_renders_avoir_credit():
    """Avoir refunds don't have a Payment row — the receipt must still show
    the customer that they received store credit."""
    text = ReceiptService().generate_receipt_text(
        _mock_refund_tx(payments=[])
    )
    assert "AVOIR client" in text
    assert "49.00 EUR" in text


def test_sale_receipt_unchanged_for_non_refund():
    """Make sure the existing sale template still applies when type != refund."""
    tx = _mock_refund_tx()
    tx.transaction_type = TransactionType.sale
    text = ReceiptService().generate_receipt_text(tx)
    assert "Ticket #42" in text
    assert "TICKET DE RETOUR" not in text
