"""Consentement au pixel d'ouverture des e-mails (recommandation CNIL 2026).

Couvre :
- le gate ``track_opens`` propagé dans le payload Brevo (tag d'audit) ;
- le helper ``latest_consent_granted`` (le dernier enregistrement fait foi).
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.client import Client, Consent, ConsentPurpose
from app.services.email_gateway import EmailMessage, send_email
from app.services.rgpd import latest_consent_granted


def _clear_env(monkeypatch):
    for key in ("BREVO_API_KEY", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)


class _FakeResp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b'{"messageId": "<id@brevo>"}'


def _capture_brevo(monkeypatch, seen):
    def fake_urlopen(req, timeout):
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp()

    monkeypatch.setattr("app.services.email_gateway.urlopen", fake_urlopen)


def test_brevo_tags_no_open_tracking_when_declined(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BREVO_API_KEY", "ak")
    seen: dict = {}
    _capture_brevo(monkeypatch, seen)

    send_email(EmailMessage(
        to="a@x.fr", subject="Promo", html="<p>hi</p>", track_opens=False,
    ))
    assert "no-open-tracking" in seen["body"].get("tags", [])


def test_brevo_no_marker_when_consented(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BREVO_API_KEY", "ak")
    seen: dict = {}
    _capture_brevo(monkeypatch, seen)

    send_email(EmailMessage(
        to="a@x.fr", subject="Promo", html="<p>hi</p>", track_opens=True,
    ))
    assert "no-open-tracking" not in seen["body"].get("tags", [])


def test_brevo_no_marker_for_transactional(monkeypatch):
    """track_opens=None (défaut, e-mail de service) → pas de marqueur."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("BREVO_API_KEY", "ak")
    seen: dict = {}
    _capture_brevo(monkeypatch, seen)

    send_email(EmailMessage(to="a@x.fr", subject="Ticket", html="<p>hi</p>"))
    assert "no-open-tracking" not in seen["body"].get("tags", [])


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(
                c, tables=[Client.__table__, Consent.__table__]
            )
        )
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as s:
        yield s
    await eng.dispose()


@pytest.mark.anyio
async def test_latest_consent_granted_latest_wins(session):
    client = Client(first_name="Ada", last_name="L", email="ada@x.fr")
    session.add(client)
    await session.flush()

    base = datetime(2026, 7, 1, tzinfo=timezone.utc)

    def _add(granted: bool, offset_min: int) -> None:
        # created_at explicite → ordre déterministe (en prod les horodatages
        # sont naturellement distincts).
        session.add(Consent(
            id=uuid.uuid4(),
            client_id=client.id,
            purpose=ConsentPurpose.email_open_tracking,
            granted=granted,
            policy_version="v-test",
            source="test",
            created_at=base + timedelta(minutes=offset_min),
        ))

    # Aucun enregistrement → non accordé.
    assert not await latest_consent_granted(
        session, client.id, ConsentPurpose.email_open_tracking
    )

    # Accordé (t0) puis retiré (t1) → le dernier (retrait) fait foi.
    _add(True, 0)
    _add(False, 1)
    await session.flush()
    assert not await latest_consent_granted(
        session, client.id, ConsentPurpose.email_open_tracking
    )

    # Ré-accordé (t2) → True.
    _add(True, 2)
    await session.flush()
    assert await latest_consent_granted(
        session, client.id, ConsentPurpose.email_open_tracking
    )
