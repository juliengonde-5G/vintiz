"""Tests for the storefront photo service (background removal + branding).

The background-removal backends (Photoroom API / rembg) are never hit here:
Photoroom is gated by an API key and rembg is monkeypatched. We verify the
local compositing and the graceful-degradation contract that keeps product
intake from ever being blocked by image processing.
"""

import io

import pytest
from PIL import Image

from app.services import storefront_photo
from app.services.storefront_photo import CANVAS_SIZE


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _cutout_png(width: int = 400, height: int = 600) -> bytes:
    """A transparent canvas with an opaque rectangle in the middle."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    inner = Image.new("RGBA", (width // 2, height // 2), (200, 30, 30, 255))
    img.paste(inner, (width // 4, height // 4))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


@pytest.mark.anyio
async def test_compose_storefront_produces_square_branded_png():
    composed = storefront_photo.compose_storefront(_cutout_png())
    img = Image.open(io.BytesIO(composed))
    assert img.format == "PNG"
    assert img.size == (CANVAS_SIZE, CANVAS_SIZE)
    # Background corner should be the off-white canvas colour (top-left, away
    # from both the centred product and the bottom-right watermark).
    px = img.convert("RGB").getpixel((5, 5))
    assert px == (246, 245, 241)


@pytest.mark.anyio
async def test_compose_trims_transparent_borders_and_centres():
    # A tiny opaque square in the corner of a large transparent frame must be
    # trimmed + re-centred, not left in the corner.
    composed = storefront_photo.compose_storefront(_cutout_png(800, 800))
    img = Image.open(io.BytesIO(composed)).convert("RGB")
    centre = img.getpixel((CANVAS_SIZE // 2, CANVAS_SIZE // 2))
    # Centre should carry the product colour, not the background.
    assert centre != (246, 245, 241)


@pytest.mark.anyio
async def test_generate_skipped_when_no_backend(monkeypatch):
    monkeypatch.setattr(storefront_photo.settings, "PHOTOROOM_API_KEY", None)
    monkeypatch.setattr(storefront_photo, "_rembg_cutout", lambda _b: None)

    result = await storefront_photo.generate(b"\xff\xd8\xff", "image/jpeg")
    assert result.status == "skipped"
    assert result.image is None
    assert result.backend is None


@pytest.mark.anyio
async def test_generate_done_with_local_backend(monkeypatch):
    monkeypatch.setattr(storefront_photo.settings, "PHOTOROOM_API_KEY", None)
    monkeypatch.setattr(storefront_photo, "_rembg_cutout", lambda _b: _cutout_png())

    result = await storefront_photo.generate(b"raw-bytes", "image/jpeg")
    assert result.status == "done"
    assert result.backend == "rembg"
    img = Image.open(io.BytesIO(result.image))
    assert img.size == (CANVAS_SIZE, CANVAS_SIZE)


@pytest.mark.anyio
async def test_generate_failed_when_backend_errors(monkeypatch):
    async def _boom(_b, _m):
        raise RuntimeError("Photoroom 500")

    monkeypatch.setattr(storefront_photo, "_photoroom_cutout", _boom)

    result = await storefront_photo.generate(b"raw-bytes", "image/jpeg")
    assert result.status == "failed"
    assert result.image is None


@pytest.mark.anyio
async def test_photoroom_returns_none_without_key(monkeypatch):
    monkeypatch.setattr(storefront_photo.settings, "PHOTOROOM_API_KEY", None)
    assert await storefront_photo._photoroom_cutout(b"x", "image/jpeg") is None


@pytest.mark.anyio
async def test_generate_and_persist_writes_file(monkeypatch, tmp_path):
    monkeypatch.setattr(storefront_photo, "_UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(storefront_photo.settings, "PHOTOROOM_API_KEY", None)
    monkeypatch.setattr(storefront_photo, "_rembg_cutout", lambda _b: _cutout_png())

    url, status = await storefront_photo.generate_and_persist(
        "prod-123", b"raw", "image/jpeg"
    )
    assert status == "done"
    assert url is not None
    assert url.startswith("/uploads/products/prod-123/")
    assert url.endswith("_storefront.png")
    written = list((tmp_path / "prod-123").glob("*_storefront.png"))
    assert len(written) == 1


@pytest.mark.anyio
async def test_generate_and_persist_skips_without_backend(monkeypatch, tmp_path):
    monkeypatch.setattr(storefront_photo, "_UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(storefront_photo.settings, "PHOTOROOM_API_KEY", None)
    monkeypatch.setattr(storefront_photo, "_rembg_cutout", lambda _b: None)

    url, status = await storefront_photo.generate_and_persist("p", b"raw", "image/jpeg")
    assert url is None
    assert status == "skipped"
    assert not tmp_path.exists() or not list(tmp_path.glob("**/*_storefront.png"))


@pytest.mark.anyio
async def test_fetch_source_bytes_reads_local_uploads(monkeypatch, tmp_path):
    monkeypatch.setattr(storefront_photo, "_UPLOAD_ROOT", tmp_path)
    prod_dir = tmp_path / "abc"
    prod_dir.mkdir()
    (prod_dir / "img.png").write_bytes(b"local-bytes")

    result = await storefront_photo.fetch_source_bytes("/uploads/products/abc/img.png")
    assert result is not None
    blob, media_type = result
    assert blob == b"local-bytes"
    assert media_type == "image/png"


@pytest.mark.anyio
async def test_fetch_source_bytes_missing_local_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(storefront_photo, "_UPLOAD_ROOT", tmp_path)
    assert await storefront_photo.fetch_source_bytes("/uploads/products/x/none.jpg") is None
