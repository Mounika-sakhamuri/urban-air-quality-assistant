"""Pydantic data models for request validation and typed API responses."""

from pydantic import BaseModel, Field


class ActionPlanRequest(BaseModel):
    """Validated user input payload for generating an air quality protection plan."""

    city: str = Field(..., min_length=2, max_length=100, description="Target city name")
    aqi: int = Field(..., ge=0, le=999, description="Current US Air Quality Index")
    routine: str = Field(..., min_length=3, max_length=500, description="Household and commute profile")
    home_setup: str = Field(..., min_length=3, max_length=500, description="Indoor setup and ventilation")


class TimeRoutineItem(BaseModel):
    """Single time-slotted daily routine recommendation."""

    slot: str
    title: str
    action: str
    why: str


class SustainableAlternativeItem(BaseModel):
    """Actionable low-emission commute or lifestyle swap."""

    title: str
    action: str
    impact: str


class IndoorHackItem(BaseModel):
    """Practical indoor air quality improvement measure."""

    title: str
    action: str
    benefit: str


class AirQualityPlan(BaseModel):
    """Structured AI-generated air quality protection and emission reduction plan."""

    risk_summary: str
    inhaled_bio_dose_ug: int = Field(..., ge=0)
    safest_window: str
    exposure_prevented_ug: int = Field(..., ge=0)
    time_routines: list[TimeRoutineItem]
    sustainable_alternatives: list[SustainableAlternativeItem]
    indoor_air_hacks: list[IndoorHackItem]


class ActionPlanResponse(BaseModel):
    """Top-level response envelope for generated air quality plans."""

    status: str
    city: str
    aqi: int
    plan: AirQualityPlan


class ForecastPoint(BaseModel):
    """Single hourly temperature forecast point."""

    time: str
    temp: int


class TelemetryResponse(BaseModel):
    """Real-time city air quality, pollutant, coordinate, and weather telemetry."""

    city: str
    lat: float
    lon: float
    aqi: int
    pm2_5: float
    pm10: float
    no2: float
    o3: float
    temp_c: int
    is_day: int
    forecast: list[ForecastPoint]