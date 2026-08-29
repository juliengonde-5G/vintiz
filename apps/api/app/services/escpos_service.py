"""ESC/POS driver for the MUNBYN 047P-WiFi receipt printer.

Generates ESC/POS byte streams from a Vintiz transaction and sends them to
the printer over TCP (raw port 9100). Also kicks the Safescan SD-4141 cash
drawer wired to the printer's RJ-12 port via the ``ESC p m t1 t2`` command.

The printer is an 80 mm thermal model, 42 characters wide in Font A.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

_log = logging.getLogger("vintiz")

# Vintiz logo for the ticket header — converted on the fly from the PNG
# in app/assets/. The result is cached so we don't pay the resize +
# threshold cost on every receipt. ``RECEIPT_LOGO_PATH`` env var lets
# ops point at a different asset without redeploying.
_LOGO_PATH = Path(
    os.getenv(
        "RECEIPT_LOGO_PATH",
        str(Path(__file__).resolve().parent.parent / "assets" / "receipt-logo.png"),
    )
)
# Logo printed at 320 dots wide (≈ 40 mm) so it sits comfortably in the
# 80 mm paper with margin on both sides. The 047P's print zone is 576
# dots — anything wider than that is silently clipped on the right.
_LOGO_TARGET_WIDTH = 320
# Cache keyed by resolved logo path so a re-uploaded company logo isn't masked
# by a stale raster.
_logo_raster_cache: dict[str, bytes] = {}
_logo_raster_lock = threading.Lock()

# Per-host serialization: two concurrent ESC/POS streams on the same printer
# would interleave bytes and corrupt the output (and the cash drawer kick
# is part of the same byte stream).
_host_locks: dict[tuple[str, int], threading.Lock] = {}
_host_locks_guard = threading.Lock()


def _lock_for(host: str, port: int) -> threading.Lock:
    key = (host, int(port))
    with _host_locks_guard:
        lock = _host_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _host_locks[key] = lock
        return lock

# ESC/POS control bytes -----------------------------------------------------
ESC = b"\x1b"
GS = b"\x1d"
LF = b"\n"

# Robust initialisation sequence — sent at the start of every job.
#
# Why this matters: ``ESC @`` alone resets the printer but leaves the
# codepage and character set at firmware defaults, which vary between
# MUNBYN firmware revisions (CN, EU, …). On some 047P units the default
# codepage is "no codepage" and text bytes are silently dropped, which
# manifests as a paper that feeds + cuts cleanly but comes out blank.
# We therefore force CP858 (Western Europe + Euro), the US international
# charset, Font A and clear character emphasis so the printer is in a
# predictable, printable state for every job.
INIT = (
    ESC + b"@"             # reset all flags
    + ESC + b"t\x13"       # codepage 19 = CP858 (Western Europe + €)
    + ESC + b"R\x00"       # international charset = USA
    + ESC + b"M\x00"       # select Font A
    + ESC + b"!\x00"       # no double height / no double width / no emphasis
)

ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_RIGHT = ESC + b"a\x02"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
DOUBLE_ON = GS + b"!\x11"                  # double width + height
DOUBLE_OFF = GS + b"!\x00"
UNDERLINE_ON = ESC + b"-\x01"
UNDERLINE_OFF = ESC + b"-\x00"
# Feed 6 lines before the partial cut so the receipt clears the tear
# bar even on units where the firmware ignores trailing LFs.
FEED_BEFORE_CUT = ESC + b"d\x06"
CUT_PARTIAL = FEED_BEFORE_CUT + GS + b"V\x42\x00"  # feed + partial cut

STORE_NAME = "VINTIZ"
STORE_ADDRESS = "6 rue Saint-Jacques, 27200 Vernon"
STORE_INFO = "Boutique seconde main premium"


# Accent → ASCII fold. Several MUNBYN 047P firmware revisions ignore the
# ``ESC t`` codepage select and render CP858 high bytes as garbage (the
# "é" / "à" come out as random glyphs). Folding to ASCII before encoding
# guarantees a legible ticket on every unit — we lose the accent but never
# the readability, which is the right trade-off for a thermal receipt.
_ACCENT_FOLD = str.maketrans(
    {
        "à": "a", "â": "a", "ä": "a", "á": "a", "ã": "a", "å": "a",
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "î": "i", "ï": "i", "í": "i", "ì": "i",
        "ô": "o", "ö": "o", "ó": "o", "ò": "o", "õ": "o",
        "ù": "u", "û": "u", "ü": "u", "ú": "u",
        "ç": "c", "ñ": "n", "ÿ": "y",
        "À": "A", "Â": "A", "Ä": "A", "Á": "A", "Ã": "A",
        "É": "E", "È": "E", "Ê": "E", "Ë": "E",
        "Î": "I", "Ï": "I", "Ô": "O", "Ö": "O",
        "Ù": "U", "Û": "U", "Ü": "U", "Ç": "C", "Ñ": "N",
        "œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE",
        "€": "EUR", "’": "'", "‘": "'", "“": '"', "”": '"',
        "–": "-", "—": "-", "…": "...", "·": "-", "•": "-",
        " ": " ", " ": " ",
    }
)


def _encode(text: str) -> bytes:
    """Fold accents to ASCII, then encode (printer-codepage agnostic)."""
    folded = (text or "").translate(_ACCENT_FOLD)
    return folded.encode("ascii", errors="replace")


def _build_logo_raster(logo_path: str | None = None) -> bytes:
    """Convert the company logo PNG into an ESC/POS raster command.

    Uses ``GS v 0 m xL xH yL yH d…`` (raster bit image) which is the
    most widely supported image command on ESC/POS clones. The PNG is
    composited on white, converted to 1-bit at ``_LOGO_TARGET_WIDTH``
    dots wide, then packed MSB-first 8 pixels per byte. Cached per path.

    ``logo_path`` overrides the default asset (used by the configurable
    company logo). Returns ``b""`` on any failure so the receipt still
    prints without the logo.
    """
    path = Path(logo_path) if logo_path else _LOGO_PATH
    key = str(path)
    with _logo_raster_lock:
        cached = _logo_raster_cache.get(key)
        if cached is not None:
            return cached
        try:
            from PIL import Image  # local import — only needed once
        except ImportError:
            _log.warning("Pillow not available, receipt logo disabled")
            _logo_raster_cache[key] = b""
            return b""
        if not path.exists():
            _log.warning("Receipt logo missing at %s", path)
            _logo_raster_cache[key] = b""
            return b""
        try:
            im = Image.open(path).convert("RGBA")
            ratio = _LOGO_TARGET_WIDTH / im.size[0]
            target_h = int(im.size[1] * ratio)
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            flat = Image.alpha_composite(bg, im).convert("L")
            resized = flat.resize(
                (_LOGO_TARGET_WIDTH, target_h), Image.LANCZOS
            ).convert("1")
            width_bytes = _LOGO_TARGET_WIDTH // 8
            # Pillow's "1" mode is one bit per pixel ; black = 0, white = 1.
            # ESC/POS raster expects "1 = burn / print" — invert.
            pixels = resized.tobytes()
            inverted = bytes(b ^ 0xFF for b in pixels)
            x_l, x_h = width_bytes & 0xFF, (width_bytes >> 8) & 0xFF
            y_l, y_h = target_h & 0xFF, (target_h >> 8) & 0xFF
            header = GS + b"v0" + bytes([0, x_l, x_h, y_l, y_h])
            _logo_raster_cache[key] = header + inverted
            return _logo_raster_cache[key]
        except Exception as exc:  # noqa: BLE001 — never fail the receipt
            _log.warning("Receipt logo conversion failed: %s", exc)
            _logo_raster_cache[key] = b""
            return b""


def _item_detail_parts(item: Any) -> list[str]:
    """Build extra description chips for one transaction item.

    Pulls size / color / brand / barcode from the linked Product when
    available. Falls back to whatever attributes the item itself carries
    so the function also works with the dict-shaped transactions
    returned by ``PosService.get_transaction`` (used by the resend
    handler and the dashboard preview).
    """
    parts: list[str] = []

    def _get(field: str) -> str | None:
        value = getattr(item, field, None)
        if value is None and hasattr(item, "product"):
            value = getattr(item.product, field, None)
        return value or None

    size = _get("size")
    if size:
        parts.append(f"T.{size}")
    color = _get("color")
    if color:
        parts.append(str(color))
    brand = _get("brand")
    if brand:
        parts.append(str(brand))
    return parts


def _line(text: str = "") -> bytes:
    return _encode(text) + LF


def _shop_info() -> dict[str, Any]:
    """Persisted boutique metadata (name, address, logo…). Sync read from the
    app_config JSON file — safe to call from this sync builder."""
    try:
        from app.services.app_config import get_section

        return get_section("shop_info") or {}
    except Exception:  # noqa: BLE001 — never fail the receipt on a config read
        return {}


def _wrap(text: str, width: int) -> list[str]:
    """Wrap a string to ``width`` columns without splitting words."""
    text = text or ""
    if len(text) <= width:
        return [text]
    out: list[str] = []
    cur = ""
    for word in text.split():
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= width:
            cur += " " + word
        else:
            out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    # Hard-split any single word longer than the width.
    final: list[str] = []
    for chunk in out:
        while len(chunk) > width:
            final.append(chunk[:width])
            chunk = chunk[width:]
        final.append(chunk)
    return final or [""]


def _row(left: str, right: str, width: int = 42) -> bytes:
    """Build a left/right justified row fitting the paper width."""
    left = left[: width - 1]
    space = max(1, width - len(left) - len(right))
    return _encode(left + (" " * space) + right) + LF


def build_receipt(
    transaction: Any,
    *,
    template: Any | None = None,
    shop: dict[str, Any] | None = None,
    width: int = 42,
    cut: bool = True,
    duplicata_number: int | None = None,
) -> bytes:
    """Produce an ESC/POS byte stream for a completed Vintiz transaction.

    Unified with the back-office configuration: the header (shop name +
    address), the footer and the return conditions come from the persisted
    ``shop_info`` and the resolved ticket ``ReceiptTemplate`` — the same model
    the dashboard receipt text and the studio preview use. Hardcoded constants
    are only the last-resort fallback when nothing is configured.
    """
    out = bytearray()
    out += INIT

    shop = shop if shop is not None else _shop_info()
    store_name = (
        (template.title if template and getattr(template, "title", None) else "")
        or shop.get("name")
        or STORE_NAME
    )
    store_info = shop.get("tagline") or STORE_INFO
    addr_parts = [
        shop.get("address_line1", ""),
        f"{shop.get('postal_code', '')} {shop.get('city', '')}".strip(),
    ]
    store_address = ", ".join(p for p in addr_parts if p) or STORE_ADDRESS

    # Logo : the `GS v 0` raster command is OFF by default because
    # several MUNBYN 047P firmware revisions don't recognise it and
    # print the raw bytes as garbled ASCII at the top of the ticket.
    # Opt-in via the env flag OR the persisted ``shop_info.print_logo_on_ticket``
    # once the printer is verified. The text wordmark below always shows.
    env_logo = os.getenv("RECEIPT_PRINT_RASTER_LOGO", "false").lower() in {"1", "true", "yes"}
    if env_logo or bool(shop.get("print_logo_on_ticket")):
        logo = _build_logo_raster(shop.get("logo_path") or None)
        if logo:
            out += ALIGN_CENTER
            out += logo
            out += LF

    # Header (centered, bold, double size for store name)
    out += ALIGN_CENTER + BOLD_ON + DOUBLE_ON
    for hline in _wrap(store_name.upper(), max(8, width // 2)):
        out += _line(hline)
    out += DOUBLE_OFF
    out += _line(store_info)
    out += BOLD_OFF
    for aline in _wrap(store_address, width):
        out += _line(aline)
    out += _line("=" * width)

    # NF525 : toute réimpression est un duplicata numéroté, marqué sur le
    # ticket lui-même (jamais une copie indiscernable de l'original).
    if duplicata_number:
        out += ALIGN_CENTER + BOLD_ON + DOUBLE_ON
        out += _line(f"* DUPLICATA n.{duplicata_number} *")
        out += DOUBLE_OFF + BOLD_OFF

    # Transaction meta
    out += ALIGN_LEFT
    dt = getattr(transaction, "created_at", None) or datetime.now(timezone.utc)
    ticket_no = getattr(transaction, "transaction_number", "-")
    out += _line(f"Ticket #{ticket_no}")
    out += _line(f"Date: {dt.strftime('%d/%m/%Y %H:%M')}")
    out += _line("-" * width)

    # Line items — full detail: name, size/color/brand chips, optional
    # barcode reference, qty × unit price + line total. The brief asked
    # for more than a bare reference: the customer should be able to
    # read what they bought from the ticket alone.
    items = getattr(transaction, "items", None) or []
    for item in items:
        product = getattr(item, "product", None)
        pn = getattr(item, "product_name", None)
        name = (
            (pn if isinstance(pn, str) and pn.strip() else None)
            or getattr(product, "name", None)
            or "Article"
        )
        qty = getattr(item, "quantity", 1) or 1
        unit = float(getattr(item, "unit_price", 0) or 0)
        total = float(getattr(item, "line_total", qty * unit) or 0)
        discount = float(getattr(item, "discount_percent", 0) or 0)
        barcode = (
            getattr(item, "barcode", None)
            or getattr(product, "barcode", None)
            or None
        )

        for nline in _wrap(str(name), width):
            out += _line(nline)
        # Secondary chip line — only when there's actually something to show
        chips = _item_detail_parts(item)
        if chips:
            out += _line("  " + " · ".join(chips)[: width - 2])
        # Barcode reference on its own discreet line so the customer can
        # spot the ref for an exchange / SAV without ambiguity
        if barcode:
            out += _line(f"  Réf : {barcode}"[:width])

        discount_suffix = f" -{discount:.0f}%" if discount > 0 else ""
        out += _row(
            f"  {qty} x {unit:.2f}{discount_suffix}",
            f"{total:.2f} EUR",
            width=width,
        )

    out += _line("-" * width)

    total_ht = float(getattr(transaction, "total_ht", 0) or 0)
    total_tva = float(getattr(transaction, "total_tva", 0) or 0)
    total_ttc = float(getattr(transaction, "total_ttc", 0) or 0)

    vat_rate = shop.get("vat_rate_percent")
    vat_label = f"TVA {float(vat_rate):g}%" if vat_rate else "TVA"
    out += _row("Total HT", f"{total_ht:.2f} EUR", width=width)
    out += _row(vat_label, f"{total_tva:.2f} EUR", width=width)
    out += BOLD_ON
    out += _row("TOTAL TTC", f"{total_ttc:.2f} EUR", width=width)
    out += BOLD_OFF
    out += _line("-" * width)

    # Payments — for CB payments backed by a SumUp transaction we add
    # the card brand + last 4 digits + auth code + SumUp transaction
    # code on dedicated lines. This is required by French ANC fiscal
    # rules for card-present payments (the customer's "souche
    # commerçant" must show the auth code and a way to reconcile back
    # to the acquirer) and is also useful for SAV / disputes.
    payments = getattr(transaction, "payments", None) or []
    total_paid = Decimal("0")
    for payment in payments:
        method = getattr(payment, "method", None)
        label = getattr(method, "value", str(method or "PAIE")).upper().replace("_", " ")
        amount = float(getattr(payment, "amount", 0) or 0)
        total_paid += Decimal(str(amount))
        out += _row(label, f"{amount:.2f} EUR", width=width)

        # SumUp CB-specific detail block — only present when the
        # payment was matched against a SumUp transaction (see
        # migration 0037). Stays silent for cash/cheque/avoir.
        card_brand = getattr(payment, "sumup_card_brand", None)
        card_last4 = getattr(payment, "sumup_card_last4", None)
        auth_code = getattr(payment, "sumup_auth_code", None)
        tx_code = getattr(payment, "sumup_transaction_code", None)
        if any((card_brand, card_last4, auth_code, tx_code)):
            if card_brand or card_last4:
                brand = (card_brand or "CB").upper()
                last4 = card_last4 or "****"
                out += _line(f"  {brand} **** {last4}"[:width])
            if auth_code:
                out += _line(f"  Authorisation : {auth_code}"[:width])
            if tx_code:
                out += _line(f"  Réf SumUp : {tx_code}"[:width])

    change = float(total_paid) - total_ttc
    if change > 0:
        out += _row("RENDU", f"{change:.2f} EUR", width=width)

    out += _line("=" * width)

    # Fiscal hash (NF525)
    hash_chain = getattr(transaction, "hash_chain", None) or ""
    if hash_chain:
        out += _line(f"Hash NF525: {hash_chain[:16]}")

    # Footer — wrapped in an explicit state reset so it always prints
    # in the right size/alignment even if an earlier section left the
    # printer in a weird state (some MUNBYN clones don't clear flags
    # on LF). The previous version only printed "Merci..." and
    # "vintiz.fr" with no buffer flush — on some firmwares the
    # CUT_PARTIAL was reaching the cutter before the head had inked
    # the footer.
    out += LF
    out += ALIGN_CENTER + BOLD_ON
    footer_text = (
        (template.footer if template and getattr(template, "footer", None) else "")
        or "Merci de votre visite !"
    )
    for fline in _wrap(footer_text, width):
        out += _line(fline)
    out += BOLD_OFF
    website = shop.get("website")
    if website:
        out += _line(str(website))
    # Return conditions from the configured ticket template (unified with the
    # studio + dashboard receipt text).
    conditions = template.conditions_retour if template else None
    if conditions:
        out += _line("-" * width)
        out += ALIGN_LEFT
        for cline in _wrap(str(conditions), width):
            out += _line(cline)
        out += ALIGN_CENTER
    out += _line(f"{shop.get('city', 'Vernon')} · {dt.strftime('%d/%m/%Y')}")
    # Explicit feed before cut so the head has time to flush the
    # buffer onto the paper before the cutter fires.
    out += LF + LF
    out += ALIGN_LEFT

    if cut:
        out += CUT_PARTIAL

    return bytes(out)


def build_cb_ticket(
    data: dict[str, Any],
    *,
    shop: dict[str, Any] | None = None,
    merchant_code: str | None = None,
    width: int = 42,
    cut: bool = True,
) -> bytes:
    """Build a card-payment slip (ticket CB) from the SumUp Solo return.

    ``data`` carries: ``copy`` ("merchant"|"client"), ``amount``, ``status``
    ("paid"|"failed"|"cancelled"|"timeout"), and the optional card detail
    (``card_brand``, ``card_last4``, ``auth_code``, ``transaction_code``,
    ``transaction_id``, ``declined_reason``).

    Issued for every CB attempt — success or failure — so the merchant keeps a
    trace of the terminal outcome (ANC/CB rules) and the client gets a copy on
    demand.
    """
    shop = shop if shop is not None else _shop_info()
    out = bytearray()
    out += INIT

    store_name = (shop.get("name") or STORE_NAME).upper()
    addr_parts = [
        shop.get("address_line1", ""),
        f"{shop.get('postal_code', '')} {shop.get('city', '')}".strip(),
    ]
    store_address = ", ".join(p for p in addr_parts if p) or STORE_ADDRESS

    out += ALIGN_CENTER + BOLD_ON + DOUBLE_ON
    for hline in _wrap(store_name, max(8, width // 2)):
        out += _line(hline)
    out += DOUBLE_OFF
    out += BOLD_OFF
    for aline in _wrap(store_address, width):
        out += _line(aline)
    out += LF
    out += BOLD_ON
    out += _line("TICKET CARTE BANCAIRE")
    copy = (data.get("copy") or "merchant").lower()
    out += _line("COPIE COMMERCANT" if copy == "merchant" else "COPIE CLIENT")
    out += BOLD_OFF
    out += _line("=" * width)

    out += ALIGN_LEFT
    now = datetime.now()
    out += _line(f"Date  : {now.strftime('%d/%m/%Y %H:%M')}")
    if merchant_code:
        out += _line(f"Commercant : {merchant_code}")
    brand = (data.get("card_brand") or "").upper()
    last4 = data.get("card_last4") or ""
    if brand or last4:
        out += _line(f"Carte : {brand or 'CB'} **** {last4 or '****'}")
    amount = float(data.get("amount") or 0)
    out += _row("Montant", f"{amount:.2f} EUR", width=width)
    out += _line("-" * width)

    status = (data.get("status") or "").lower()
    out += ALIGN_CENTER + BOLD_ON
    if status == "paid":
        out += _line("*** TRANSACTION ACCEPTEE ***")
    else:
        out += _line("*** TRANSACTION REFUSEE ***")
    out += BOLD_OFF
    out += ALIGN_LEFT
    if status == "paid":
        auth = data.get("auth_code")
        if auth:
            out += _line(f"Autorisation : {auth}")
        ref = data.get("transaction_code") or data.get("transaction_id")
        if ref:
            out += _line(f"Reference    : {ref}")
    else:
        reason = data.get("declined_reason")
        if reason:
            for rline in _wrap(f"Motif : {reason}", width):
                out += _line(rline)
    out += _line("=" * width)

    out += LF
    out += ALIGN_CENTER
    if copy == "merchant":
        out += _line("Exemplaire conserve par le commercant")
    else:
        out += _line("Conservez ce ticket")
    out += LF + LF
    out += ALIGN_LEFT
    if cut:
        out += CUT_PARTIAL
    return bytes(out)


def build_drawer_kick(pin: int = 0, on_time: int = 50, off_time: int = 250) -> bytes:
    """Build the ESC/POS pulse command that kicks the cash drawer.

    ``ESC p m t1 t2`` — ``m`` selects the drawer pin (0 = pin 2, 1 = pin 5),
    ``t1``/``t2`` encode the on/off durations (units of 2 ms, max 255).
    """
    m = 0 if pin == 0 else 1
    t1 = max(1, min(255, on_time // 2))
    t2 = max(1, min(255, off_time // 2))
    return ESC + b"p" + bytes([m, t1, t2])


def build_test_ticket(width: int = 42) -> bytes:
    """Build a short test ticket used by the Hardware settings screen.

    Designed to fail loudly rather than silently : the ticket prints a
    pure-ASCII banner (no codepage-dependent chars), an explicit visual
    pattern (asterisks) and the timestamp. If even this comes out blank
    the issue is upstream of the byte stream (paper loaded backwards,
    head not heating, USB endpoint wrong) — see ``docs/MANUEL_BOUTIQUE.md``
    for the troubleshooting checklist.
    """
    out = bytearray()
    out += INIT
    out += ALIGN_CENTER + BOLD_ON + DOUBLE_ON
    out += _line("VINTIZ")
    out += DOUBLE_OFF
    out += BOLD_OFF
    out += _line("Test impression MUNBYN")
    out += _line(datetime.now().strftime("%d/%m/%Y %H:%M"))
    out += _line("*" * (width // 2))  # high-contrast pattern visible regardless of codepage
    out += ALIGN_LEFT
    out += _line("Si vous voyez ce ticket,")
    out += _line("l'imprimante est correctement")
    out += _line("connectee au backend Vintiz.")
    out += _line("")
    out += _line("Sinon: papier a l'envers ?")
    out += _line("(grattez avec l'ongle pour")
    out += _line(" verifier le cote thermosensible)")
    out += CUT_PARTIAL
    return bytes(out)




def send_raw(
    host: str,
    port: int,
    payload: bytes,
    timeout: float = 5.0,
    *,
    retries: int = 3,
) -> None:
    """Send a raw byte payload to a network printer (port 9100).

    Retries with exponential backoff (0.3s, 0.6s, 1.2s) on transient TCP
    errors — the boutique Wi-Fi can drop the printer for a few seconds during
    AP roaming. Concurrent calls to the same host:port are serialized so that
    two payloads (e.g. a receipt + a drawer kick) never interleave their
    bytes on the wire.
    """
    if not host:
        raise ValueError("Imprimante non configuree : adresse IP manquante")
    last_exc: Exception | None = None
    lock = _lock_for(host, port)
    with lock:
        for attempt in range(max(1, retries)):
            try:
                with socket.create_connection((host, int(port)), timeout=timeout) as sock:
                    sock.sendall(payload)
                return
            except (OSError, socket.timeout) as exc:
                last_exc = exc
                if attempt + 1 >= retries:
                    break
                backoff = 0.3 * (2 ** attempt)
                _log.warning(
                    "escpos send_raw failed on %s:%s (attempt %d/%d): %s — retry in %.1fs",
                    host, port, attempt + 1, retries, exc, backoff,
                )
                time.sleep(backoff)
    assert last_exc is not None
    raise last_exc


def print_receipt(
    transaction: Any,
    host: str,
    port: int = 9100,
    *,
    template: Any | None = None,
    shop: dict[str, Any] | None = None,
    width: int = 42,
    cut: bool = True,
    duplicata_number: int | None = None,
) -> int:
    payload = build_receipt(
        transaction, template=template, shop=shop, width=width, cut=cut,
        duplicata_number=duplicata_number,
    )
    send_raw(host, port, payload)
    return len(payload)


def kick_drawer(host: str, port: int = 9100, *, pin: int = 0, on_time: int = 50, off_time: int = 250) -> None:
    payload = build_drawer_kick(pin=pin, on_time=on_time, off_time=off_time)
    send_raw(host, port, payload)


def print_test(host: str, port: int = 9100, *, width: int = 42) -> None:
    send_raw(host, port, build_test_ticket(width=width))
