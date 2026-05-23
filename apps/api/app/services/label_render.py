"""Vintiz product-label renderer — printer-agnostic raster (PNG/PDF).

Replaces the Zebra ZPL stack (``zebra_zpl`` + ``label_preview``). Labels are
now rendered server-side as an image and printed by the in-store Raspberry Pi
agent via CUPS, so the format no longer depends on any single printer's page
description language.

Standard Vintiz tag — 25 mm wide × 52 mm long, read held sideways:

    ┌───────────────┐
    │ ║▌█▌█▌  N  S   │   Code 128 (rotated) + name + intake week
    │ ║▌█▌█▌  o  e   │
    │ VTZ-2026-00142 │   ← barcode interpretation line = réf
    └───────────────┘

The label content (per the boutique brief) is only the Code 128 barcode, its
reference, the product name and the intake week. The image is composed in
landscape (the long 52 mm side horizontal) then rotated 90° so the barcode bars
run along the 52 mm length and stay scannable on a 25 mm-wide media.

Two output encodings share the single ``_compose`` layout (so preview and print
can never drift):

* :func:`render_label_png` — for the admin preview (browser-friendly).
* :func:`render_label_pdf` — for the Pi agent; a PDF whose page is sized exactly
  25 × 52 mm at 203 dpi, so CUPS prints it at the right physical size without
  guessing scale. ``copies`` becomes that many PDF pages.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont

# 25 × 52 mm @ 8 dpmm (203 dpi). Width = across the print head, length = feed
# direction. Change here (+ hardware.json label_*_mm) to retarget a different
# media size.
DPMM = 8
LABEL_WIDTH_MM = 25
LABEL_HEIGHT_MM = 52
DPI = 203  # 8 dpmm ≈ 203 dpi — used to size the print PDF page in inches.

WIDTH_PX = LABEL_WIDTH_MM * DPMM   # 200 — final portrait width (25 mm)
HEIGHT_PX = LABEL_HEIGHT_MM * DPMM  # 416 — final portrait height (52 mm)

_MARGIN = 8
# Landscape working canvas (rotated to portrait at the end).
_LAND_W = HEIGHT_PX  # 416
_LAND_H = WIDTH_PX   # 200

_FONT_DIR = "/usr/share/fonts/truetype/dejavu"


@dataclass(frozen=True)
class LabelData:
    """Plain-data view of a product, ready for the label template.

    Decoupled from the SQLAlchemy ``Product`` so the template is trivially
    unit-testable without a database. The 25×52 tag only prints the barcode
    (``barcode``), the product name and the intake week; the other fields are
    kept for backward compatibility with existing callers / fixtures.
    """

    product_name: str
    category: str
    size: str | None
    condition: str | None
    sale_price: float
    barcode: str
    shelf_date: datetime | None
    location: str | None = None
    entry_date: datetime | None = None
    # ISO week of intake. When None it is derived from shelf/entry date.
    week_number: int | None = None


def _sanitize(text: str | None, *, max_length: int | None = None) -> str:
    """Collapse whitespace and clamp length for a label text field."""
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    if max_length is not None and len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 1].rstrip() + "…"
    return cleaned


def _week_label(data: LabelData) -> str:
    """`Semaine NN` from the product's week number, or derived from a date."""
    week = data.week_number
    if not week:
        anchor = data.shelf_date or data.entry_date
        if anchor is not None:
            week = anchor.isocalendar()[1]
    if not week:
        return "Semaine —"
    return f"Semaine {int(week):02d}"


def label_snapshot(data: LabelData) -> dict[str, str]:
    """Reduce a :class:`LabelData` to the minimal printable, JSON-safe content.

    This is what gets stored on a queued print job, so the label reflects what
    the manager saw at enqueue time even if the product is later edited/deleted.
    """
    return {
        "ref": _sanitize(data.barcode, max_length=24) or "VTZ-NOREF",
        "name": _sanitize(data.product_name, max_length=48) or "Article",
        "week_label": _week_label(data),
    }


# Product statuses that mean the item is physically on the shop floor. Mirrors
# FLOOR_STATUSES in the inventory router + store_ops_audit so the views agree.
_FLOOR_STATUS_VALUES = {"display", "displayed", "discounted", "deep_discounted"}


def product_to_label_data(product: Any) -> LabelData:
    """Adapt an ORM ``Product`` (or duck-typed stub) to :class:`LabelData`."""
    category_name = (
        product.category.name if getattr(product, "category", None) else "Article"
    )
    shelf = getattr(product, "displayed_at", None) or getattr(product, "shelf_date", None)
    received = getattr(product, "received_at", None)

    status = getattr(product, "status", None)
    status_val = getattr(status, "value", status)
    location = "rayon" if status_val in _FLOOR_STATUS_VALUES else "stock"

    return LabelData(
        product_name=getattr(product, "name", "") or "",
        category=category_name,
        size=getattr(product, "size", None),
        condition=getattr(product, "condition", None),
        sale_price=float(getattr(product, "sale_price", 0) or 0),
        barcode=getattr(product, "barcode", "") or "",
        shelf_date=shelf,
        location=location,
        entry_date=received,
        week_number=getattr(product, "week_number", None),
    )


def product_label_snapshot(product: Any) -> dict[str, str]:
    """Convenience: ORM product → printable snapshot in one call."""
    return label_snapshot(product_to_label_data(product))


def test_label_snapshot() -> dict[str, str]:
    """Snapshot for the /settings hardware test label."""
    return {
        "ref": "VINTIZ-TEST",
        "name": "Test impression",
        "week_label": "Raspberry · CUPS",
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(os.path.join(_FONT_DIR, name), size)
    except OSError:
        return ImageFont.load_default()


def _barcode_image(ref: str) -> Image.Image:
    """Render a Code 128 (bars + interpretation line) as a PIL image at 203 dpi."""
    writer = ImageWriter()
    writer.dpi = DPI
    code = barcode.get("code128", ref, writer=writer)
    img = code.render(
        writer_options={
            "module_width": 0.3,   # mm per narrow bar
            "module_height": 11.0,  # mm bar height
            "quiet_zone": 2.0,      # mm side margins
            "font_size": 7,         # pt — interpretation line
            "text_distance": 2.5,   # mm gap bars→text
            "write_text": True,
            "dpi": DPI,
        }
    )
    return img.convert("RGB")


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    """Greedy word-wrap ``text`` to fit ``max_width``, capped at ``max_lines``."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    # If we ran out of lines, mark truncation on the last line.
    if len(lines) == max_lines and current and lines[-1] != current:
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_width:
            last = last[:-1]
        lines[-1] = (last + "…") if last else "…"
    return lines or [""]


def _compose(snapshot: dict[str, str]) -> Image.Image:
    """Lay out the label in landscape and rotate to the 200×416 portrait media."""
    ref = snapshot.get("ref") or "VTZ-NOREF"
    name = snapshot.get("name") or "Article"
    week = snapshot.get("week_label") or "Semaine —"

    canvas = Image.new("RGB", (_LAND_W, _LAND_H), "white")
    draw = ImageDraw.Draw(canvas)

    # --- barcode block (left ~62 % of the long side) ---
    bc = _barcode_image(ref)
    bc_box_w = int(_LAND_W * 0.60) - _MARGIN
    bc_box_h = _LAND_H - 2 * _MARGIN
    scale = min(bc_box_w / bc.width, bc_box_h / bc.height)
    if scale < 1:
        bc = bc.resize((max(1, int(bc.width * scale)), max(1, int(bc.height * scale))), Image.LANCZOS)
    bc_x = _MARGIN
    bc_y = (_LAND_H - bc.height) // 2
    canvas.paste(bc, (bc_x, bc_y))

    # --- text block (right side: product name + intake week) ---
    text_x = int(_LAND_W * 0.60) + 4
    text_w = _LAND_W - text_x - _MARGIN
    name_font = _font(20, bold=True)
    week_font = _font(15)
    name_lines = _wrap(draw, name, name_font, text_w, max_lines=4)

    line_h = (name_font.getbbox("Ag")[3] - name_font.getbbox("Ag")[1]) + 4
    week_h = (week_font.getbbox("Ag")[3] - week_font.getbbox("Ag")[1]) + 6
    block_h = line_h * len(name_lines) + week_h
    y = max(_MARGIN, (_LAND_H - block_h) // 2)
    for line in name_lines:
        draw.text((text_x, y), line, font=name_font, fill="black")
        y += line_h
    draw.text((text_x, y + 2), week, font=week_font, fill="black")

    # Rotate so the barcode bars run along the 52 mm length on the 25 mm media.
    return canvas.rotate(90, expand=True)


def render_label_png(snapshot: dict[str, str]) -> bytes:
    """Render one label as PNG bytes (used by the admin preview)."""
    buf = io.BytesIO()
    _compose(snapshot).save(buf, format="PNG")
    return buf.getvalue()


def render_label_pdf(snapshot: dict[str, str], *, copies: int = 1) -> bytes:
    """Render a print-ready PDF (one page per copy, sized exactly 25×52 mm).

    Saving at ``resolution=DPI`` makes each page ``WIDTH_PX/DPI`` inches wide —
    i.e. the physical label size — so CUPS prints at 100 % scale.
    """
    img = _compose(snapshot)
    pages = [img] * max(1, int(copies))
    buf = io.BytesIO()
    pages[0].save(
        buf,
        format="PDF",
        resolution=float(DPI),
        save_all=True,
        append_images=pages[1:],
    )
    return buf.getvalue()
