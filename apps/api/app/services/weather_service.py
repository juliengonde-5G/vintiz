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

# Realistic seasonal fallback data for Vernon (Normandie)
def _get_seasonal_fallback() -> dict:
    """Plausible seasonal weather estimate for Vernon when no API key is set.

    Varies deterministically per calendar day (a gentle temperature wave +
    rotating sky state) so the dashboard, the 5-day forecast and the saved
    daily history snapshots aren't all identical — the previous constant made
    the "14 derniers jours" report show the exact same weather every day.
    """
    from datetime import date

    today = date.today()
    if 4 <= today.month <= 9:  # Spring / Summer
        base_min, base_max, humidity, wind = 11.0, 20.0, 70, 3.2
        states = [
            ("Ensoleillé", "01d"), ("Partiellement nuageux", "02d"),
            ("Nuageux", "03d"), ("Averses éparses", "09d"),
        ]
    else:  # Autumn / Winter
        base_min, base_max, humidity, wind = 4.0, 11.0, 85, 5.1
        states = [
            ("Couvert", "04d"), ("Couvert avec averses", "09d"),
            ("Nuageux", "03d"), ("Brumeux", "50d"),
        ]
    o = today.toordinal()
    delta = [0.0, 1.5, -1.0, 2.5, -0.5, 1.0, -1.5][o % 7]
    desc, icon = states[o % len(states)]
    tmin = round(base_min + delta, 1)
    tmax = round(base_max + delta, 1)
    temp = round((tmin + tmax) / 2, 1)
    return {
        "description": desc, "temp": temp, "feels_like": round(temp - 1.5, 1),
        "temp_min": tmin, "temp_max": tmax,
        "humidity": humidity + (o % 11) - 5, "icon": icon,
        "wind_speed": round(wind + (o % 3) - 1, 1), "city": "Vernon",
    }


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


def _seasonal_forecast_fallback() -> list:
    """Varied 5-day fallback when no API key is set.

    The previous version copied a single seasonal estimate to all 5 days, so
    the dashboard showed the exact same weather every day. We now vary each
    day deterministically (a gentle temperature wave + rotating sky states)
    and split morning / afternoon so the widget still looks alive offline.
    """
    from datetime import date, timedelta

    base = _get_seasonal_fallback()
    states = [
        ("Ensoleillé", "01d"),
        ("Partiellement nuageux", "02d"),
        ("Nuageux", "03d"),
        ("Couvert", "04d"),
        ("Averses éparses", "09d"),
    ]
    out = []
    for i in range(1, 6):
        d = date.today() + timedelta(days=i)
        # Deterministic wave so consecutive days differ but stay seasonal.
        delta = [0.0, 1.5, -1.0, 2.5, -0.5][(i - 1) % 5]
        tmin = round(base["temp_min"] + delta, 1)
        tmax = round(base["temp_max"] + delta, 1)
        desc, icon = states[(d.toordinal() + i) % len(states)]
        am_desc, am_icon = states[(d.toordinal()) % len(states)]
        pm_desc, pm_icon = states[(d.toordinal() + 2) % len(states)]
        out.append({
            "date": str(d),
            "description": desc,
            "temp_min": tmin,
            "temp_max": tmax,
            "icon": icon,
            "morning": {"temp": round((tmin + tmax) / 2 - 1.5, 1), "description": am_desc, "icon": am_icon.replace("d", "d")},
            "afternoon": {"temp": tmax, "description": pm_desc, "icon": pm_icon},
        })
    return out


def _slot_summary(item: dict) -> dict:
    return {
        "temp": round(item["main"]["temp"], 1),
        "description": item["weather"][0]["description"].capitalize(),
        "icon": item["weather"][0]["icon"],
    }


async def _fetch_weather_forecast_uncached() -> list:
    if not OPENWEATHER_API_KEY:
        return _seasonal_forecast_fallback()
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
