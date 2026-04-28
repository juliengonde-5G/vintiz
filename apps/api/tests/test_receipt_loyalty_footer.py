"""Tests for the new fidelity footer on receipts (PR1)."""

from datetime import datetime, timezone

import pytest

from app.models.client import Client, LoyaltyAccount
from app.models.pos import Transaction, TransactionType
from app.services.receipt import ReceiptService


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_tx(total_ttc: float = 30.0) -> Transaction:
    """Build a minimal Transaction object that doesn't need a DB session."""
    tx = Transaction(
        transaction_number=42,
        transaction_type=TransactionType.sale,
        total_ht=total_ttc / 1.20,
        total_tva=total_ttc - (total_ttc / 1.20),
        total_ttc=total_ttc,
        hash_chain="deadbeef" * 4,
    )
    tx.created_at = datetime.now(timezone.utc)
    tx.items = []
    tx.payments = []
    return tx


def _make_member(membership_number: str, points: int = 0) -> tuple[Client, LoyaltyAccount]:
    client = Client(first_name="Alice", last_name="Martin", email="alice@x.fr")
    account = LoyaltyAccount(
        client_id=client.id,
        points=points,
        membership_number=membership_number,
    )
    return client, account


@pytest.mark.anyio
async def test_member_footer_includes_membership_and_balance():
    tx = _make_tx(total_ttc=42.0)
    client, account = _make_member("V482931", points=120)

    text = ReceiptService().generate_receipt_text(
        tx, client=client, loyalty_account=account, points_earned_on_sale=42
    )
    assert "Fidelite Vintiz" in text
    assert "V482931" in text
    assert "Alice Martin" in text
    assert "Solde : 120 pts" in text
    assert "+42 sur cet achat" in text


@pytest.mark.anyio
async def test_non_member_footer_includes_would_earn():
    tx = _make_tx(total_ttc=37.0)
    text = ReceiptService().generate_receipt_text(tx)
    assert "Fidelite Vintiz" in text
    # 37 € → 37 pts at 1 €/pt
    assert "Vous auriez gagne 37 pts" in text
    assert "Adherez" in text
    # No "Membre :" / "Solde :" lines for non-members.
    assert "Membre :" not in text
    assert "Solde :" not in text
    import re
    assert re.search(r"\bV\d{6}\b", text) is None


@pytest.mark.anyio
async def test_non_member_footer_with_zero_points_omits_would_earn_line():
    """A free transaction (e.g. avoir-only) skips the X-points teaser."""
    tx = _make_tx(total_ttc=0.0)
    text = ReceiptService().generate_receipt_text(tx)
    assert "Fidelite Vintiz" in text
    assert "auriez gagne" not in text
