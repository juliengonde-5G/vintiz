"""Service de monitoring — health checks de tous les services externes.

Vérifie : DB, Pennylane API, SumUp API, Brevo API.
Peut envoyer une alerte email si un service passe de healthy à KO.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_log = logging.getLogger("vintiz.monitoring")

SERVICES = ["db", "pennylane", "sumup", "brevo", "api"]


@dataclass
class ServiceStatus:
    name: str
    healthy: bool
    latency_ms: float | None = None
    detail: str = ""
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class MonitoringReport:
    all_healthy: bool
    checked_at: str
    services: list[ServiceStatus]


class MonitoringService:
    def __init__(self, db=None) -> None:
        self.db = db

    async def check_all(self) -> MonitoringReport:
        results: list[ServiceStatus] = []
        results.append(await self._check_db())
        results.append(self._check_pennylane())
        results.append(self._check_sumup())
        results.append(self._check_brevo())
        results.append(ServiceStatus(name="api", healthy=True, latency_ms=0, detail="OK"))
        all_ok = all(s.healthy for s in results)
        return MonitoringReport(
            all_healthy=all_ok,
            checked_at=datetime.now(timezone.utc).isoformat(),
            services=results,
        )

    async def _check_db(self) -> ServiceStatus:
        t0 = time.monotonic()
        try:
            from sqlalchemy import text
            await self.db.execute(text("SELECT 1"))
            ms = round((time.monotonic() - t0) * 1000, 1)
            return ServiceStatus(name="db", healthy=True, latency_ms=ms, detail="PostgreSQL OK")
        except Exception as exc:
            ms = round((time.monotonic() - t0) * 1000, 1)
            return ServiceStatus(name="db", healthy=False, latency_ms=ms, detail=str(exc)[:200])

    def _http_get(self, url: str, headers: dict, timeout: int = 8) -> tuple[bool, float, str]:
        t0 = time.monotonic()
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                ms = round((time.monotonic() - t0) * 1000, 1)
                return True, ms, f"HTTP {resp.status}"
        except HTTPError as exc:
            ms = round((time.monotonic() - t0) * 1000, 1)
            # 4xx = service accessible (auth problem, not down)
            healthy = exc.code < 500
            return healthy, ms, f"HTTP {exc.code}"
        except (URLError, Exception) as exc:
            ms = round((time.monotonic() - t0) * 1000, 1)
            return False, ms, str(exc)[:120]

    def _check_pennylane(self) -> ServiceStatus:
        try:
            from app.services.app_config import get_section
            api_key = (get_section("accounting") or {}).get("pennylane_api_key", "")
        except Exception:
            api_key = ""
        if not api_key:
            # Try env or DB — if not configured, report as "not configured"
            return ServiceStatus(name="pennylane", healthy=True, detail="Non configuré")

        ok, ms, detail = self._http_get(
            "https://app.pennylane.com/api/external/v1/companies",
            {"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        return ServiceStatus(name="pennylane", healthy=ok, latency_ms=ms, detail=detail)

    def _check_sumup(self) -> ServiceStatus:
        api_key = ""
        try:
            from app.services.app_config import get_section
            api_key = (get_section("sumup") or {}).get("api_key", "")
        except Exception:
            pass
        if not api_key:
            api_key = os.getenv("SUMUP_API_KEY", "")
        if not api_key:
            return ServiceStatus(name="sumup", healthy=True, detail="Non configuré")

        ok, ms, detail = self._http_get(
            "https://api.sumup.com/v0.1/me",
            {"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        return ServiceStatus(name="sumup", healthy=ok, latency_ms=ms, detail=detail)

    def _check_brevo(self) -> ServiceStatus:
        api_key = ""
        try:
            from app.services.app_config import get_section
            api_key = (get_section("email") or {}).get("brevo_api_key", "")
        except Exception:
            pass
        if not api_key:
            api_key = os.getenv("BREVO_API_KEY", "")
        if not api_key:
            return ServiceStatus(name="brevo", healthy=True, detail="Non configuré (simulation)")

        ok, ms, detail = self._http_get(
            "https://api.brevo.com/v3/account",
            {"api-key": api_key, "Accept": "application/json"},
        )
        return ServiceStatus(name="brevo", healthy=ok, latency_ms=ms, detail=detail)

    async def check_and_alert(self) -> None:
        """Lance les checks et envoie un email si un service est KO."""
        report = await self.check_all()
        if report.all_healthy:
            return
        ko = [s for s in report.services if not s.healthy]
        try:
            from app.services.email_gateway import EmailMessage, send_email
            from app.services.accounting_service import AccountingService
            from sqlalchemy.ext.asyncio import AsyncSession

            cfg_email = os.getenv("MONITORING_ALERT_EMAIL", "vernon@vintiz.fr")
            rows = "".join(
                f"<tr><td style='padding:6px 12px'>{s.name}</td>"
                f"<td style='padding:6px 12px;color:#dc2626;font-weight:bold'>KO</td>"
                f"<td style='padding:6px 12px;font-size:12px'>{s.detail}</td></tr>"
                for s in ko
            )
            html = f"""
<p><strong>⚠️ Vintiz Monitoring — {len(ko)} service(s) KO</strong></p>
<table border="1" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
  <thead><tr><th style='padding:6px 12px'>Service</th><th>Statut</th><th>Détail</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
<p style='color:#888;font-size:12px'>Vérification : {report.checked_at}</p>
"""
            send_email(EmailMessage(
                to=cfg_email,
                subject=f"⚠️ Vintiz — {len(ko)} service(s) KO ({', '.join(s.name for s in ko)})",
                html=html,
                tags=["monitoring", "alert"],
            ))
        except Exception as exc:
            _log.warning("Monitoring alert email failed: %s", exc)
