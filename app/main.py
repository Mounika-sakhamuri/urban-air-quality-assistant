from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.ai_service import generate_air_quality_plan
from app.schemas import ActionPlanRequest, TelemetryResponse
from app.telemetry import get_city_telemetry


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manages a single pooled async HTTP client across application lifetime."""
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
    async with httpx.AsyncClient(timeout=12.0, limits=limits) as http_client:
        application.state.http_client = http_client
        yield


app = FastAPI(
    title="AeroGuard AI — Urban Air Quality Intelligence",
    description="High-efficiency async AQI telemetry, street mapping, and AI-powered low-emission routines.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Lightweight health check endpoint."""
    return {"status": "ok", "version": "3.0.0"}


@app.get("/api/live-aqi", response_model=TelemetryResponse)
async def fetch_live_telemetry(
    request: Request,
    city: str = Query(..., min_length=2, max_length=100),
) -> dict:
    """Returns cached or live US AQI, pollutants, coordinates, and hourly forecast."""
    return await get_city_telemetry(city=city, client=request.app.state.http_client)


@app.post("/api/generate-plan")
async def create_action_plan(payload: ActionPlanRequest, request: Request) -> dict:
    """Generates personalized low-emission routines and indoor air hacks asynchronously."""
    plan = await generate_air_quality_plan(
        city=payload.city.strip(),
        aqi=payload.aqi,
        routine=payload.routine.strip(),
        home_setup=payload.home_setup.strip(),
        client=request.app.state.http_client,
    )
    return {
        "status": "success",
        "city": payload.city.strip(),
        "aqi": payload.aqi,
        "plan": plan,
    }


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_frontend() -> FileResponse:
    """Serves the single-page AeroGuard AI dashboard."""
    return FileResponse("static/index.html")