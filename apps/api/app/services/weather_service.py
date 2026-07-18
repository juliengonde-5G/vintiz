import logging
import os

import httpx

from app.core.cache import cache_get_or_set

logger = logging.getLogger("vintiz")

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
VERNON_LAT = 49.0937
VERNON_LON = 1.4833

# Cache TTLs — current weather refreshed every 15 min is plenty for a
# boutique dashboard ; the 5-day forecast doesn't move that fast either.
_CURRENT_TTL_SECONDS = 900   # 15 minutes
_FORECAST_TTL_SECONDS = 3600  # 1 hour

def _unavailable(reason: str) -> dict:
    """Payload explicite « météo indisponible » — on n'invente JAMAIS de météo.

    Décision 2026-07-18 : l'ancien fallback saisonnier fabriquait des données
    plausibles sans clé API, et ``/api/admin/weather`` les a persistées 30 jours
    dans ``weather_history`` comme si c'était la réalité. Désormais : pas de
    donnée réelle → indisponibilité affichée telle quelle (widget, cahier) et
    rien n'est écrit dans l'historique."""
    return {"unavailable": True, "reason": reason, "city": "Vernon"}


async def _fetch_current_weather_uncached() -> dict:
    """Direct OpenWeather call — wrapped by the cached entry-point below."""
    if not OPENWEATHER_API_KEY:
        return _unavailable("OPENWEATHER_API_KEY non configurée")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "lat": VERNON_LAT, "lon": VERNON_LON,
                    "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "fr"
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "description": data["weather"][0]["description"].capitalize(),
                "temp": round(data["main"]["temp"], 1),
                "feels_like": round(data["main"]["feels_like"], 1),
                "temp_min": round(data["main"]["temp_min"], 1),
                "temp_max": round(data["main"]["temp_max"], 1),
                "humidity": data["main"]["humidity"],
                "icon": data["weather"][0]["icon"],
                "wind_speed": round(data.get("wind", {}).get("speed", 0), 1),
                "city": "Vernon",
            }
    except Exception:
        logger.exception("OpenWeather call failed")
        return _unavailable("Erreur d'appel OpenWeather")


async def get_current_weather() -> dict:
    """Fetch current weather for Vernon (27200), Redis-cached 15 min.

    Without the cache, every dashboard auto-refresh (60 s) × every open admin
    tab burned an OpenWeather call — quota gone in a day. 15 min is enough
    granularity for a retail dashboard.
    """
    return await cache_get_or_set(
        key="vintiz:weather:current:vernon",
        ttl=_CURRENT_TTL_SECONDS,
        factory=_fetch_current_weather_uncached,
    )


async def get_weather_forecast() -> list:
    """Fetch 5-day forecast for Vernon, Redis-cached 1 h."""
    return await cache_get_or_set(
        key="vintiz:weather:forecast:vernon",
        ttl=_FORECAST_TTL_SECONDS,
        factory=_fetch_weather_forecast_uncached,
    )


def _slot_summary(item: dict) -> dict:
    return {
        "temp": round(item["main"]["temp"], 1),
        "description": item["weather"][0]["description"].capitalize(),
        "icon": item["weather"][0]["icon"],
    }


async def _fetch_weather_forecast_uncached() -> list:
    # Pas de clé → pas de prévisions. On n'invente rien : liste vide, le
    # widget n'affiche simplement aucun jour.
    if not OPENWEATHER_API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={
                    "lat": VERNON_LAT, "lon": VERNON_LON,
                    "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "fr",
                    # 40 × 3 h = 5 full days. The old cnt=8 only covered ~24 h,
                    # so every "day" after the first collapsed to the same slot.
                    "cnt": 40,
                }
            )
            resp.raise_for_status()
            data = resp.json()
            # Aggregate per calendar day: real min/max across all slots, plus a
            # morning (~09–12 h) and afternoon (~15 h) detail slot.
            days: dict[str, dict] = {}
            for item in data["list"]:
                day = item["dt_txt"][:10]
                hour = int(item["dt_txt"][11:13])
                bucket = days.setdefault(day, {
                    "temp_min": item["main"]["temp_min"],
                    "temp_max": item["main"]["temp_max"],
                    "slots": [],
                    "morning": None,
                    "afternoon": None,
                })
                bucket["temp_min"] = min(bucket["temp_min"], item["main"]["temp_min"])
                bucket["temp_max"] = max(bucket["temp_max"], item["main"]["temp_max"])
                bucket["slots"].append(item)
                if 9 <= hour <= 12 and bucket["morning"] is None:
                    bucket["morning"] = _slot_summary(item)
                if 15 <= hour <= 18 and bucket["afternoon"] is None:
                    bucket["afternoon"] = _slot_summary(item)

            result = []
            for day, b in list(days.items())[:5]:
                slots = b["slots"]
                # Headline description = midday slot when available, else first.
                midday = next(
                    (s for s in slots if 11 <= int(s["dt_txt"][11:13]) <= 14),
                    slots[len(slots) // 2] if slots else None,
                )
                headline = _slot_summary(midday) if midday else {
                    "temp": round(b["temp_max"], 1), "description": "", "icon": "01d",
                }
                result.append({
                    "date": day,
                    "description": headline["description"],
                    "temp_min": round(b["temp_min"], 1),
                    "temp_max": round(b["temp_max"], 1),
                    "icon": headline["icon"],
                    "morning": b["morning"],
                    "afternoon": b["afternoon"],
                })
            return result
    except Exception:
        logger.exception("OpenWeather forecast call failed")
        return []
