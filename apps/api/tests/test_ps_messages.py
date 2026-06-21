"""Tests for persisting + sending a Personal Shopper selection."""

import types
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import Client
from app.models.communications import CommunicationLog
from app.models.personal_shopper import PersonalShopperMessage
from app.services import ps_messages as svc


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        Client.__table__,
        PersonalShopperMessage.__table__,
        CommunicationLog.__table__,
    ]
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


async def _client(session, email="julie@example.fr", phone=None) -> Client:
    c = Client(first_name="Julie", last_name="Martin", email=email, phone=phone)
    session.add(c)
    await session.flush()
    return c


@pytest.fixture
def fake_email(monkeypatch):
    sent = []

    def _send(msg):
        sent.append(msg)
        return types.SimpleNamespace(status="simulated", backend="test", sent_at="now")

    monkeypatch.setattr("app.services.email_gateway.send_email", _send)
    return sent


@pytest.mark.anyio
async def test_send_email_persists_message_and_comm_log(session, fake_email):
    client = await _client(session)
    pid = str(uuid.uuid4())
    row = await svc.create_and_send(
        session, client,
        message="Bonjour Julie,\nVoici 3 pièces pour vous.",
        product_ids=[pid],
        products=[{"id": pid, "name": "Robe Sandro", "brand": "Sandro", "sale_price": 45.0}],
        channel="email",
        sent_by_id=None,
    )
    assert row.status == "simulated"
    assert row.backend == "test"
    assert row.channel == "email"
    assert row.product_ids == [pid]
    # The email gateway was called with the rendered HTML containing the product.
    assert len(fake_email) == 1
    assert "Robe Sandro" in (fake_email[0].html or "")

    # A mirrored communication log row exists.
    logs = await svc.list_for_client(session, client.id)
    assert len(logs) == 1
    assert logs[0]["products"][0]["name"] == "Robe Sandro"
    from sqlalchemy import func, select
    n_comm = (await session.execute(
        select(func.count()).select_from(CommunicationLog)
        .where(CommunicationLog.kind == "personal_shopper")
    )).scalar_one()
    assert n_comm == 1


@pytest.mark.anyio
async def test_send_email_without_address_is_failed_not_crash(session, fake_email):
    client = await _client(session, email=None)
    row = await svc.create_and_send(
        session, client, message="x", product_ids=[], channel="email",
    )
    assert row.status == "failed"
    # No gateway call, no comm-log delivery success.
    assert len(fake_email) == 0


@pytest.mark.anyio
async def test_channel_none_records_without_sending(session, fake_email):
    client = await _client(session)
    row = await svc.create_and_send(
        session, client, message="présentée en boutique", product_ids=[], channel="none",
    )
    assert row.status == "saved"
    assert len(fake_email) == 0  # nothing sent
    # 'none' channel does not mirror a communication log.
    from sqlalchemy import func, select
    n_comm = (await session.execute(
        select(func.count()).select_from(CommunicationLog)
    )).scalar_one()
    assert n_comm == 0


@pytest.mark.anyio
async def test_count_and_last_for_client(session):
    from datetime import datetime, timedelta, timezone

    client = await _client(session)
    assert await svc.count_for_client(session, client.id) == 0
    assert await svc.last_for_client(session, client.id) is None

    base = datetime.now(timezone.utc)
    # Explicit, distinct timestamps so "last" is deterministic (real sends are
    # never sub-second apart; the test pins the ordering anyway).
    session.add_all([
        PersonalShopperMessage(
            client_id=client.id, message="1", product_ids=[], channel="email",
            status="sent", created_at=base - timedelta(minutes=5),
        ),
        PersonalShopperMessage(
            client_id=client.id, message="2", product_ids=[], channel="email",
            status="sent", created_at=base,
        ),
    ])
    await session.flush()

    assert await svc.count_for_client(session, client.id) == 2
    last = await svc.last_for_client(session, client.id)
    assert last is not None and last["message"] == "2"
