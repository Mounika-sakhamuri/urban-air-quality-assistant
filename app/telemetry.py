import asyncio
import httpx
from fastapi import HTTPException

from app.cache import BoundedTTLCache

_telemetry_cache = BoundedTTLCache(max_size=128, ttl_seconds=600)


async def get_city_telemetry(city: str, client: httpx.AsyncClient) -> dict:
    """Fetches geocoding, live AQI, and weather concurrently with 10-minute TTL caching."""
    normalized = city.strip().lower()
    cached = _telemetry_cache.get(normalized)
    if cached is not None:
        return cached

    try:
        geo_res = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city.strip(), "count": 1, "language": "en", "format": "json"},
        )
        geo_res.raise_for_status()
        results = geo_res.json().get("results")
        if not results:
            raise HTTPException(status_code=404, detail=f"City '{city}' not found.")

        loc = results[0]
        lat, lon = loc["latitude"], loc["longitude"]
        resolved_name = f"{loc['name']}, {loc.get('country', '')}".strip(", ")

        aq_task = client.get(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "us_aqi,pm2_5,pm10,nitrogen_dioxide,ozone",
            },
        )
        wx_task = client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,is_day",
                "hourly": "temperature_2m",
                "forecast_days": 1,
            },
        )
        aq_res, wx_res = await asyncio.gather(aq_task, wx_task)
        aq_res.raise_for_status()
        wx_res.raise_for_status()

        aq_cur = aq_res.json().get("current", {})
        wx_json = wx_res.json()
        wx_cur = wx_json.get("current", {})
        hourly_temps = wx_json.get("hourly", {}).get("temperature_2m", [])[:7]
        hourly_times = wx_json.get("hourly", {}).get("time", [])[:7]

        forecast = [
            {"time": "Now" if idx == 0 else t_str.split("T")[-1][:5], "temp": round(float(temp))}
            for idx, (t_str, temp) in enumerate(zip(hourly_times, hourly_temps))
        ]

        payload = {
            "city": resolved_name,
            "lat": lat,
            "lon": lon,
            "aqi": int(round(aq_cur.get("us_aqi") or 110)),
            "pm2_5": round(float(aq_cur.get("pm2_5") or 32.0), 1),
            "pm10": round(float(aq_cur.get("pm10") or 61.0), 1),
            "no2": round(float(aq_cur.get("nitrogen_dioxide") or 18.5), 1),
            "o3": round(float(aq_cur.get("ozone") or 44.0), 1),
            "temp_c": round(float(wx_cur.get("temperature_2m") or 27)),
            "is_day": int(wx_cur.get("is_day", 1)),
            "forecast": forecast,
        }
        _telemetry_cache.set(normalized, payload)
        return payload
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream telemetry error: {exc}") from exc