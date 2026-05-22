"""Tests for the Zebra cloud printing transport (SendFileToPrinter).

The Zebra Data Services API is never hit: ``httpx.AsyncClient`` is replaced
by a fake that records the outgoing request and returns a canned response.
We verify the request shape (endpoint, ``apikey``/``tenant`` headers, the
``sn`` + ``zpl_file`` multipart fields) and the error contract.
"""

import pytest

from app.services import zebra_cloud
from app.services.zebra_printer import PrinterUnreachable


@pytest.fixture
def anyio_backend():
    return "asyncio"


_FULL_CFG = {
    "cloud_api_key": "key-abc",
    "cloud_tenant": "tenant-123",
    "cloud_serial": "SN0001",
}


class _FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    """Stand-in for httpx.AsyncClient that records the last POST."""

    captured: dict = {}
    response = _FakeResponse(200)
    raise_on_post: Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, *, headers=None, data=None, files=None):
        _FakeClient.captured = {
            "url": url,
            "headers": headers,
            "data": data,
            "files": files,
        }
        if _FakeClient.raise_on_post is not None:
            raise _FakeClient.raise_on_post
        return _FakeClient.response


@pytest.fixture(autouse=True)
def _patch_httpx(monkeypatch):
    _FakeClient.captured = {}
    _FakeClient.response = _FakeResponse(200)
    _FakeClient.raise_on_post = None
    monkeypatch.setattr(zebra_cloud.httpx, "AsyncClient", _FakeClient)


def test_resolve_credentials_complete():
    api_key, tenant, serial, endpoint = zebra_cloud.resolve_credentials(_FULL_CFG)
    assert (api_key, tenant, serial) == ("key-abc", "tenant-123", "SN0001")
    assert endpoint == zebra_cloud.DEFAULT_ENDPOINT


def test_resolve_credentials_lists_missing_fields():
    with pytest.raises(zebra_cloud.CloudConfigError) as exc:
        zebra_cloud.resolve_credentials({"cloud_api_key": "k"})
    msg = str(exc.value)
    assert "tenant" in msg and "série" in msg
    assert "clé API" not in msg  # the one we provided


def test_resolve_credentials_custom_endpoint():
    *_, endpoint = zebra_cloud.resolve_credentials(
        {**_FULL_CFG, "cloud_endpoint": "https://eu.example/send"}
    )
    assert endpoint == "https://eu.example/send"


@pytest.mark.anyio
async def test_send_zpl_posts_expected_request():
    serial = await zebra_cloud.send_zpl("^XA^FDhi^FS^XZ", _FULL_CFG)
    assert serial == "SN0001"

    cap = _FakeClient.captured
    assert cap["url"] == zebra_cloud.DEFAULT_ENDPOINT
    assert cap["headers"] == {"apikey": "key-abc", "tenant": "tenant-123"}
    assert cap["data"] == {"sn": "SN0001"}
    # zpl_file part: (filename, bytes, content-type)
    field_name, (filename, payload, content_type) = next(iter(cap["files"].items()))
    assert field_name == "zpl_file"
    assert payload == b"^XA^FDhi^FS^XZ"
    assert content_type == "application/octet-stream"


@pytest.mark.anyio
async def test_send_zpl_raises_config_error_when_incomplete():
    with pytest.raises(zebra_cloud.CloudConfigError):
        await zebra_cloud.send_zpl("^XA^XZ", {"cloud_api_key": "only-key"})


@pytest.mark.anyio
async def test_send_zpl_non_2xx_raises_print_error():
    _FakeClient.response = _FakeResponse(404, "printer not found")
    with pytest.raises(zebra_cloud.CloudPrintError) as exc:
        await zebra_cloud.send_zpl("^XA^XZ", _FULL_CFG)
    assert "404" in str(exc.value)
    # CloudPrintError is a PrinterUnreachable so the router maps it to 502.
    assert isinstance(exc.value, PrinterUnreachable)


@pytest.mark.anyio
async def test_send_zpl_transport_error_raises_print_error():
    import httpx

    _FakeClient.raise_on_post = httpx.ConnectError("boom")
    with pytest.raises(zebra_cloud.CloudPrintError):
        await zebra_cloud.send_zpl("^XA^XZ", _FULL_CFG)
