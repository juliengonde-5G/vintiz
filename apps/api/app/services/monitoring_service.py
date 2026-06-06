"""Service de monitoring — health checks des services externes.

Vérifie : PostgreSQL, Pennylane, SumUp, Brevo (email). Peut envoyer une
alerte email quand un ou plusieurs services sont KO (``check_and_alert``).

Les credentials sont lus selon les conventions de l'app :
- Pennylane : config comptable persistée en base (``AccountingService``).
- SumUp / Brevo : ``app_config`` (section ``sumup`` / ``email``) avec repli
  sur les variables d'environnement.
Un service non configuré est reporté ``healthy`` avec le détail « Non
configuré » (absence de clé = pas une panne).
"""
from __future__ import annotations

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
        results: list[ServiceStatus] = [
            await self._check_db(),
            await self._check_pennylane(),
            self._check_sumup(),
            self._check_brevo(),
            ServiceStatus(name="api", healthy=True, latency_ms=0, detail="OK"),
        ]
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
            # 4xx = service joignable (souci d'auth, pas une panne)
            return exc.code < 500, ms, f"HTTP {exc.code}"
        except (URLError, Exception) as exc:
            ms = round((time.monotonic() - t0) * 1000, 1)
            return False, ms, str(exc)[:120]

    async def _check_pennylane(self) -> ServiceStatus:
        # La clé Pennylane vit dans la config comptable persistée en base.
        api_key = ""
        api_url = ""
        if self.db is not None:
            try:
                from app.services.accounting_service import AccountingService
                cfg = await AccountingService(self.db).get_config()
                api_key = (cfg.pennylane_api_key or "").strip()
                api_url = (cfg.pennylane_api_url or "").strip()
            except Exception as exc:
                _log.debug("Pennylane config read failed: %s", exc)
        if not api_key:
            return ServiceStatus(name="pennylane", healthy=True, detail="Non configuré")

        try:
            from app.services.pennylane_client import DEFAULT_API_URL
            base = api_url or DEFAULT_API_URL
        except Exception:
            base = api_url or "https://app.pennylane.com/api/external/v2"
        ok, ms, detail = self._http_get(
            f"{base.rstrip('/')}/journals",
            {"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        return ServiceStatus(name="pennylane", healthy=ok, latency_ms=ms, detail=detail)

    def _check_sumup(self) -> ServiceStatus:
        api_key = ""
        try:
            from app.services.app_config import get_section
            api_key = (get_section("sumup") or {}).get("api_key", "") or ""
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
            api_key = (get_section("email") or {}).get("brevo_api_key", "") or ""
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

            to = os.getenv("MONITORING_ALERT_EMAIL", "") or os.getenv(
                "BACKUP_ALERT_EMAIL", ""
            )
            if not to:
                try:
                    from app.services.app_config import get_section
                    to = (get_section("email") or {}).get("from_address", "") or ""
                except Exception:
                    to = ""
            if not to:
                _log.warning("Monitoring: %d service(s) KO mais aucun email d'alerte configuré", len(ko))
                return

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
                to=to,
                subject=f"⚠️ Vintiz — {len(ko)} service(s) KO ({', '.join(s.name for s in ko)})",
                html=html,
                tags=["monitoring", "alert"],
            ))
        except Exception as exc:
            _log.warning("Monitoring alert email failed: %s", exc)
