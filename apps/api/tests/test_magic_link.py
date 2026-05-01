"""Tests for magic_link service (PR1)."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Client, MagicLinkToken
from app.services.magic_link import (
    MagicLinkError,
    _hash_code,
    issue,
    verify,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as s:
        yield s
    await eng.dispose()


async def _issue_with_known_code(session, email: str, code: str = "482931"):
    """Issue a token then overwrite the code hash to a known plaintext."""
    await issue(session, email, ip="127.0.0.1")
    await session.flush()
    row = await session.execute(
        select(MagicLinkToken)
        .where(MagicLinkToken.email == email)
        .order_by(MagicLinkToken.created_at.desc())
        .limit(1)
    )
    tok = row.scalar_one()
    tok.code_hash = _hash_code(code)
    await session.flush()
    return tok


@pytest.mark.anyio
async def test_issue_and_verify_happy_path(session):
    session.add(Client(first_name="Alice", last_name="M", email="alice@x.fr"))
    await session.flush()
    await _issue_with_known_code(session, "alice@x.fr", code="482931")

    result = await verify(session, "alice@x.fr", "482931", ip="127.0.0.1")
    assert result.access_token
    assert result.client_id
    assert result.expires_in == 3600


@pytest.mark.anyio
async def test_verify_rejects_replay(session):
    session.add(Client(first_name="A", last_name="B", email="a@x.fr"))
    await session.flush()
    await _issue_with_known_code(session, "a@x.fr", code="111111")
    await verify(session, "a@x.fr", "111111", ip="127.0.0.1")

    with pytest.raises(MagicLinkError) as exc:
        await verify(session, "a@x.fr", "111111", ip="127.0.0.1")
    assert exc.value.code == "invalid_or_expired"


@pytest.mark.anyio
async def test_verify_wrong_code_increments_attempts(session):
    session.add(Client(first_name="A", last_name="B", email="a@x.fr"))
    await session.flush()
    await _issue_with_known_code(session, "a@x.fr", code="123456")

    with pytest.raises(MagicLinkError) as exc:
        await verify(session, "a@x.fr", "999999", ip="127.0.0.1")
    assert exc.value.code == "invalid_or_expired"

    row = await session.execute(
        select(MagicLinkToken).where(MagicLinkToken.email == "a@x.fr")
    )
    tok = row.scalar_one()
    assert tok.attempts == 1


@pytest.mark.anyio
async def test_verify_locks_after_5_attempts(session):
    session.add(Client(first_name="A", last_name="B", email="a@x.fr"))
    await session.flush()
    await _issue_with_known_code(session, "a@x.fr", code="123456")

    for _ in range(4):
        with pytest.raises(MagicLinkError):
            await verify(session, "a@x.fr", "000000", ip="127.0.0.1")

    # 5th wrong attempt locks the row.
    with pytest.raises(MagicLinkError) as exc:
        await verify(session, "a@x.fr", "000000", ip="127.0.0.1")
    assert exc.value.code == "too_many_attempts"

    # Even the right code is rejected once locked.
    with pytest.raises(MagicLinkError):
        await verify(session, "a@x.fr", "123456", ip="127.0.0.1")


@pytest.mark.anyio
async def test_verify_no_client_returns_invalid(session):
    """A code can be issued for an email with no Client row, but verify still 401s."""
    await _issue_with_known_code(session, "ghost@x.fr", code="333333")
    with pytest.raises(MagicLinkError) as exc:
        await verify(session, "ghost@x.fr", "333333", ip="127.0.0.1")
    assert exc.value.code == "invalid_or_expired"


@pytest.mark.anyio
async def test_issue_rate_limit_per_email(session):
    """7th issue within an hour silently does nothing (no row inserted).

    Tracks ``RATE_LIMIT_EMAIL_PER_HOUR`` — bumped from 3 to 6 for diagnostic
    tolerance (5d9ebbe). Brute-force on a 6-digit OTP remains negligible.
    """
    from app.services.magic_link import RATE_LIMIT_EMAIL_PER_HOUR

    for _ in range(RATE_LIMIT_EMAIL_PER_HOUR):
        await issue(session, "spam@x.fr", ip="127.0.0.1")
    await session.flush()
    rows = (
        await session.execute(
            select(MagicLinkToken).where(MagicLinkToken.email == "spam@x.fr")
        )
    ).scalars().all()
    assert len(rows) == RATE_LIMIT_EMAIL_PER_HOUR

    await issue(session, "spam@x.fr", ip="127.0.0.1")
    await session.flush()
    rows = (
        await session.execute(
            select(MagicLinkToken).where(MagicLinkToken.email == "spam@x.fr")
        )
    ).scalars().all()
    # The (N+1)-th was rate-limited, no new row.
    assert len(rows) == RATE_LIMIT_EMAIL_PER_HOUR
