"""TCP socket driver for the Zebra ZD421d label printer.

The printer accepts raw ZPL II on port 9100. We open a short-lived socket
per job (the printer queues internally, so reusing the connection would
buy us nothing and complicate retries).

No CUPS, no vendor driver — just the bytes on the wire.
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass

DEFAULT_PORT = 9100
DEFAULT_TIMEOUT_S = 3.0


class PrinterUnreachable(RuntimeError):
    """Raised when the printer host doesn't accept a TCP connection."""


@dataclass(frozen=True)
class PrinterStatus:
    online: bool
    ip: str
    port: int
    latency_ms: float | None
    detail: str | None = None


def send_zpl(
    zpl: str,
    *,
    host: str,
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> int:
    """Send a ZPL job to the printer and return the byte count written.

    Raises ``PrinterUnreachable`` if the socket can't be opened within
    ``timeout`` seconds — the caller maps this to a 502.
    """
    if not host:
        raise PrinterUnreachable("Adresse IP imprimante non configurée")

    payload = zpl.encode("utf-8")
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(payload)
    except (socket.timeout, OSError) as exc:
        raise PrinterUnreachable(
            f"Imprimante {host}:{port} injoignable ({exc})"
        ) from exc
    return len(payload)


def ping(
    *,
    host: str,
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> PrinterStatus:
    """Test reachability without printing anything.

    Opens a TCP connection, measures the round-trip and closes immediately.
    The Zebra firmware accepts and discards an empty payload, so this is
    safe to call as often as the UI wants for its status pill.
    """
    if not host:
        return PrinterStatus(
            online=False, ip=host or "", port=port, latency_ms=None,
            detail="IP non configurée",
        )
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except (socket.timeout, OSError) as exc:
        return PrinterStatus(
            online=False, ip=host, port=port, latency_ms=None, detail=str(exc),
        )
    latency_ms = round((time.monotonic() - start) * 1000, 1)
    return PrinterStatus(online=True, ip=host, port=port, latency_ms=latency_ms)


def send_test_label(*, host: str, port: int = DEFAULT_PORT) -> int:
    """Send a tiny ZPL test page so the operator can validate the wiring.

    Prints "VINTIZ • Test impression" + the current date — enough to
    confirm the printer is reachable and configured correctly without
    bothering with a real product fixture.
    """
    test_zpl = (
        "^XA^CI28^PW640^LL400^LH0,0"
        "^FO0,60^FB640,1,0,C,0^A0N,80,80^FDVINTIZ^FS"
        "^FO20,160^GB600,2,2^FS"
        "^FO0,190^FB640,1,0,C,0^A0N,40,40^FDTest impression^FS"
        "^FO0,260^FB640,1,0,C,0^A0N,28,28^FDZebra ZD421d • ZPL^FS"
        "^PQ1^XZ"
    )
    return send_zpl(test_zpl, host=host, port=port)
