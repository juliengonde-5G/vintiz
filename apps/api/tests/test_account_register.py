"""Tests for public self-service account creation (POST /account/register)."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.crm.account import AccountRegisterRequest, public_account_register
from app.models import Base, Client
from app.models.client import Consent, ConsentPurpose
from app.models.auth import MagicLinkToken


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


class _StubRequest:
    """Minimal stand-in for fastapi.Request (only .client.host is read)."""

    class _Client:
        host = "127.0.0.1"

    client = _Client()


@pytest.mark.anyio
async def test_register_creates_client_and_consents_and_token(session):
    req = AccountRegisterRequest(
        email="New.Customer@Example.FR",
        first_name="Léa",
        last_name="Dupont",
        optin_newsletter=True,
        optin_sms=False,
    )
    res = await public_account_register(req, _StubRequest(), session)
    assert res["status"] == "ok"

    # Client created with normalised email.
    client = (
        await session.execute(select(Client).where(Client.email == "new.customer@example.fr"))
    ).scalar_one()
    assert client.first_name == "Léa"
    assert client.email_optin is True

    # Newsletter consent recorded (SMS not, since opt-out).
    consents = (
        await session.execute(select(Consent).where(Consent.client_id == client.id))
    ).scalars().all()
    purposes = {c.purpose for c in consents if c.granted}
    assert ConsentPurpose.email_marketing in purposes
    assert ConsentPurpose.sms_marketing not in purposes

    # A magic-link token was issued so the visitor can confirm + log in.
    tokens = (
        await session.execute(
            select(MagicLinkToken).where(MagicLinkToken.email == "new.customer@example.fr")
        )
    ).scalars().all()
    assert len(tokens) == 1


@pytest.mark.anyio
async def test_register_existing_email_is_idempotent_no_duplicate(session):
    session.add(Client(first_name="Julie", last_name="M", email="julie@x.fr"))
    await session.flush()

    req = AccountRegisterRequest(email="julie@x.fr")
    res = await public_account_register(req, _StubRequest(), session)
    assert res["status"] == "ok"  # same response — no enumeration leak

    # Still exactly one client (no duplicate created).
    clients = (
        await session.execute(select(Client).where(Client.email == "julie@x.fr"))
    ).scalars().all()
    assert len(clients) == 1
    # A magic link is still issued (existing email → effectively a login).
    tokens = (
        await session.execute(
            select(MagicLinkToken).where(MagicLinkToken.email == "julie@x.fr")
        )
    ).scalars().all()
    assert len(tokens) == 1


@pytest.mark.anyio
async def test_register_rejects_malformed_email(session):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await public_account_register(
            AccountRegisterRequest(email="not-an-email"), _StubRequest(), session
        )
    assert exc.value.status_code == 400
