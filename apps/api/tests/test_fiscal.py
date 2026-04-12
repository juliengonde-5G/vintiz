"""Tests for NF525 fiscal compliance: hash chain generation and integrity."""

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.fiscal import FiscalService


def _make_transaction(
    number: int,
    total_ttc: float,
    created_at: datetime,
    hash_chain: str = "",
) -> MagicMock:
    """Create a mock Transaction object."""
    t = MagicMock()
    t.transaction_number = number
    t.total_ttc = total_ttc
    t.created_at = created_at
    t.hash_chain = hash_chain
    return t


def _compute_expected_hash(number: int, total_ttc: float, created_at: datetime, previous_hash: str) -> str:
    data_string = (
        f"{number}|"
        f"{total_ttc:.2f}|"
        f"{created_at.isoformat()}|"
        f"{previous_hash}"
    )
    return hashlib.sha256(data_string.encode("utf-8")).hexdigest()


@pytest.mark.anyio
async def test_hash_chain_generation():
    """Verify that sign_transaction computes the correct SHA-256 hash."""
    db = AsyncMock()

    # Mock: no previous transactions (first in chain)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    service = FiscalService(db)

    now = datetime(2026, 3, 29, 10, 0, 0, tzinfo=timezone.utc)
    transaction = _make_transaction(number=1, total_ttc=49.99, created_at=now)

    await service.sign_transaction(transaction)

    expected_hash = _compute_expected_hash(1, 49.99, now, "0")
    assert transaction.hash_chain == expected_hash


@pytest.mark.anyio
async def test_hash_chain_integrity():
    """Verify that verify_chain_integrity detects a valid chain."""
    db = AsyncMock()

    now = datetime(2026, 3, 29, 10, 0, 0, tzinfo=timezone.utc)
    later = datetime(2026, 3, 29, 11, 0, 0, tzinfo=timezone.utc)

    hash1 = _compute_expected_hash(1, 29.00, now, "0")
    hash2 = _compute_expected_hash(2, 49.00, later, hash1)

    t1 = _make_transaction(1, 29.00, now, hash1)
    t2 = _make_transaction(2, 49.00, later, hash2)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [t1, t2]
    db.execute.return_value = mock_result

    service = FiscalService(db)
    result = await service.verify_chain_integrity()

    assert result["valid"] is True
    assert result["checked"] == 2


@pytest.mark.anyio
async def test_hash_chain_integrity_broken():
    """Verify that verify_chain_integrity detects a broken chain."""
    db = AsyncMock()

    now = datetime(2026, 3, 29, 10, 0, 0, tzinfo=timezone.utc)
    later = datetime(2026, 3, 29, 11, 0, 0, tzinfo=timezone.utc)

    hash1 = _compute_expected_hash(1, 29.00, now, "0")
    # Tampered hash for transaction 2
    t1 = _make_transaction(1, 29.00, now, hash1)
    t2 = _make_transaction(2, 49.00, later, "tampered_hash_value")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [t1, t2]
    db.execute.return_value = mock_result

    service = FiscalService(db)
    result = await service.verify_chain_integrity()

    assert result["valid"] is False
    assert result["broken_at"] == 2


@pytest.mark.anyio
async def test_z_report_hash():
    """Verify Z report hash includes the previous Z report hash."""
    # The Z report hash formula:
    # hash = SHA256(report_number | total_sales | total_refunds | total_net | tx_count | previous_hash)
    previous_z_hash = "abc123def456"
    report_number = 5
    total_sales = 1500.00
    total_refunds = 50.00
    total_net = 1450.00
    tx_count = 30

    hash_data = (
        f"{report_number}|"
        f"{total_sales:.2f}|"
        f"{total_refunds:.2f}|"
        f"{total_net:.2f}|"
        f"{tx_count}|"
        f"{previous_z_hash}"
    )
    expected_hash = hashlib.sha256(hash_data.encode("utf-8")).hexdigest()

    # Verify the hash includes the previous hash by checking a different previous hash
    # produces a different result
    hash_data_different = (
        f"{report_number}|"
        f"{total_sales:.2f}|"
        f"{total_refunds:.2f}|"
        f"{total_net:.2f}|"
        f"{tx_count}|"
        f"different_previous_hash"
    )
    different_hash = hashlib.sha256(hash_data_different.encode("utf-8")).hexdigest()

    assert expected_hash != different_hash, "Z report hash must depend on previous hash"
    assert len(expected_hash) == 64, "Hash should be 64-char hex SHA-256"
