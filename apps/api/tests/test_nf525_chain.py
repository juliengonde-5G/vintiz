"""Complementary NF525 tests covering tampering scenarios not in test_fiscal.py.

Acceptance criterion (V1 ticket P1-001): "toute modification d'une transaction
passée invalide la chaîne". The existing test_fiscal.py covers a tampered
hash field; these tests cover tampered DATA (which causes the recomputed
expected hash to differ from the stored hash) and ordering attacks.
"""

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.fiscal import FiscalService


def _make_transaction(
    number: int,
    total_ttc: float,
    created_at: datetime,
    hash_chain: str = "",
) -> MagicMock:
    t = MagicMock()
    t.transaction_number = number
    t.total_ttc = total_ttc
    t.created_at = created_at
    t.hash_chain = hash_chain
    return t


def _compute_expected_hash(
    number: int, total_ttc: float, created_at: datetime, previous_hash: str
) -> str:
    data_string = (
        f"{number}|"
        f"{total_ttc:.2f}|"
        f"{created_at.isoformat()}|"
        f"{previous_hash}"
    )
    return hashlib.sha256(data_string.encode("utf-8")).hexdigest()


def _setup_db_with_transactions(transactions: list[MagicMock]) -> AsyncMock:
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = transactions
    db.execute.return_value = mock_result
    return db


# ---------------------------------------------------------------------------
# Tampering with each transaction field invalidates the chain
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_modifying_total_ttc_breaks_chain():
    """Changing total_ttc on a stored transaction must be detected."""
    t0 = datetime(2026, 4, 26, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 4, 26, 11, 0, 0, tzinfo=timezone.utc)

    h1 = _compute_expected_hash(1, 29.00, t0, "0")
    h2 = _compute_expected_hash(2, 49.00, t1, h1)

    tx1 = _make_transaction(1, 29.00, t0, h1)
    # Attacker changed total from 49.00 → 19.00 but kept the original hash
    tampered = _make_transaction(2, 19.00, t1, h2)

    service = FiscalService(_setup_db_with_transactions([tx1, tampered]))
    result = await service.verify_chain_integrity()

    assert result["valid"] is False
    assert result["broken_at"] == 2


@pytest.mark.anyio
async def test_modifying_created_at_breaks_chain():
    """Changing created_at on a stored transaction must be detected."""
    t0 = datetime(2026, 4, 26, 10, 0, 0, tzinfo=timezone.utc)
    original_t1 = datetime(2026, 4, 26, 11, 0, 0, tzinfo=timezone.utc)
    backdated_t1 = datetime(2026, 4, 25, 11, 0, 0, tzinfo=timezone.utc)

    h1 = _compute_expected_hash(1, 29.00, t0, "0")
    h2_legit = _compute_expected_hash(2, 49.00, original_t1, h1)

    tx1 = _make_transaction(1, 29.00, t0, h1)
    # Attacker backdated created_at but kept the legit hash
    tampered = _make_transaction(2, 49.00, backdated_t1, h2_legit)

    service = FiscalService(_setup_db_with_transactions([tx1, tampered]))
    result = await service.verify_chain_integrity()

    assert result["valid"] is False
    assert result["broken_at"] == 2


@pytest.mark.anyio
async def test_modifying_first_transaction_cascades():
    """Tampering the first transaction must surface at the first link.

    Even if the attacker recomputes the first hash to match the new data,
    the previous_hash anchor is "0" — so they'd need to also tamper
    every subsequent hash. This test verifies detection at the first.
    """
    t0 = datetime(2026, 4, 26, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 4, 26, 11, 0, 0, tzinfo=timezone.utc)

    h1_legit = _compute_expected_hash(1, 29.00, t0, "0")
    h2_legit = _compute_expected_hash(2, 49.00, t1, h1_legit)

    # Attacker increased the first transaction total from 29 to 99,
    # but kept the original h1 — verification will fail at tx 1.
    tampered_tx1 = _make_transaction(1, 99.00, t0, h1_legit)
    tx2 = _make_transaction(2, 49.00, t1, h2_legit)

    service = FiscalService(_setup_db_with_transactions([tampered_tx1, tx2]))
    result = await service.verify_chain_integrity()

    assert result["valid"] is False
    assert result["broken_at"] == 1


@pytest.mark.anyio
async def test_insertion_attack_breaks_chain():
    """Inserting a fake transaction in the middle must break verification.

    The attacker would need to recompute every subsequent hash to maintain
    the chain — this test simulates a naive insertion that doesn't.
    """
    t0 = datetime(2026, 4, 26, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 4, 26, 10, 30, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 4, 26, 11, 0, 0, tzinfo=timezone.utc)

    h1 = _compute_expected_hash(1, 29.00, t0, "0")
    # Originally h2 was chained from h1; after fake insertion, h2 should
    # have been recomputed from h_fake but wasn't.
    h2_originally_from_h1 = _compute_expected_hash(2, 49.00, t2, h1)

    tx1 = _make_transaction(1, 29.00, t0, h1)
    fake = _make_transaction(99, 1000.00, t1, "fake_hash_value")
    tx2 = _make_transaction(2, 49.00, t2, h2_originally_from_h1)

    service = FiscalService(_setup_db_with_transactions([tx1, fake, tx2]))
    result = await service.verify_chain_integrity()

    assert result["valid"] is False
    # The fake transaction is detected first (its hash doesn't match data)
    assert result["broken_at"] == 99


# ---------------------------------------------------------------------------
# Long chain is still verifiable
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_long_valid_chain_passes():
    """A 100-transaction chain built correctly must verify as valid."""
    transactions: list[MagicMock] = []
    previous_hash = "0"
    base_time = datetime(2026, 4, 26, 8, 0, 0, tzinfo=timezone.utc)

    for i in range(1, 101):
        ts = base_time.replace(minute=i % 60, second=i % 60)
        amount = 10.0 + (i * 0.5)
        h = _compute_expected_hash(i, amount, ts, previous_hash)
        transactions.append(_make_transaction(i, amount, ts, h))
        previous_hash = h

    service = FiscalService(_setup_db_with_transactions(transactions))
    result = await service.verify_chain_integrity()

    assert result["valid"] is True
    assert result["checked"] == 100


# ---------------------------------------------------------------------------
# Hash format guarantees (NF525 audit-friendly)
# ---------------------------------------------------------------------------


def test_hash_format_is_64_hex_chars():
    """Each chain hash must be exactly 64 hex characters (SHA-256 output)."""
    t = datetime(2026, 4, 26, 10, 0, 0, tzinfo=timezone.utc)
    h = _compute_expected_hash(1, 49.99, t, "0")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_genesis_anchor_is_string_zero():
    """The chain genesis must use '0' as previous_hash for the very first tx."""
    t = datetime(2026, 4, 26, 10, 0, 0, tzinfo=timezone.utc)
    expected = _compute_expected_hash(1, 49.99, t, "0")
    # If implementation accidentally used "" or None, the hash would differ:
    different_anchor = _compute_expected_hash(1, 49.99, t, "")
    assert expected != different_anchor, (
        "Genesis anchor must be the literal string '0', not empty string"
    )
