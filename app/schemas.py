from pydantic import BaseModel, Field


class ActionPlanRequest(BaseModel):
    """Validated payload for personalized air quality plan generation."""

    city: str = Field(..., min_length=2, max_length=100, description="Target city name")
    aqi: int = Field(..., ge=0, le=999, description="Current US AQI value")
    routine: str = Field(..., min_length=3, max_length=500, description="Household and commute profile")
    home_setup: str = Field(..., min_length=3, max_length=500, description="Indoor setup and ventilation")


class TimeRoutineItem(BaseModel):
    slot: str
    title: str
    action: str
    why: str


class SustainableAlternativeItem(BaseModel):
    title: str
    action: str
    impact: str


class IndoorHackItem(BaseModel):
    title: str
    action: str
    benefit: str


class AirQualityPlan(BaseModel):
    risk_summary: str
    inhaled_bio_dose_ug: int
    safest_window: str
    exposure_prevented_ug: int
    time_routines: list[TimeRoutineItem]
    sustainable_alternatives: list[SustainableAlternativeItem]
    indoor_air_hacks: list[IndoorHackItem]


class TelemetryResponse(BaseModel):
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
    forecast: list[dict[str, str | int]]