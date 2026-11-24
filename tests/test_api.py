from fastapi.testclient import TestClient
from app.cache import BoundedTTLCache
from app.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


def test_bounded_ttl_cache():
    cache = BoundedTTLCache(max_size=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1
    cache.set("c", 3)
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_generate_plan_validation():
    with TestClient(app) as client:
        res = client.post("/api/generate-plan", json={"city": "", "aqi": -5, "routine": "", "home_setup": ""})
        assert res.status_code == 422


def test_generate_plan_success(monkeypatch):
    async def mock_plan(city: str, aqi: int, routine: str, home_setup: str, client=None) -> dict:
        return {
            "risk_summary": f"Moderate air quality in {city} (AQI {aqi}).",
            "inhaled_bio_dose_ug": 16,
            "safest_window": "12:30 PM – 4:00 PM",
            "exposure_prevented_ug": 9,
            "time_routines": [
                {"slot": "Morning", "title": "Indoor stretch", "action": "Stay inside", "why": "Traffic smog"}
            ],
            "sustainable_alternatives": [{"title": "Metro", "action": "Use rail", "impact": "-28% PM2.5"}],
            "indoor_air_hacks": [{"title": "Wet mop", "action": "Avoid dry broom", "benefit": "-35% PM10"}],
        }

    monkeypatch.setattr("app.main.generate_air_quality_plan", mock_plan)
    with TestClient(app) as client:
        res = client.post(
            "/api/generate-plan",
            json={"city": "Guntur", "aqi": 120, "routine": "Bike commute", "home_setup": "2BHK flat"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["plan"]["inhaled_bio_dose_ug"] == 16