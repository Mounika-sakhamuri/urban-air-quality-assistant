import os
import json
import httpx
from google import genai
from dotenv import load_dotenv

load_dotenv(override=True)

SYSTEM_PROMPT = """
You are an expert Urban Air Quality & Sustainability Assistant.
Given a user's city, current AQI level, daily commute/routine, and indoor home setup, provide:
1. "risk_summary": A concise 1-2 sentence health and air quality assessment tailored to the AQI severity.
2. "low_emission_routines": 3 specific, actionable daily routine adjustments to cut personal carbon/particulate emissions (include estimated CO2 or pollution impact).
3. "indoor_air_hacks": 3 practical, budget-friendly indoor air purification hacks tailored to their home setup.

Respond ONLY in valid JSON matching this exact schema:
{
  "risk_summary": "string",
  "low_emission_routines": [{"title": "string", "action": "string", "impact": "string"}],
  "indoor_air_hacks": [{"title": "string", "action": "string", "benefit": "string"}]
}
"""


def _smart_aqi_plan(city: str, aqi: int, routine: str, home_setup: str) -> dict:
    """Guaranteed AQI-calibrated fallback plan if external LLM endpoints are rate-limited."""
    level = "Unhealthy" if aqi > 150 else ("Moderate" if aqi > 50 else "Good")
    return {
        "risk_summary": f"In {city}, an AQI of {aqi} falls into the {level} category. Reducing peak-hour traffic exposure and controlling indoor combustion/dust sources will significantly lower daily PM2.5 inhalation.",
        "low_emission_routines": [
            {
                "title": "Off-Peak Commute & Shared Transit",
                "action": f"Shift your routine ({routine[:55]}) outside rush hour or switch 2–3 days/week to public transit or carpooling.",
                "impact": "-1.9 kg CO2 / day",
            },
            {
                "title": "Indoor Exercise Substitution",
                "action": "Replace evening outdoor jogging with indoor bodyweight/yoga workouts whenever local AQI exceeds 150.",
                "impact": "-65% PM2.5 lung intake",
            },
            {
                "title": "Zero-Idling & Eco-Routing",
                "action": "Switch off engine ignition at traffic signals longer than 20 seconds and prefer tree-lined side streets over main arterials.",
                "impact": "-15% tailpipe emissions",
            },
        ],
        "indoor_air_hacks": [
            {
                "title": "Timed Cross-Ventilation Window",
                "action": f"For your setup ({home_setup[:55]}), keep road-facing windows closed during peak traffic (8–11 AM, 6–9 PM) and ventilate between 1–4 PM.",
                "benefit": "Cuts indoor PM2.5 infiltration",
            },
            {
                "title": "Gas Stove Exhaust & Wet Mopping",
                "action": "Always run kitchen exhaust/chimney while cooking on gas and wet-mop floors daily instead of dry sweeping.",
                "benefit": "Traps NO2 & settled dust",
            },
            {
                "title": "Natural Bio-Filtration & Door Seals",
                "action": "Place Snake Plants or Areca Palms near windows/entryways and seal door gaps with damp cloth draft stoppers.",
                "benefit": "Zero-electricity air filtering",
            },
        ],
    }


def generate_air_quality_plan(city: str, aqi: int, routine: str, home_setup: str) -> dict:
    """Generates tailored low-emission routines and indoor air hacks using Gemini with Groq fallback."""
    load_dotenv(override=True)
    user_prompt = (
        f"City: {city}\n"
        f"Current AQI: {aqi}\n"
        f"Daily Routine/Commute: {routine}\n"
        f"Indoor Setup: {home_setup}"
    )

    # 1. Primary: Google Gemini
    gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if gemini_key:
        for model_name in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.8-flash"]:
            try:
                client = genai.Client(api_key=gemini_key)
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.4,
                    ),
                )
                return json.loads(response.text)
            except Exception:
                continue

    # 2. Secondary: Groq API
    groq_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if groq_key:
        try:
            res = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "UrbanAirAssistant/1.0",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.4,
                },
                timeout=20.0,
            )
            if res.status_code == 200:
                return json.loads(res.json()["choices"][0]["message"]["content"])
        except Exception:
            pass

    # 3. Guaranteed Offline-Safe Fallback
    return _smart_aqi_plan(city, aqi, routine, home_setup)