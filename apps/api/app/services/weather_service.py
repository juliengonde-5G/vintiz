import logging
import os
from datetime import datetime

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

# Realistic seasonal fallback data for Vernon (Normandie)
def _get_seasonal_fallback() -> dict:
    """Return a plausible seasonal weather estimate for Vernon when API key is unavailable."""
    month = datetime.now().month
    # Spring/Summer
    if 4 <= month <= 9:
        return {"description": "Partiellement nuageux", "temp": 16.0, "feels_like": 14.5,
                "temp_min": 11.0, "temp_max": 20.0,
                "humidity": 70, "icon": "02d", "wind_speed": 3.2, "city": "Vernon"}
    # Autumn/Winter
    return {"description": "Couvert avec averses", "temp": 8.0, "feels_like": 5.5,
            "temp_min": 4.0, "temp_max": 11.0,
            "humidity": 85, "icon": "09d", "wind_speed": 5.1, "city": "Vernon"}


async def _fetch_current_weather_uncached() -> dict:
    """Direct OpenWeather call — wrapped by the cached entry-point below."""
    if not OPENWEATHER_API_KEY:
        return _get_seasonal_fallback()

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
        return {"description": "Erreur météo", "temp": 0, "feels_like": 0, "humidity": 0, "icon": "01d", "wind_speed": 0, "city": "Vernon"}


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


async def _fetch_weather_forecast_uncached() -> list:
    if not OPENWEATHER_API_KEY:
        from datetime import date, timedelta
        base = _get_seasonal_fallback()
        days = []
        for i in range(1, 6):
            d = date.today() + timedelta(days=i)
            days.append({
                "date": str(d),
                "description": base["description"],
                "temp_min": base["temp_min"],
                "temp_max": base["temp_max"],
                "icon": base["icon"],
            })
        return days
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={
                    "lat": VERNON_LAT, "lon": VERNON_LON,
                    "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "fr", "cnt": 8
                }
            )
            resp.raise_for_status()
            data = resp.json()
            # Group by day
            days: dict[str, dict] = {}
            for item in data["list"]:
                day = item["dt_txt"][:10]
                if day not in days:
                    days[day] = {
                        "description": item["weather"][0]["description"].capitalize(),
                        "temp_min": item["main"]["temp_min"],
                        "temp_max": item["main"]["temp_max"],
                        "icon": item["weather"][0]["icon"],
                    }
            return [{"date": k, **v} for k, v in list(days.items())[:5]]
    except Exception:
        logger.exception("OpenWeather forecast call failed")
        return []
