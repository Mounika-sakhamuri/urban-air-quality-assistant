"""Asynchronous AI orchestration service with Gemini primary, Groq fallback, and TTL caching."""

import hashlib
import json
import logging
import os
import httpx
from dotenv import load_dotenv
from google import genai

from app.cache import BoundedTTLCache
from app.schemas import AirQualityPlan

load_dotenv(override=True)
logger = logging.getLogger("aeroguard.ai")

PLAN_CACHE_TTL_SECONDS = 900
PLAN_CACHE_MAX_SIZE = 256
AQI_BUCKET_SIZE = 5
BIO_DOSE_FACTOR = 0.14
EXPOSURE_REDUCTION_RATIO = 0.46
GEMINI_MODELS = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.8-flash")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

_plan_cache = BoundedTTLCache(max_size=PLAN_CACHE_MAX_SIZE, ttl_seconds=PLAN_CACHE_TTL_SECONDS)

SYSTEM_PROMPT = """
You are AeroGuard AI, an Urban Air Quality & Environmental Health Intelligence Engine.
Given a user's city, current US AQI, household profile, primary commute, and indoor setup,
generate a structured daily protection and low-emission plan.

Respond ONLY in valid JSON matching this exact schema:
{
  "risk_summary": "1-2 concise sentences summarizing local AQI hazard and key indoor/outdoor action.",
  "inhaled_bio_dose_ug": 24,
  "safest_window": "12:30 PM – 4:00 PM",
  "exposure_prevented_ug": 19,
  "time_routines": [
    {"slot": "Morning (6:30 – 10:00 AM)", "title": "string", "action": "string", "why": "string"},
    {"slot": "Midday (1:00 – 4:00 PM)", "title": "string", "action": "string", "why": "string"},
    {"slot": "Evening (6:00 – 10:00 PM)", "title": "string", "action": "string", "why": "string"}
  ],
  "sustainable_alternatives": [
    {"title": "string", "action": "string", "impact": "-28% PM2.5"},
    {"title": "string", "action": "string", "impact": "-22% NO2"},
    {"title": "string", "action": "string", "impact": "-18% CO2"}
  ],
  "indoor_air_hacks": [
    {"title": "string", "action": "string", "benefit": "-35% Indoor PM2.5"},
    {"title": "string", "action": "string", "benefit": "Zero VOC Spike"},
    {"title": "string", "action": "string", "benefit": "Overnight Clean Zone"}
  ]
}
"""


def _build_cache_key(city: str, aqi: int, routine: str, home_setup: str) -> str:
    """Builds a deterministic SHA-256 cache key quantized by AQI bucket."""
    raw = f"{city.lower()}|{aqi // AQI_BUCKET_SIZE}|{routine.lower()}|{home_setup.lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _classify_aqi_severity(aqi: int) -> str:
    """Maps numeric US AQI to a human-readable severity category."""
    if aqi > 250:
        return "Very Poor"
    if aqi > 150:
        return "Unhealthy"
    if aqi > 50:
        return "Moderate"
    return "Good"


def _build_fallback_plan(city: str, aqi: int, routine: str, home_setup: str) -> dict:
    """Builds a deterministic, schema-validated fallback plan calibrated to local AQI."""
    severity = _classify_aqi_severity(aqi)
    bio_dose = max(8, round(aqi * BIO_DOSE_FACTOR))
    prevented = max(5, round(bio_dose * EXPOSURE_REDUCTION_RATIO))
    safest_window = "12:30 PM – 4:00 PM" if aqi > 100 else "7:00 AM – 6:00 PM"

    plan = AirQualityPlan(
        risk_summary=(
            f"{city} is at AQI {aqi} ({severity}). Tailoring ventilation timing and commute exposure "
            f"for your profile ({routine}; {home_setup}) cuts daily particulate inhalation by nearly half."
        ),
        inhaled_bio_dose_ug=bio_dose,
        safest_window=safest_window,
        exposure_prevented_ug=prevented,
        time_routines=[
            {
                "slot": "Morning (6:30 – 10:00 AM)",
                "title": "Keep road-facing windows sealed; shift workout indoors",
                "action": "Avoid rush-hour outdoor exertion near traffic corridors.",
                "why": "Morning thermal inversion traps vehicle & biomass PM2.5 near breathing height.",
            },
            {
                "slot": "Midday (1:00 – 4:00 PM)",
                "title": "Open cross-ventilation for 20 mins & batch outdoor errands",
                "action": "Flush stale indoor CO2 while daytime mixing disperses ground smog.",
                "why": "Solar heating lifts the inversion layer, dropping outdoor PM2.5 by up to 35%.",
            },
            {
                "slot": "Evening (6:00 – 10:00 PM)",
                "title": "Activate bedroom clean-air zone 1 hr before sleep",
                "action": "Close exterior vents and run filtration or wet-mopped damp circulation.",
                "why": "Evening traffic + cooling air spikes PM2.5; clean bedroom air aids overnight recovery.",
            },
        ],
        sustainable_alternatives=[
            {
                "title": "Shift Commute to Metro / EV Carpool",
                "action": f"Adapt your routine ({routine[:45]}) to shared transit 3+ days/week.",
                "impact": "-28% PM2.5 Dose",
            },
            {
                "title": "Run Kitchen Exhaust + Lid-On Cooking",
                "action": "Eliminates indoor NO2 spikes and ultrafine cooking aerosols.",
                "impact": "-22% Indoor NO2",
            },
            {
                "title": "Zero-Idling & Shaded Side-Street Routing",
                "action": "Cut engine at stops >20s and avoid congested arterial junctions.",
                "impact": "-19.2 kg CO2/wk",
            },
        ],
        indoor_air_hacks=[
            {
                "title": "Wet-Mop Floors Instead of Dry Sweeping",
                "action": "Traps settled PM10 road dust without resuspending particles into indoor air.",
                "benefit": "-35% Resuspended Dust",
            },
            {
                "title": "Damp Microfiber Door-Draft Stoppers",
                "action": f"Seal entry gaps in your setup ({home_setup[:40]}) during peak evening smog.",
                "benefit": "Blocks Smog Infiltration",
            },
            {
                "title": "Bio-Filtration Cluster (Snake Plant & Areca Palm)",
                "action": "Place high-transpiration indoor plants near bedroom and living room windows.",
                "benefit": "24/7 Passive VOC Capture",
            },
        ],
    )
    return plan.model_dump()


async def _query_gemini(user_prompt: str, api_key: str) -> dict | None:
    """Attempts async structured JSON generation across configured Gemini models."""
    ai_client = genai.Client(api_key=api_key)
    for model_name in GEMINI_MODELS:
        try:
            response = await ai_client.aio.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.35,
                ),
            )
            validated = AirQualityPlan.model_validate_json(response.text)
            return validated.model_dump()
        except (ValueError, KeyError, RuntimeError) as err:
            logger.warning("Gemini model %s unavailable: %s", model_name, err)
    return None


async def _query_groq(user_prompt: str, api_key: str, client: httpx.AsyncClient) -> dict | None:
    """Attempts async structured JSON generation via Groq fallback endpoint."""
    try:
        res = await client.post(
            GROQ_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AeroGuardAI/3.1",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.35,
            },
        )
        if res.status_code == 200:
            raw_content = res.json()["choices"][0]["message"]["content"]
            validated = AirQualityPlan.model_validate_json(raw_content)
            return validated.model_dump()
    except (httpx.HTTPError, ValueError, KeyError) as err:
        logger.warning("Groq fallback unavailable: %s", err)
    return None


async def generate_air_quality_plan(
    city: str,
    aqi: int,
    routine: str,
    home_setup: str,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Generates and caches a validated personalized air quality protection plan."""
    cache_key = _build_cache_key(city, aqi, routine, home_setup)
    cached_plan = _plan_cache.get(cache_key)
    if cached_plan is not None:
        return cached_plan

    user_prompt = (
        f"City: {city}\n"
        f"Current US AQI: {aqi}\n"
        f"Household & Commute Profile: {routine}\n"
        f"Indoor Setup: {home_setup}"
    )

    gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if gemini_key:
        gemini_plan = await _query_gemini(user_prompt, gemini_key)
        if gemini_plan is not None:
            _plan_cache.set(cache_key, gemini_plan)
            return gemini_plan

    groq_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if groq_key and client is not None:
        groq_plan = await _query_groq(user_prompt, groq_key, client)
        if groq_plan is not None:
            _plan_cache.set(cache_key, groq_plan)
            return groq_plan

    fallback = _build_fallback_plan(city, aqi, routine, home_setup)
    _plan_cache.set(cache_key, fallback)
    return fallback