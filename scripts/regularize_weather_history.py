#!/usr/bin/env python3
"""Régularise l'historique météo (weather_history) avec la VRAIE météo passée.

Contexte : sans OPENWEATHER_API_KEY, l'ancien fallback saisonnier fabriquait
une météo plausible que ``/api/admin/weather`` persistait chaque jour dans le
setting ``weather_history`` — 30 jours d'historique faux (fallback supprimé
le 2026-07-18 : désormais l'indisponibilité est affichée, jamais inventée).

Ce script REMPLACE l'historique pollué par les relevés réels de Vernon issus
d'Open-Meteo (API d'archives publique, gratuite, sans clé) : min/max du jour,
état du ciel (code WMO → libellé + icône). Principe « pas d'invention » :
un jour sans donnée chez Open-Meteo est signalé et reste ABSENT de
l'historique (le cahier affiche alors « — »), il n'est pas comblé.

Le jour courant n'est pas écrit : il sera enregistré par le dashboard via
OpenWeather une fois la clé configurée.

Usage :
    # Aperçu (n'écrit rien)
    PYTHONPATH=apps/api python scripts/regularize_weather_history.py --dry-run

    # Exécution réelle (remplace weather_history)
    PYTHONPATH=apps/api python scripts/regularize_weather_history.py --confirm

    # En prod
    docker exec -it vintiz-api python scripts/regularize_weather_history.py --confirm
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Rendre ``import app.core...`` fonctionnel en dev ET en Docker (/app).
_HERE = Path(__file__).resolve()
for _candidate in (
    _HERE.parents[1] / "apps" / "api",   # layout dev (repo)
    _HERE.parents[1],                    # layout Docker prod (/app)
):
    if (_candidate / "app" / "core" / "database.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    raise SystemExit(
        "regularize_weather_history: package `app` introuvable — vérifié "
        f"{_HERE.parents[1] / 'apps' / 'api'} et {_HERE.parents[1]}"
    )

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.database import async_session  # noqa: E402
from app.models.audit import Settings  # noqa: E402
from app.services.weather_service import VERNON_LAT, VERNON_LON  # noqa: E402

HISTORY_DAYS = 30

# Codes météo WMO (Open-Meteo) → libellé FR + icône OpenWeather (le widget
# construit ses URLs d'icônes sur openweathermap.org).
_WMO: list[tuple[tuple[int, ...], str, str]] = [
    ((0,), "Ciel dégagé", "01d"),
    ((1,), "Généralement dégagé", "02d"),
    ((2,), "Partiellement nuageux", "03d"),
    ((3,), "Couvert", "04d"),
    ((45, 48), "Brouillard", "50d"),
    ((51, 53, 55, 56, 57), "Bruine", "09d"),
    ((61, 63, 65, 66, 67), "Pluie", "10d"),
    ((71, 73, 75, 77), "Neige", "13d"),
    ((80, 81, 82), "Averses", "09d"),
    ((85, 86), "Averses de neige", "13d"),
    ((95, 96, 99), "Orage", "11d"),
]


def _wmo_label(code: int | None) -> tuple[str, str]:
    if code is None:
        return ("Inconnu", "01d")
    for codes, label, icon in _WMO:
        if code in codes:
            return (label, icon)
    return ("Inconnu", "01d")


async def _fetch_real_history() -> dict[str, dict]:
    """Relevés quotidiens réels des 30 derniers jours à Vernon (Open-Meteo)."""
    params = {
        "latitude": VERNON_LAT,
        "longitude": VERNON_LON,
        "daily": "weather_code,temperature_2m_min,temperature_2m_max,wind_speed_10m_max",
        "past_days": HISTORY_DAYS,
        "forecast_days": 1,
        "timezone": "Europe/Paris",
        "wind_speed_unit": "ms",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
        resp.raise_for_status()
        daily = (resp.json() or {}).get("daily") or {}

    days: dict[str, dict] = {}
    dates = daily.get("time") or []
    for i, day in enumerate(dates):
        def _at(key: str):
            vals = daily.get(key) or []
            return vals[i] if i < len(vals) else None

        tmin, tmax = _at("temperature_2m_min"), _at("temperature_2m_max")
        if tmin is None or tmax is None:
            continue  # pas de relevé → le jour restera absent (pas d'invention)
        desc, icon = _wmo_label(_at("weather_code"))
        snapshot = {
            "date": day,
            "temp": round((tmin + tmax) / 2, 1),
            "description": desc,
            "icon": icon,
            "temp_min": round(tmin, 1),
            "temp_max": round(tmax, 1),
            # humidité non fournie en historique quotidien → on ne l'invente
            # pas (champ absent ; les lecteurs utilisent .get()).
            "source": "open-meteo-backfill",
        }
        wind = _at("wind_speed_10m_max")
        if wind is not None:
            snapshot["wind_speed"] = round(wind, 1)
        days[day] = snapshot
    return days


async def run(dry_run: bool) -> None:
    today = date.today()
    wanted = [str(today - timedelta(days=n)) for n in range(HISTORY_DAYS, 0, -1)]

    print(
        f"Récupération des relevés réels Vernon ({VERNON_LAT}, {VERNON_LON}) "
        f"sur {HISTORY_DAYS} jours via Open-Meteo…\n"
    )
    real = await _fetch_real_history()
    entries = [real[d] for d in wanted if d in real]
    missing = [d for d in wanted if d not in real]

    for e in entries:
        wind = f" · vent {e['wind_speed']} m/s" if "wind_speed" in e else ""
        print(
            f"  {e['date']}  {e['temp_min']:>5.1f}° / {e['temp_max']:>4.1f}°  "
            f"{e['description']}{wind}"
        )
    if missing:
        print(f"\n⚠️  {len(missing)} jour(s) SANS relevé (resteront absents, pas inventés) : {', '.join(missing)}")

    async with async_session() as db:
        setting = (
            await db.execute(select(Settings).where(Settings.key == "weather_history"))
        ).scalar_one_or_none()
        old_count = len(json.loads(setting.value or "[]")) if setting else 0
        print(
            f"\nHistorique actuel : {old_count} entrée(s) (fallback fabriqué) "
            f"→ remplacement par {len(entries)} relevé(s) réel(s)."
        )

        if dry_run:
            print("\n[DRY-RUN] Aucune écriture. Relancer avec --confirm pour appliquer.")
            return

        payload = json.dumps(entries)
        if setting:
            setting.value = payload
        else:
            db.add(Settings(key="weather_history", value=payload))
        await db.commit()
        print(f"\nOK — weather_history régularisé ({len(entries)} jour(s) réels).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remplace l'historique météo fabriqué par les relevés réels Open-Meteo"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Aperçu sans écriture")
    group.add_argument("--confirm", action="store_true", help="Exécute réellement")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
