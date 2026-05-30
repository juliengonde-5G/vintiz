"""Real visual embedding backend (CLIP/SigLIP) — PS 360 V4 (audit §9.2).

Default OFF: ``settings.VISUAL_EMBEDDING_BACKEND == "structured"`` keeps the
dependency-free hashing-trick encoder over the Vision attributes. When set to
``"clip"`` AND the ``[clip]`` extra is installed AND ``CLIP_MODEL_PATH`` points
to a valid image-encoder ``.onnx``, this module runs the model on a product
photo and returns a raw embedding vector.

Everything is **lazy + fail-safe**: any missing dependency, model or image
returns ``None`` and the caller (``embeddings._encode_visual``) falls back to
the structured encoder for that product. Turning the backend on is therefore
non-breaking — exactly like the rembg storefront-photo fallback.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger("vintiz.visual_encoder")

CLIP_INPUT_SIZE = 224
# CLIP ViT-B/32 image normalisation constants.
_MEAN = (0.48145466, 0.4578275, 0.40821073)
_STD = (0.26862954, 0.26130258, 0.27577711)


def backend_active() -> bool:
    """True when the operator opted into the real CLIP backend."""
    return (settings.VISUAL_EMBEDDING_BACKEND or "structured").lower() == "clip"


@lru_cache(maxsize=1)
def _session():
    """Lazily build + cache the ONNX inference session. ``None`` if unavailable."""
    path = settings.CLIP_MODEL_PATH
    if not path or not os.path.exists(path):
        logger.warning(
            "CLIP backend active but CLIP_MODEL_PATH missing/invalid: %r", path
        )
        return None
    try:
        import onnxruntime as ort

        return ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    except Exception as exc:  # pragma: no cover — depends on optional extra
        logger.warning("CLIP onnxruntime session unavailable: %s", exc)
        return None


def _load_image_bytes(image_ref: str) -> bytes | None:
    try:
        if image_ref.startswith(("http://", "https://")):
            import urllib.request

            with urllib.request.urlopen(image_ref, timeout=10) as resp:  # noqa: S310
                return resp.read()
        candidates = [image_ref]
        media_root = os.environ.get("VINTIZ_MEDIA_ROOT", "")
        if media_root:
            candidates.append(os.path.join(media_root, image_ref.lstrip("/")))
        for c in candidates:
            if os.path.exists(c):
                with open(c, "rb") as f:
                    return f.read()
    except Exception as exc:  # pragma: no cover — network / fs dependent
        logger.debug("CLIP image load failed for %r: %s", image_ref, exc)
    return None


def encode_image(image_ref: str | None) -> list[float] | None:
    """Return the raw CLIP image embedding for ``image_ref`` (or ``None``).

    The caller resizes the vector to ``EMBEDDING_DIM`` — this returns the
    model's native dimensionality (e.g. 512 for ViT-B/32).
    """
    if not backend_active() or not image_ref:
        return None
    session = _session()
    if session is None:
        return None
    raw = _load_image_bytes(image_ref)
    if raw is None:
        return None
    try:  # pragma: no cover — requires the optional [clip] extra + a model
        import io

        import numpy as np
        from PIL import Image

        img = (
            Image.open(io.BytesIO(raw))
            .convert("RGB")
            .resize((CLIP_INPUT_SIZE, CLIP_INPUT_SIZE))
        )
        arr = np.asarray(img, dtype="float32") / 255.0
        for c in range(3):
            arr[:, :, c] = (arr[:, :, c] - _MEAN[c]) / _STD[c]
        tensor = np.transpose(arr, (2, 0, 1))[None, :, :, :].astype("float32")
        input_name = session.get_inputs()[0].name
        out = session.run(None, {input_name: tensor})[0]
        return np.asarray(out).reshape(-1).astype("float32").tolist()
    except Exception as exc:  # pragma: no cover
        logger.warning("CLIP inference failed: %s", exc)
        return None
