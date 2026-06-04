"""Client HTTP Pennylane — crée des écritures via l'API externe v2.

Important (migration 2026) : l'API v1 a été supprimée et l'endpoint
``POST /journal_entries`` n'existe sur aucune base (→ HTTP 404). La v2 a
renommé la ressource en ``ledger_entries`` et raisonne en **identifiants
numériques** (``journal_id``, ``ledger_account_id``) là où Vintiz manipule
des codes/numéros lisibles (``journal_code="VTE"``, ``account_number="707100"``).

Ce client résout donc les codes/numéros vers leurs IDs Pennylane via
``GET /journals`` et ``GET /ledger_accounts`` (avec cache par instance) avant
de poster l'écriture. Les montants sont envoyés en chaînes décimales et les
lignes sont équilibrées (Σdébit = Σcrédit), comme l'exige la v2.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_log = logging.getLogger("vintiz.pennylane")

# API externe Pennylane v2 (la v1 « ledger events » a été supprimée en 2026).
# Base surchargeable via ``AccountingConfig.pennylane_api_url``.
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
        # Caches par instance (un client = un export) : évite de re-télécharger
        # la liste des journaux / comptes pour chaque ligne.
        self._journal_ids: dict[str, int] = {}
        self._account_ids: dict[str, int] = {}

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

    # ------------------------------------------------------------------
    # Pagination helper (v2 = curseur)
    # ------------------------------------------------------------------

    def _iter_list(self, path: str, *, max_pages: int = 50):
        """Itère les items d'un endpoint listé v2 (pagination par curseur).

        La v2 renvoie ``{"items": [...], "has_more": bool, "next_cursor": ...}``
        (ou une liste à plat sur certaines réponses) ; on gère les deux formes
        défensivement et on plafonne le nombre de pages.
        """
        cursor: str | None = None
        for _ in range(max_pages):
            query = f"?{urlencode({'cursor': cursor})}" if cursor else ""
            payload = self._call_with_retry("GET", f"{path}{query}")
            if isinstance(payload, list):
                yield from payload
                return
            items = payload.get("items") or payload.get("data") or []
            yield from items
            if not payload.get("has_more"):
                return
            cursor = payload.get("next_cursor") or payload.get("cursor")
            if not cursor:
                return

    # ------------------------------------------------------------------
    # Résolution code/numéro → id Pennylane
    # ------------------------------------------------------------------

    def _resolve_journal_id(self, journal_code: str) -> int:
        if journal_code in self._journal_ids:
            return self._journal_ids[journal_code]
        for j in self._iter_list("/journals"):
            code = str(j.get("code") or j.get("label") or "").strip()
            jid = j.get("id")
            if code and jid is not None:
                self._journal_ids[code] = int(jid)
        if journal_code not in self._journal_ids:
            raise PennylaneError(
                f"Journal Pennylane introuvable pour le code « {journal_code} » — "
                f"créez-le dans Pennylane (Comptabilité > Journaux) ou corrigez "
                f"le code dans Paramétrage > Comptabilité.",
                status_code=404,
            )
        return self._journal_ids[journal_code]

    def _resolve_account_id(self, account_number: str) -> int:
        number = str(account_number).strip()
        if number in self._account_ids:
            return self._account_ids[number]
        # Filtre côté serveur si disponible, sinon scan complet (caché).
        found: int | None = None
        for a in self._iter_list("/ledger_accounts"):
            num = str(a.get("number") or "").strip()
            aid = a.get("id")
            if num and aid is not None:
                self._account_ids[num] = int(aid)
                if num == number:
                    found = int(aid)
        if found is None and number not in self._account_ids:
            raise PennylaneError(
                f"Compte comptable Pennylane introuvable pour le numéro "
                f"« {number} » — créez-le dans Pennylane (Plan comptable) ou "
                f"corrigez le numéro dans Paramétrage > Comptabilité.",
                status_code=404,
            )
        return self._account_ids[number]

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Teste la connexion. ``GET /journals`` est un probe léger v2
        (liste des journaux du dossier)."""
        try:
            self._call("GET", "/journals")
            return True
        except PennylaneError:
            return False

    def create_journal_entry(self, entry: JournalEntry) -> str:
        """Crée une écriture comptable (API v2 ``/ledger_entries``).

        Résout ``journal_code`` → ``journal_id`` et chaque ``account_number`` →
        ``ledger_account_id``, puis poste l'écriture. Montants en chaînes
        décimales, lignes équilibrées. Retourne l'id Pennylane de l'écriture.
        """
        journal_id = self._resolve_journal_id(entry.journal_code)

        lines_payload = []
        for line in entry.lines:
            if line.debit <= 0 and line.credit <= 0:
                continue
            lines_payload.append({
                "ledger_account_id": self._resolve_account_id(line.account_number),
                "label": line.label,
                "debit": f"{round(line.debit, 2):.2f}",
                "credit": f"{round(line.credit, 2):.2f}",
            })

        payload = {
            "date": entry.date.isoformat(),
            "label": entry.label,
            "journal_id": journal_id,
            "currency": entry.currency,
            "ledger_entry_lines": lines_payload,
        }
        _log.info(
            "Pennylane v2 → POST /ledger_entries (journal_id=%s, %d lignes)",
            journal_id, len(lines_payload),
        )
        result = self._call_with_retry("POST", "/ledger_entries", payload)
        # v2 renvoie l'objet à plat ({"id": ..., "status": "recorded"}) ;
        # on tolère aussi un éventuel enveloppage.
        entry_data = result.get("ledger_entry", result)
        return str(entry_data.get("id", ""))
