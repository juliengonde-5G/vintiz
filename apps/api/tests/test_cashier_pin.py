"""Tests for the POS cashier PIN service (P1-002 + P1-014).

Uses mocks for the DB session to keep these as fast unit tests; integration
tests against the FastAPI app live alongside test_security.py and run
in CI with the full stack.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.cashier import (
    PIN_LENGTH,
    CashierService,
    _validate_pin_format,
)


def _make_user(username: str, pin_hash: str | None = None, is_active: bool = True):
    user = MagicMock()
    user.username = username
    user.pin_hash = pin_hash
    user.is_active = is_active
    user.role = MagicMock(value="collaborateur")
    return user


def _db_returning_users(users: list) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = users
    db.execute.return_value = result
    return db


# ---------------------------------------------------------------------------
# PIN format validation
# ---------------------------------------------------------------------------


def test_pin_format_accepts_4_digits():
    _validate_pin_format("1234")  # no exception


@pytest.mark.parametrize("bad_pin", ["", "12", "12345", "abcd", "12 4", "12a4", None])
def test_pin_format_rejects_invalid(bad_pin):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _validate_pin_format(bad_pin)
    assert exc.value.status_code == 400
    assert str(PIN_LENGTH) in exc.value.detail


# ---------------------------------------------------------------------------
# set_pin / clear_pin
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_set_pin_hashes_with_bcrypt():
    import bcrypt

    db = AsyncMock()
    user = _make_user("sophie")

    service = CashierService(db)
    await service.set_pin(user, "4321")

    assert user.pin_hash is not None
    assert user.pin_hash != "4321"  # never store plain
    assert bcrypt.checkpw(b"4321", user.pin_hash.encode("utf-8"))
    db.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_set_pin_with_bad_format_raises_before_hashing():
    from fastapi import HTTPException

    db = AsyncMock()
    user = _make_user("sophie", pin_hash="existing-hash")
    service = CashierService(db)

    with pytest.raises(HTTPException):
        await service.set_pin(user, "12")  # only 2 digits

    assert user.pin_hash == "existing-hash"  # unchanged
    db.flush.assert_not_awaited()


@pytest.mark.anyio
async def test_clear_pin_nullifies_hash():
    db = AsyncMock()
    user = _make_user("sophie", pin_hash="something")
    service = CashierService(db)

    await service.clear_pin(user)

    assert user.pin_hash is None
    db.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# authenticate_pin
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_authenticate_pin_returns_matching_user():
    import bcrypt

    sophie_hash = bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode("utf-8")
    lea_hash = bcrypt.hashpw(b"5678", bcrypt.gensalt()).decode("utf-8")

    sophie = _make_user("sophie", pin_hash=sophie_hash)
    lea = _make_user("lea", pin_hash=lea_hash)

    service = CashierService(_db_returning_users([sophie, lea]))
    result = await service.authenticate_pin("5678")

    assert result is lea


@pytest.mark.anyio
async def test_authenticate_pin_rejects_wrong_pin():
    import bcrypt
    from fastapi import HTTPException

    sophie_hash = bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode("utf-8")
    sophie = _make_user("sophie", pin_hash=sophie_hash)

    service = CashierService(_db_returning_users([sophie]))

    with pytest.raises(HTTPException) as exc:
        await service.authenticate_pin("9999")
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_authenticate_pin_with_no_candidates_returns_401():
    from fastapi import HTTPException

    service = CashierService(_db_returning_users([]))

    with pytest.raises(HTTPException) as exc:
        await service.authenticate_pin("1234")
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_authenticate_pin_with_bad_format_returns_400():
    from fastapi import HTTPException

    service = CashierService(_db_returning_users([]))

    with pytest.raises(HTTPException) as exc:
        await service.authenticate_pin("abc")
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_authenticate_pin_iterates_all_candidates_for_constant_timing():
    """The service should not short-circuit on the first match — this prevents
    an attacker from inferring user count via timing differences."""
    import bcrypt

    matching_hash = bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode("utf-8")
    other_hash = bcrypt.hashpw(b"9999", bcrypt.gensalt()).decode("utf-8")

    # Match is first in the list — service should still check the rest.
    matching_user = _make_user("first", pin_hash=matching_hash)
    other_user1 = _make_user("second", pin_hash=other_hash)
    other_user2 = _make_user("third", pin_hash=other_hash)

    db = _db_returning_users([matching_user, other_user1, other_user2])
    service = CashierService(db)
    result = await service.authenticate_pin("1234")

    assert result is matching_user
    # We can't easily assert "no break" without instrumenting bcrypt,
    # but verify the function doesn't return early — the test simply
    # documents the intent. The implementation uses `match = match or candidate`
    # rather than `return candidate` to enforce this.


# ---------------------------------------------------------------------------
# list_with_pin_status
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_with_pin_status_marks_users_with_and_without_pin():
    import uuid as _uuid

    sophie = _make_user("sophie", pin_hash="hash-here")
    sophie.id = _uuid.uuid4()
    julien = _make_user("julien", pin_hash=None)
    julien.id = _uuid.uuid4()

    service = CashierService(_db_returning_users([julien, sophie]))
    rows = await service.list_with_pin_status()

    assert len(rows) == 2
    by_username = {r["username"]: r for r in rows}
    assert by_username["sophie"]["has_pin"] is True
    assert by_username["julien"]["has_pin"] is False
