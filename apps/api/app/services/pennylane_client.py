"""Client HTTP Pennylane — POST journal_entries vers l'API externe."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_log = logging.getLogger("vintiz.pennylane")

# API externe Pennylane v1 — le client public officiel. Une tentative
# précédente de pointer sur ``/external/v2`` renvoyait 404 sur
# ``/journal_entries`` (l'endpoint n'existe pas à cette base). Le rollback
# auto live dans ``accounting_service.py`` corrige toute config persistée.
# Base surchargeable via ``AccountingConfig.pennylane_api_url``.
DEFAULT_API_URL = "https://app.pennylane.com/api/external/v1"


@dataclass
class JournalEntryLine:
    account_number: str
    account_label: str
    debit: float
    credit: float
    label: str


@dataclass
class JournalEntry:
    date: date
    label: str
    journal_code: str
    lines: list[JournalEntryLine] = field(default_factory=list)
    currency: str = "EUR"


class PennylaneError(RuntimeError):
    """Raised when Pennylane API call fails after retries."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class PennylaneClient:
    def __init__(self, api_key: str, api_url: str = DEFAULT_API_URL) -> None:
        self._api_key = api_key
        self._base = api_url.rstrip("/")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self._base}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")[:500]
            raise PennylaneError(
                f"Pennylane {method} {path} → HTTP {exc.code}: {raw}",
                status_code=exc.code,
            ) from exc
        except URLError as exc:
            raise PennylaneError(f"Pennylane network error: {exc.reason}") from exc

    def _call_with_retry(
        self, method: str, path: str, body: dict | None = None, max_attempts: int = 3
    ) -> dict:
        delays = [2, 4, 8]
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                return self._call(method, path, body)
            except PennylaneError as exc:
                last_exc = exc
                if exc.status_code and 400 <= exc.status_code < 500:
                    raise  # 4xx : pas la peine de retry
                if attempt < max_attempts - 1:
                    time.sleep(delays[attempt])
        raise last_exc  # type: ignore[misc]

    def ping(self) -> bool:
        """Teste la connexion. ``GET /companies`` est un probe léger v1
        disponible sur tout dossier."""
        try:
            self._call("GET", "/companies")
            return True
        except PennylaneError:
            return False

    def create_journal_entry(self, entry: JournalEntry) -> str:
        """Crée une écriture comptable (API v1). Retourne l'id Pennylane.

        Schéma v1 : ``POST /journal_entries`` avec
        ``ledger_event_lines_attributes`` portant ``currency_amount`` +
        ``direction`` ("debit"|"credit"). ``journal_code`` route vers le bon
        journal (VTE par défaut).
        """
        lines_payload = []
        for line in entry.lines:
            if line.debit > 0:
                lines_payload.append({
                    "account_number": line.account_number,
                    "label": line.label,
                    "currency_amount": round(line.debit, 2),
                    "direction": "debit",
                })
            elif line.credit > 0:
                lines_payload.append({
                    "account_number": line.account_number,
                    "label": line.label,
                    "currency_amount": round(line.credit, 2),
                    "direction": "credit",
                })

        payload = {
            "journal_entry": {
                "date": entry.date.isoformat(),
                "label": entry.label,
                "currency": entry.currency,
                "journal_code": entry.journal_code,
                "ledger_event_lines_attributes": lines_payload,
            }
        }
        _log.info("Pennylane v1 → POST /journal_entries (%d lignes)", len(lines_payload))
        result = self._call_with_retry("POST", "/journal_entries", payload)
        entry_data = result.get("journal_entry", result)
        return str(entry_data.get("id", ""))
