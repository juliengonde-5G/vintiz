"""ESC/POS driver for the MUNBYN 047P-WiFi receipt printer.

Generates ESC/POS byte streams from a Vintiz transaction and sends them to
the printer over TCP (raw port 9100). Also kicks the Safescan SD-4141 cash
drawer wired to the printer's RJ-12 port via the ``ESC p m t1 t2`` command.

The printer is an 80 mm thermal model, 42 characters wide in Font A.
"""

from __future__ import annotations

import socket
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

# ESC/POS control bytes -----------------------------------------------------
ESC = b"\x1b"
GS = b"\x1d"
LF = b"\n"

INIT = ESC + b"@"                          # reset printer
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_RIGHT = ESC + b"a\x02"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
DOUBLE_ON = GS + b"!\x11"                  # double width + height
DOUBLE_OFF = GS + b"!\x00"
UNDERLINE_ON = ESC + b"-\x01"
UNDERLINE_OFF = ESC + b"-\x00"
CUT_PARTIAL = GS + b"V\x42\x00"            # full feed + partial cut

STORE_NAME = "VINTIZ"
STORE_ADDRESS = "6 rue Saint-Jacques, 27200 Vernon"
STORE_INFO = "Boutique seconde main premium"


def _encode(text: str) -> bytes:
    """Encode text in CP858 (Euro + accents) with fallback."""
    try:
        return text.encode("cp858")
    except (UnicodeEncodeError, LookupError):
        return text.encode("ascii", errors="replace")


def _line(text: str = "") -> bytes:
    return _encode(text) + LF


def _row(left: str, right: str, width: int = 42) -> bytes:
    """Build a left/right justified row fitting the paper width."""
    left = left[: width - 1]
    space = max(1, width - len(left) - len(right))
    return _encode(left + (" " * space) + right) + LF


def build_receipt(transaction: Any, *, width: int = 42, cut: bool = True) -> bytes:
    """Produce an ESC/POS byte stream for a completed Vintiz transaction."""
    out = bytearray()
    out += INIT

    # Header (centered, bold, double size for store name)
    out += ALIGN_CENTER + BOLD_ON + DOUBLE_ON
    out += _line(STORE_NAME)
    out += DOUBLE_OFF
    out += _line(STORE_INFO)
    out += BOLD_OFF
    out += _line(STORE_ADDRESS)
    out += _line("=" * width)

    # Transaction meta
    out += ALIGN_LEFT
    dt = getattr(transaction, "created_at", None) or datetime.now(timezone.utc)
    ticket_no = getattr(transaction, "transaction_number", "-")
    out += _line(f"Ticket #{ticket_no}")
    out += _line(f"Date: {dt.strftime('%d/%m/%Y %H:%M')}")
    out += _line("-" * width)

    # Line items
    items = getattr(transaction, "items", None) or []
    for item in items:
        name = getattr(item, "product_name", None) or getattr(item, "name", None) or "Article"
        qty = getattr(item, "quantity", 1) or 1
        unit = float(getattr(item, "unit_price", 0) or 0)
        total = float(getattr(item, "line_total", qty * unit) or 0)
        out += _line(name[: width])
        out += _row(f"  {qty} x {unit:.2f}", f"{total:.2f} EUR", width=width)

    out += _line("-" * width)

    total_ht = float(getattr(transaction, "total_ht", 0) or 0)
    total_tva = float(getattr(transaction, "total_tva", 0) or 0)
    total_ttc = float(getattr(transaction, "total_ttc", 0) or 0)

    out += _row("Total HT", f"{total_ht:.2f} EUR", width=width)
    out += _row("TVA 20%", f"{total_tva:.2f} EUR", width=width)
    out += BOLD_ON
    out += _row("TOTAL TTC", f"{total_ttc:.2f} EUR", width=width)
    out += BOLD_OFF
    out += _line("-" * width)

    # Payments
    payments = getattr(transaction, "payments", None) or []
    total_paid = Decimal("0")
    for payment in payments:
        method = getattr(payment, "method", None)
        label = getattr(method, "value", str(method or "PAIE")).upper()
        amount = float(getattr(payment, "amount", 0) or 0)
        total_paid += Decimal(str(amount))
        out += _row(label, f"{amount:.2f} EUR", width=width)

    change = float(total_paid) - total_ttc
    if change > 0:
        out += _row("RENDU", f"{change:.2f} EUR", width=width)

    out += _line("=" * width)

    # Fiscal hash (NF525)
    hash_chain = getattr(transaction, "hash_chain", None) or ""
    if hash_chain:
        out += _line(f"Hash NF525: {hash_chain[:16]}")

    out += LF
    out += ALIGN_CENTER + BOLD_ON
    out += _line("Merci de votre visite !")
    out += BOLD_OFF
    out += _line("vintiz.fr")
    out += LF + LF + LF

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
    """Build a short test ticket used by the Hardware settings screen."""
    out = bytearray()
    out += INIT + ALIGN_CENTER + BOLD_ON + DOUBLE_ON
    out += _line(STORE_NAME)
    out += DOUBLE_OFF
    out += BOLD_OFF
    out += _line("Test impression MUNBYN")
    out += _line(datetime.now().strftime("%d/%m/%Y %H:%M"))
    out += _line("=" * width)
    out += ALIGN_LEFT
    out += _line("Si vous voyez ce ticket,")
    out += _line("l'imprimante est correctement")
    out += _line("connectee au backend Vintiz.")
    out += LF + LF + LF
    out += CUT_PARTIAL
    return bytes(out)


def send_raw(host: str, port: int, payload: bytes, timeout: float = 5.0) -> None:
    """Send a raw byte payload to a network printer (port 9100)."""
    if not host:
        raise ValueError("Imprimante non configuree : adresse IP manquante")
    with socket.create_connection((host, int(port)), timeout=timeout) as sock:
        sock.sendall(payload)


def print_receipt(transaction: Any, host: str, port: int = 9100, *, width: int = 42, cut: bool = True) -> int:
    payload = build_receipt(transaction, width=width, cut=cut)
    send_raw(host, port, payload)
    return len(payload)


def kick_drawer(host: str, port: int = 9100, *, pin: int = 0, on_time: int = 50, off_time: int = 250) -> None:
    payload = build_drawer_kick(pin=pin, on_time=on_time, off_time=off_time)
    send_raw(host, port, payload)


def print_test(host: str, port: int = 9100, *, width: int = 42) -> None:
    send_raw(host, port, build_test_ticket(width=width))
