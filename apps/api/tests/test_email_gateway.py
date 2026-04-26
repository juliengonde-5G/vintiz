"""Tests for the unified email gateway (P4-003)."""

import os

import pytest

from app.services.email_gateway import (
    EmailDeliveryError,
    EmailMessage,
    EmailResult,
    _strip_html,
    send_bulk,
    send_email,
)


def _clear_env(monkeypatch):
    for key in (
        "BREVO_API_KEY",
        "SMTP_HOST",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "EMAIL_FROM_ADDRESS",
        "EMAIL_FROM_NAME",
    ):
        monkeypatch.delenv(key, raising=False)


def test_simulate_when_nothing_configured(monkeypatch):
    _clear_env(monkeypatch)
    result = send_email(EmailMessage(
        to="user@example.com",
        subject="Hello",
        html="<b>Hi</b>",
    ))
    assert result.status == "simulated"
    assert result.backend == "simulation"


def test_brevo_path_uses_urllib(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BREVO_API_KEY", "ak-test")
    seen: dict = {}

    class FakeResp:
        def __init__(self, body: bytes):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self._body

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        seen["body"] = req.data
        return FakeResp(b'{"messageId": "<abc@brevo>"}')

    monkeypatch.setattr(
        "app.services.email_gateway.urlopen", fake_urlopen
    )

    result = send_email(EmailMessage(
        to="user@example.com",
        to_name="Alice",
        subject="Test",
        html="<p>Hello</p>",
    ))
    assert result.status == "sent"
    assert result.backend == "brevo"
    assert result.message_id == "<abc@brevo>"
    assert seen["url"] == "https://api.brevo.com/v3/smtp/email"
    assert seen["headers"]["api-key"] == "ak-test"
    assert b"\"to\":" in seen["body"]
    assert b"user@example.com" in seen["body"]


def test_brevo_http_error_raises(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BREVO_API_KEY", "bad")

    from urllib.error import HTTPError

    def fake_urlopen(req, timeout):
        raise HTTPError(
            url="https://api.brevo.com/v3/smtp/email",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(
        "app.services.email_gateway.urlopen", fake_urlopen
    )

    with pytest.raises(EmailDeliveryError):
        send_email(EmailMessage(
            to="x@y.fr", subject="x", html="<p>x</p>",
        ))


def test_send_bulk_swallows_individual_failures(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BREVO_API_KEY", "ak")

    calls = {"n": 0}

    def fake_urlopen(req, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            from urllib.error import HTTPError
            raise HTTPError(req.full_url, 503, "boom", None, None)

        class _R:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b'{}'
        return _R()

    monkeypatch.setattr(
        "app.services.email_gateway.urlopen", fake_urlopen
    )

    results = send_bulk([
        EmailMessage(to="a@x.fr", subject="x", html="x"),
        EmailMessage(to="b@x.fr", subject="x", html="x"),
    ])
    assert [r.status for r in results] == ["failed", "sent"]


def test_strip_html_collapses_tags():
    text = _strip_html("<p>Hello <b>world</b></p><br/>second")
    assert "Hello" in text
    assert "world" in text
    assert "<" not in text
