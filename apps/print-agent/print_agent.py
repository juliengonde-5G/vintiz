#!/usr/bin/env python3
"""Vintiz label print agent — runs on the in-store Raspberry Pi.

The Vintiz API runs off-site and can't reach a printer on the boutique LAN.
Instead of being pushed to, this agent *pulls*: it polls the API for queued
label jobs (outbound HTTPS only, so it works behind the shop router's NAT with
no port-forwarding), prints each job's server-rendered PDF on the locally
attached printer via CUPS (``lp``), and acks the result.

Design goals:
  * Zero pip dependencies — stdlib only (urllib + subprocess), so the Pi just
    needs Python 3 and CUPS. Survives ``apt`` upgrades without a venv.
  * Crash-safe — a job claimed but never acked is re-queued server-side after
    RPI_AGENT_STALE_SECONDS, so a power cut never loses a label silently.
  * Quiet when idle — long-ish poll interval; backs off on errors instead of
    hammering the API.

Configuration is read from the environment (see ``.env.example``):

    VINTIZ_API_URL    Base URL of the Vintiz API      (e.g. https://app.vintiz.fr)
    RPI_AGENT_TOKEN   Shared secret (= server's RPI_AGENT_TOKEN)
    CUPS_PRINTER      CUPS queue name                 (empty = system default)
    POLL_INTERVAL     Seconds between polls when idle (default 5)
    BATCH_MAX         Max jobs claimed per poll        (default 5)
    LABEL_WIDTH_MM    Media width  for ``lp -o media`` (default 25)
    LABEL_HEIGHT_MM   Media height for ``lp -o media`` (default 52)
    LP_MEDIA          Override the whole media string  (default Custom.{W}x{H}mm)
    LP_EXTRA_OPTIONS  Extra ``-o`` options, space-sep  (e.g. "orientation-requested=3")
    PRINT_TIMEOUT     Seconds to wait on the lp call   (default 30)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

LOG = logging.getLogger("vintiz.print-agent")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


API_URL = _env("VINTIZ_API_URL").rstrip("/")
TOKEN = _env("RPI_AGENT_TOKEN")
CUPS_PRINTER = _env("CUPS_PRINTER")
POLL_INTERVAL = float(_env("POLL_INTERVAL", "5"))
BATCH_MAX = int(_env("BATCH_MAX", "5"))
LABEL_W = _env("LABEL_WIDTH_MM", "25")
LABEL_H = _env("LABEL_HEIGHT_MM", "52")
LP_MEDIA = _env("LP_MEDIA", f"Custom.{LABEL_W}x{LABEL_H}mm")
LP_EXTRA_OPTIONS = _env("LP_EXTRA_OPTIONS")
PRINT_TIMEOUT = float(_env("PRINT_TIMEOUT", "30"))

# Network backoff bounds (seconds) when the API is unreachable.
_BACKOFF_START = POLL_INTERVAL
_BACKOFF_MAX = 60.0
_HTTP_TIMEOUT = 20.0

_running = True


def _stop(signum, _frame):
    global _running
    LOG.info("Signal %s reçu — arrêt propre de l'agent.", signum)
    _running = False


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    """Make an authenticated request to the Vintiz API. Returns (status, json)."""
    url = f"{API_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"X-Agent-Token": TOKEN}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:  # noqa: S310 — URL from trusted config
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"detail": raw[:200]}
        return exc.code, payload


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------


def _print_pdf(pdf_bytes: bytes) -> tuple[bool, str]:
    """Print a PDF via CUPS ``lp``. Returns (success, message).

    The PDF page is already sized to the physical label, so we don't rescale —
    we only tell CUPS the media size. ``copies`` is baked into the PDF as one
    page per label, so no ``-n`` is needed.
    """
    cmd = ["lp"]
    if CUPS_PRINTER:
        cmd += ["-d", CUPS_PRINTER]
    if LP_MEDIA:
        cmd += ["-o", f"media={LP_MEDIA}"]
    for opt in LP_EXTRA_OPTIONS.split():
        cmd += ["-o", opt]

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
            fh.write(pdf_bytes)
            tmp_path = fh.name
        cmd.append(tmp_path)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=PRINT_TIMEOUT
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout or "lp a échoué").strip()[:300]
        return True, (result.stdout or "imprimé").strip()[:200]
    except FileNotFoundError:
        return False, "commande 'lp' introuvable — CUPS n'est pas installé ?"
    except subprocess.TimeoutExpired:
        return False, f"lp n'a pas répondu en {PRINT_TIMEOUT:.0f}s"
    except Exception as exc:  # noqa: BLE001 — defensive: any failure → ack error
        return False, f"erreur d'impression : {exc}"
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _handle_job(job: dict) -> None:
    """Print one claimed job and ack its outcome."""
    job_id = job.get("id")
    ref = job.get("ref") or "?"
    try:
        pdf = base64.b64decode(job["content_b64"])
    except (KeyError, ValueError) as exc:
        LOG.error("Job %s (%s) : contenu illisible (%s)", job_id, ref, exc)
        _request("POST", f"/api/labels/agent/jobs/{job_id}/ack",
                 {"success": False, "error": f"contenu illisible : {exc}"})
        return

    ok, message = _print_pdf(pdf)
    if ok:
        LOG.info("Job %s (%s) imprimé : %s", job_id, ref, message)
    else:
        LOG.error("Job %s (%s) échec impression : %s", job_id, ref, message)
    status, _ = _request(
        "POST", f"/api/labels/agent/jobs/{job_id}/ack",
        {"success": ok, "error": None if ok else message},
    )
    if status != 200:
        LOG.warning("Ack du job %s rejeté (HTTP %s)", job_id, status)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def _validate_config() -> None:
    missing = [n for n, v in (("VINTIZ_API_URL", API_URL), ("RPI_AGENT_TOKEN", TOKEN)) if not v]
    if missing:
        LOG.error("Configuration incomplète : %s manquant(s). Voir .env.example.", ", ".join(missing))
        sys.exit(2)


def run() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    _validate_config()
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    LOG.info(
        "Agent démarré → %s | imprimante CUPS=%s | media=%s | poll=%.0fs",
        API_URL, CUPS_PRINTER or "(défaut système)", LP_MEDIA, POLL_INTERVAL,
    )
    backoff = _BACKOFF_START
    while _running:
        try:
            status, payload = _request("GET", f"/api/labels/agent/jobs/next?max={BATCH_MAX}")
        except urllib.error.URLError as exc:
            LOG.warning("API injoignable (%s) — nouvelle tentative dans %.0fs", exc.reason, backoff)
            _sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)
            continue
        except Exception as exc:  # noqa: BLE001 — never let the loop die
            LOG.warning("Erreur de poll (%s) — retry dans %.0fs", exc, backoff)
            _sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)
            continue

        backoff = _BACKOFF_START  # reset on any successful contact

        if status == 503:
            LOG.warning("Agent désactivé côté serveur (RPI_AGENT_TOKEN non posé). Pause 60s.")
            _sleep(60)
            continue
        if status == 401:
            LOG.error("Jeton agent refusé (401). Vérifiez RPI_AGENT_TOKEN. Pause 60s.")
            _sleep(60)
            continue
        if status != 200:
            LOG.warning("Réponse inattendue HTTP %s : %s", status, payload.get("detail"))
            _sleep(POLL_INTERVAL)
            continue

        jobs = payload.get("jobs") or []
        if jobs:
            LOG.info("%d job(s) à imprimer.", len(jobs))
            for job in jobs:
                if not _running:
                    break
                _handle_job(job)
            # Drain quickly when busy: poll again without the idle wait.
            continue

        _sleep(POLL_INTERVAL)

    LOG.info("Agent arrêté.")


def _sleep(seconds: float) -> None:
    """Sleep in short slices so signals interrupt promptly."""
    end = time.monotonic() + seconds
    while _running and time.monotonic() < end:
        time.sleep(min(0.5, end - time.monotonic()))


if __name__ == "__main__":
    run()
