"""Tests for the communications service (templates + log + seed)."""


import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import Client
from app.models.communications import CommunicationLog, MessageTemplate
from app.services.communications import (
    log_communication,
    render_template,
    seed_default_templates,
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


@pytest.mark.anyio
async def test_render_falls_back_when_no_template(session):
    r = await render_template(
        session, "anniversary", {"prenom": "Léa"},
        fallback_subject="Bonjour {prenom}",
        fallback_text="Salut {prenom}",
    )
    assert r.subject == "Bonjour Léa"
    assert r.text == "Salut Léa"
    assert r.template_key is None  # fallback used


@pytest.mark.anyio
async def test_seed_then_render_uses_template_and_substitutes(session):
    added = await seed_default_templates(session)
    assert added >= 4
    # Idempotent: a second seed adds nothing.
    assert await seed_default_templates(session) == 0

    r = await render_template(
        session, "anniversary",
        {"prenom": "Julie", "code_coupon": "ANNIV-7", "valeur": "8 €", "validite_jours": 30},
    )
    assert r.template_key == "anniversary"
    assert "Julie" in (r.subject or "")
    assert "ANNIV-7" in ((r.text or "") + (r.html or ""))


@pytest.mark.anyio
async def test_inactive_template_falls_back(session):
    await seed_default_templates(session)
    tpl = (
        await session.execute(select(MessageTemplate).where(MessageTemplate.key == "anniversary"))
    ).scalar_one()
    tpl.is_active = False
    await session.flush()

    r = await render_template(
        session, "anniversary", {"prenom": "X"},
        fallback_subject="FB {prenom}",
    )
    assert r.template_key is None
    assert r.subject == "FB X"


@pytest.mark.anyio
async def test_log_communication_writes_row(session):
    c = Client(first_name="A", last_name="B", email="a@x.fr")
    session.add(c)
    await session.flush()

    await log_communication(
        session, client_id=c.id, channel="email", kind="anniversary",
        status="sent", to_address="a@x.fr", subject="Hello", backend="brevo",
        template_key="anniversary",
    )
    rows = (
        await session.execute(select(CommunicationLog).where(CommunicationLog.client_id == c.id))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "sent"
    assert rows[0].kind == "anniversary"
    assert rows[0].backend == "brevo"


@pytest.mark.anyio
async def test_log_communication_allows_null_client(session):
    # Magic-link can fire before a Client row exists.
    await log_communication(
        session, client_id=None, channel="email", kind="magic_link",
        status="simulated", to_address="ghost@x.fr",
    )
    rows = (await session.execute(select(CommunicationLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].client_id is None
