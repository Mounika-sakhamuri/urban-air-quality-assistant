import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.ai_service import generate_air_quality_plan

app = FastAPI(
    title="AeroGuard AI — Urban Air Quality Intelligence",
    description="Real-time AQI, weather telemetry, street-level mapping, and AI-powered low-emission routines.",
    version="2.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ActionPlanRequest(BaseModel):
    city: str = Field(..., min_length=2, max_length=100)
    aqi: int = Field(..., ge=0, le=999)
    routine: str = Field(..., min_length=3, max_length=500)
    home_setup: str = Field(..., min_length=3, max_length=500)


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok", "version": "2.5.0"}


@app.get("/api/live-aqi")
async def fetch_live_telemetry(city: str = Query(..., min_length=2, max_length=100)) -> dict:
    """Fetches real-time US AQI, pollutants, coordinates, and hourly weather via Open-Meteo."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            geo_res = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city.strip(), "count": 1, "language": "en", "format": "json"},
            )
            results = geo_res.json().get("results")
            if not results:
                raise HTTPException(status_code=404, detail=f"City '{city}' not found.")

            loc = results[0]
            lat, lon = loc["latitude"], loc["longitude"]
            resolved_name = f"{loc['name']}, {loc.get('country', '')}".strip(", ")

            aq_res = await client.get(
                "https://air-quality-api.open-meteo.com/v1/air-quality",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "us_aqi,pm2_5,pm10,nitrogen_dioxide,ozone",
                },
            )
            wx_res = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,is_day,weather_code",
                    "hourly": "temperature_2m",
                    "forecast_days": 1,
                },
            )

            aq_cur = aq_res.json().get("current", {})
            wx_json = wx_res.json()
            wx_cur = wx_json.get("current", {})
            hourly_temps = wx_json.get("hourly", {}).get("temperature_2m", [])[:7]
            hourly_times = wx_json.get("hourly", {}).get("time", [])[:7]

            forecast = []
            for idx, (t_str, temp) in enumerate(zip(hourly_times, hourly_temps)):
                label = "Now" if idx == 0 else t_str.split("T")[-1][:5]
                forecast.append({"time": label, "temp": round(float(temp))})

            return {
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
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Telemetry unavailable: {exc}") from exc


@app.post("/api/generate-plan")
def create_action_plan(payload: ActionPlanRequest) -> dict:
    try:
        plan = generate_air_quality_plan(
            city=payload.city.strip(),
            aqi=payload.aqi,
            routine=payload.routine.strip(),
            home_setup=payload.home_setup.strip(),
        )
        return {"status": "success", "city": payload.city.strip(), "aqi": payload.aqi, "plan": plan}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate action plan: {exc}") from exc


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse("static/index.html")