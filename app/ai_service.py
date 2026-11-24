import hashlib
import json
import logging
import os
import httpx
from dotenv import load_dotenv
from google import genai

from app.cache import BoundedTTLCache

load_dotenv(override=True)
logger = logging.getLogger("aeroguard.ai")

_plan_cache = BoundedTTLCache(max_size=256, ttl_seconds=900)

SYSTEM_PROMPT = """
You are AeroGuard AI, an Urban Air Quality & Environmental Health Intelligence Engine.
Given a user's city, current US AQI, household profile, primary commute, and indoor setup, generate a structured daily protection & low-emission plan.

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
    raw = f"{city.lower()}|{aqi // 5}|{routine.lower()}|{home_setup.lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _smart_aqi_plan(city: str, aqi: int, routine: str, home_setup: str) -> dict:
    """Deterministic AQI-calibrated fallback plan with bio-dose and time-slotted routines."""
    level = "Very Poor" if aqi > 250 else ("Unhealthy" if aqi > 150 else ("Moderate" if aqi > 50 else "Good"))
    bio_dose = max(8, round(aqi * 0.14))
    prevented = max(5, round(bio_dose * 0.46))
    return {
        "risk_summary": (
            f"{city} is at AQI {aqi} ({level}). Tailoring ventilation timing and commute exposure "
            f"for your profile ({routine}; {home_setup}) cuts daily particulate inhalation by nearly half."
        ),
        "inhaled_bio_dose_ug": bio_dose,
        "safest_window": "12:30 PM – 4:00 PM" if aqi > 100 else "7:00 AM – 6:00 PM",
        "exposure_prevented_ug": prevented,
        "time_routines": [
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
        "sustainable_alternatives": [
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
        "indoor_air_hacks": [
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
    }


async def generate_air_quality_plan(
    city: str,
    aqi: int,
    routine: str,
    home_setup: str,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Generates structured air quality intelligence asynchronously with TTL caching."""
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
        ai_client = genai.Client(api_key=gemini_key)
        for model_name in ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.8-flash"):
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
                parsed = json.loads(response.text)
                _plan_cache.set(cache_key, parsed)
                return parsed
            except (ValueError, KeyError, RuntimeError) as err:
                logger.warning("Gemini model %s skipped: %s", model_name, err)

    groq_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if groq_key and client is not None:
        try:
            res = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "AeroGuardAI/3.0",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.35,
                },
            )
            if res.status_code == 200:
                parsed = json.loads(res.json()["choices"][0]["message"]["content"])
                _plan_cache.set(cache_key, parsed)
                return parsed
        except (httpx.HTTPError, ValueError, KeyError) as err:
            logger.warning("Groq fallback skipped: %s", err)

    fallback = _smart_aqi_plan(city, aqi, routine, home_setup)
    _plan_cache.set(cache_key, fallback)
    return fallback