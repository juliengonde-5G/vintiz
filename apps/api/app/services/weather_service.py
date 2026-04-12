import os

import httpx

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
VERNON_LAT = 49.0937
VERNON_LON = 1.4833


async def get_current_weather() -> dict:
    """Fetch current weather for Vernon (27200)."""
    if not OPENWEATHER_API_KEY:
        return {"error": "API key not configured", "condition": "Inconnu", "temp": 0, "humidity": 0, "icon": "01d"}

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
                "condition": data["weather"][0]["description"].capitalize(),
                "temp": round(data["main"]["temp"], 1),
                "temp_min": round(data["main"]["temp_min"], 1),
                "temp_max": round(data["main"]["temp_max"], 1),
                "humidity": data["main"]["humidity"],
                "icon": data["weather"][0]["icon"],
                "wind_speed": round(data.get("wind", {}).get("speed", 0), 1),
                "city": "Vernon",
            }
    except Exception as e:
        return {"error": str(e), "condition": "Inconnu", "temp": 0, "humidity": 0, "icon": "01d", "city": "Vernon"}


async def get_weather_forecast() -> list:
    """Fetch 5-day forecast for Vernon."""
    if not OPENWEATHER_API_KEY:
        return []
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
                        "condition": item["weather"][0]["description"].capitalize(),
                        "temp_min": item["main"]["temp_min"],
                        "temp_max": item["main"]["temp_max"],
                        "icon": item["weather"][0]["icon"],
                    }
            return [{"date": k, **v} for k, v in list(days.items())[:5]]
    except Exception:
        return []
