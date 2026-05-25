"""Storefront photo generation — automatic background removal + branded canvas.

Every product photo taken at intake serves two purposes: it boots the AI
vision engine *and* it is the image shown on the public storefront. A raw
intake snapshot (operator's hand, cluttered sorting table, mixed lighting)
is fine for Vision but unfit for the vitrine. This service produces a clean
copy: the product is cut out from its background and re-composited onto a
neutral off-white canvas carrying a discreet Vintiz monogram — the look the
public site expects.

Pipeline:
1. ``remove_background`` → transparent PNG cutout of just the product.
   Backends are tried in order and the first that succeeds wins:
     - Photoroom API (``PHOTOROOM_API_KEY``) — best quality, paid per image.
     - rembg (local, offline) — free fallback, heavier runtime.
   If neither is available the step is *skipped* (never fatal): the original
   photo keeps serving and the product fiche just lacks a vitrine copy.
2. ``compose_storefront`` → paste the cutout, trimmed and centred, onto a
   1200×1200 off-white (#F6F5F1, charte « Sauge Néo ») square with the VZ
   monogram watermarked in the lower-right corner.

The two steps are split on purpose: whatever backend produced the cutout,
the final framing + branding is always done locally with Pillow so the
vitrine look stays consistent.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image

from app.core.config import settings

logger = logging.getLogger("vintiz")

# Same uploads tree the photo upload handler + StaticFiles mount use, resolved
# from this module's location: app/services/ → apps/api/uploads/products.
_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "products"

# --- Canvas / branding constants -------------------------------------------
# Square output keeps the storefront grid tidy regardless of the product's
# orientation. 1200 px is plenty for retina cards without bloating storage.
CANVAS_SIZE = 1200
# Off-white from the design system (vz-bg #F6F5F1). Opaque RGBA.
CANVAS_BG = (246, 245, 241, 255)
# Fraction of the canvas the product is allowed to fill (leaves a margin so
# the cutout never touches the edges).
CONTENT_RATIO = 0.82
# Watermark monogram: 12 % of the canvas width, half-opaque, bottom-right.
LOGO_RATIO = 0.12
LOGO_OPACITY = 0.45
LOGO_MARGIN_RATIO = 0.04

PHOTOROOM_ENDPOINT = "https://sdk.photoroom.com/v1/segment"
# Generous timeout: Photoroom round-trips a full-res image. Still bounded so
# a hung call can never wedge the intake flow.
PHOTOROOM_TIMEOUT = 30.0

_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo-teal.png"
_logo_cache: Image.Image | None = None
_logo_lock = threading.Lock()

_SUFFIX_TO_MEDIA_TYPE = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@dataclass
class StorefrontResult:
    """Outcome of a generation attempt.

    ``status`` is one of:
      - ``done``    — a cutout was produced and composited (``image`` set).
      - ``skipped`` — no backend was available (no key + rembg absent).
      - ``failed``  — a backend was attempted but errored out.
    """

    image: bytes | None
    status: str
    backend: str | None = None


# ---------------------------------------------------------------------------
# Background removal backends
# ---------------------------------------------------------------------------


async def _photoroom_cutout(image_bytes: bytes, media_type: str) -> bytes | None:
    """Remove the background via the Photoroom segment API.

    Returns a transparent PNG, or None if no key is configured. Raises on a
    genuine API/transport error so the caller can record a ``failed`` status.
    """
    api_key = settings.PHOTOROOM_API_KEY
    if not api_key:
        return None

    async with httpx.AsyncClient(timeout=PHOTOROOM_TIMEOUT) as client:
        resp = await client.post(
            PHOTOROOM_ENDPOINT,
            headers={"x-api-key": api_key.strip()},
            files={"image_file": ("product", image_bytes, media_type)},
            data={"format": "png"},
        )
    if resp.status_code != 200:
        # Spell out the actionable cases so the failure is diagnosable from the
        # logs without re-reading Photoroom's docs. The API credit balance is
        # billed separately from the Photoroom app subscription.
        hint = {
            401: "clé API invalide ou révoquée",
            402: "crédits API épuisés — recharger sur dashboard.photoroom.com "
                 "(les crédits API sont distincts de l'abonnement de l'app)",
            403: "clé interdite pour cet endpoint / compte",
        }.get(resp.status_code, "")
        suffix = f" — {hint}" if hint else ""
        raise RuntimeError(
            f"Photoroom {resp.status_code}{suffix}: {resp.text[:200]}"
        )
    return resp.content


def _rembg_cutout(image_bytes: bytes) -> bytes | None:
    """Remove the background locally with rembg.

    Returns a transparent PNG, or None if rembg is not installed (so the
    caller falls through to ``skipped`` rather than crashing). The import is
    lazy: rembg pulls in onnxruntime which we don't want to load at boot.
    """
    try:
        from rembg import remove  # type: ignore
    except Exception as exc:  # noqa: BLE001 — ImportError or onnxruntime load error
        logger.info("rembg unavailable, skipping local background removal: %s", exc)
        return None
    return remove(image_bytes)


async def remove_background(
    image_bytes: bytes, media_type: str = "image/jpeg"
) -> tuple[bytes | None, str | None]:
    """Produce a transparent cutout of the product.

    Returns ``(cutout_png, backend)``. ``backend`` is the name of the engine
    that succeeded, or None when nothing was available. Raises only when a
    configured backend errors out (network, bad response).
    """
    cutout = await _photoroom_cutout(image_bytes, media_type)
    if cutout:
        return cutout, "photoroom"

    # rembg inference is synchronous + CPU-heavy (onnxruntime). Run it in a
    # worker thread so a slow cutout never blocks the event loop — otherwise a
    # single heavy intake photo freezes the whole API (other requests, e.g. la
    # mise en rayon qui suit, timeout côté client → « Erreur de connexion »).
    cutout = await asyncio.to_thread(_rembg_cutout, image_bytes)
    if cutout:
        return cutout, "rembg"

    return None, None


# ---------------------------------------------------------------------------
# Compositing
# ---------------------------------------------------------------------------


def _load_logo() -> Image.Image | None:
    """Return the cached RGBA monogram, or None if the asset is missing."""
    global _logo_cache
    if _logo_cache is not None:
        return _logo_cache
    with _logo_lock:
        if _logo_cache is None:
            try:
                _logo_cache = Image.open(_LOGO_PATH).convert("RGBA")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Vintiz watermark logo unavailable (%s)", exc)
                return None
    return _logo_cache


def _apply_opacity(img: Image.Image, opacity: float) -> Image.Image:
    """Scale an RGBA image's alpha channel by ``opacity`` (0..1)."""
    img = img.convert("RGBA")
    alpha = img.getchannel("A").point(lambda a: int(a * opacity))
    img.putalpha(alpha)
    return img


def compose_storefront(cutout_png: bytes) -> bytes:
    """Frame a transparent cutout on the branded off-white canvas.

    The cutout is trimmed to its visible bounds, scaled to fill ``CONTENT_RATIO``
    of the canvas while preserving aspect, centred, and stamped with the
    Vintiz monogram. Returns PNG bytes.
    """
    cutout = Image.open(io.BytesIO(cutout_png)).convert("RGBA")

    # Trim transparent borders so centring is based on the product, not the
    # original frame. getbbox uses the alpha channel for RGBA images.
    bbox = cutout.getbbox()
    if bbox:
        cutout = cutout.crop(bbox)

    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), CANVAS_BG)

    max_dim = int(CANVAS_SIZE * CONTENT_RATIO)
    w, h = cutout.size
    if w > 0 and h > 0:
        scale = min(max_dim / w, max_dim / h)
        new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
        cutout = cutout.resize(new_size, Image.LANCZOS)

    offset = (
        (CANVAS_SIZE - cutout.width) // 2,
        (CANVAS_SIZE - cutout.height) // 2,
    )
    # Use the cutout's own alpha as the paste mask to keep edges clean.
    canvas.paste(cutout, offset, cutout)

    logo = _load_logo()
    if logo is not None:
        target_w = int(CANVAS_SIZE * LOGO_RATIO)
        ratio = target_w / logo.width
        logo_resized = logo.resize(
            (target_w, max(1, round(logo.height * ratio))), Image.LANCZOS
        )
        logo_resized = _apply_opacity(logo_resized, LOGO_OPACITY)
        margin = int(CANVAS_SIZE * LOGO_MARGIN_RATIO)
        pos = (
            CANVAS_SIZE - logo_resized.width - margin,
            CANVAS_SIZE - logo_resized.height - margin,
        )
        canvas.paste(logo_resized, pos, logo_resized)

    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def generate(
    image_bytes: bytes, media_type: str = "image/jpeg"
) -> StorefrontResult:
    """Generate the branded storefront copy of a product photo.

    Never raises: a failure in any backend or in compositing is captured as a
    ``failed`` status so product intake is never blocked by image processing.
    """
    try:
        cutout, backend = await remove_background(image_bytes, media_type)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Background removal failed: %s", exc)
        return StorefrontResult(image=None, status="failed", backend=None)

    if cutout is None:
        return StorefrontResult(image=None, status="skipped", backend=None)

    try:
        # Pillow compositing (LANCZOS resize, paste, PNG encode) is also
        # synchronous CPU work — keep it off the event loop too.
        composed = await asyncio.to_thread(compose_storefront, cutout)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Storefront compositing failed: %s", exc)
        return StorefrontResult(image=None, status="failed", backend=backend)

    return StorefrontResult(image=composed, status="done", backend=backend)


def persist(product_id: uuid.UUID | str, image_bytes: bytes) -> str:
    """Write a generated storefront PNG under the product's uploads folder.

    Returns the public ``/uploads/...`` URL served by the StaticFiles mount.
    """
    target_dir = _UPLOAD_ROOT / str(product_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{uuid.uuid4().hex}_storefront.png"
    path = target_dir / fname
    path.write_bytes(image_bytes)
    os.chmod(path, 0o644)
    return f"/uploads/products/{product_id}/{fname}"


async def generate_and_persist(
    product_id: uuid.UUID | str, image_bytes: bytes, media_type: str = "image/jpeg"
) -> tuple[str | None, str]:
    """Generate the storefront copy and, on success, persist it to disk.

    Returns ``(processed_url, status)``. ``processed_url`` is None unless a
    backend produced a cutout and it was composited + written.
    """
    result = await generate(image_bytes, media_type)
    if result.status != "done" or result.image is None:
        return None, result.status
    return persist(product_id, result.image), "done"


async def fetch_source_bytes(url: str) -> tuple[bytes, str] | None:
    """Resolve a photo URL to ``(bytes, media_type)`` for processing.

    Handles locally-hosted ``/uploads/...`` paths (read from disk) and absolute
    ``http(s)`` URLs (fetched). Returns None when the source can't be located.
    """
    suffix = Path(url.split("?", 1)[0]).suffix.lower()
    media_type = _SUFFIX_TO_MEDIA_TYPE.get(suffix, "image/jpeg")
    if url.startswith("/uploads/products/"):
        disk_path = _UPLOAD_ROOT / url[len("/uploads/products/"):]
        if disk_path.is_file():
            return disk_path.read_bytes(), media_type
        return None
    if url.startswith("http://") or url.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch photo source %s: %s", url[:80], exc)
            return None
        if resp.status_code == 200:
            return resp.content, resp.headers.get("content-type", media_type)
        return None
    return None
