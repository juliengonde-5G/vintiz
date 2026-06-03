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

# API externe Pennylane v2 (la v1 « ledger events » est dépréciée).
# Base surchargeable via AccountingConfig.pennylane_api_url ; pour un
# déploiement existant qui a encore l'URL v1 en base, l'éditer dans
# /settings > Comptabilité ou laisser le fallback v2 ci-dessous.
DEFAULT_API_URL = "https://app.pennylane.com/api/external/v2"


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
        """Teste la connexion. En v2, GET /journals est un probe léger et
        toujours disponible (la liste des journaux du dossier). Retourne True
        si l'API répond 2xx.
        """
        try:
            self._call("GET", "/journals")
            return True
        except PennylaneError:
            return False

    def create_journal_entry(self, entry: JournalEntry) -> str:
        """Crée une écriture comptable (API v2). Retourne l'id Pennylane.

        Schéma v2 : ``POST /journal_entries`` avec des lignes portant des
        champs ``debit``/``credit`` distincts (montants décimaux en chaîne),
        au lieu du couple ``direction`` + ``currency_amount`` de la v1.
        ``journal_code`` reste accepté pour router l'écriture vers le bon
        journal (VTE par défaut).
        """
        lines_payload = []
        for line in entry.lines:
            if line.debit > 0:
                lines_payload.append({
                    "account_number": line.account_number,
                    "label": line.label,
                    "debit": f"{round(line.debit, 2):.2f}",
                    "credit": "0.00",
                })
            elif line.credit > 0:
                lines_payload.append({
                    "account_number": line.account_number,
                    "label": line.label,
                    "debit": "0.00",
                    "credit": f"{round(line.credit, 2):.2f}",
                })

        payload = {
            "journal_entry": {
                "date": entry.date.isoformat(),
                "label": entry.label,
                "currency": entry.currency,
                "journal_code": entry.journal_code,
                "lines": lines_payload,
            }
        }
        _log.info("Pennylane v2 → POST /journal_entries (%d lignes)", len(lines_payload))
        result = self._call_with_retry("POST", "/journal_entries", payload)
        # v2 renvoie {"journal_entry": {"id": ...}} (ou l'objet à plat).
        entry_data = result.get("journal_entry", result)
        return str(entry_data.get("id", ""))
