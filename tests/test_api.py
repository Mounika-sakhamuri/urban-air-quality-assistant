from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_generate_plan_validation():
    res = client.post("/api/generate-plan", json={"city": "", "aqi": -5, "routine": "", "home_setup": ""})
    assert res.status_code == 422


def test_generate_plan_success(monkeypatch):
    def mock_plan(city: str, aqi: int, routine: str, home_setup: str) -> dict:
        return {
            "risk_summary": f"Moderate air quality in {city} (AQI {aqi}).",
            "low_emission_routines": [{"title": "Eco Transit", "action": "Take bus", "impact": "-2 kg CO2"}],
            "indoor_air_hacks": [{"title": "Ventilation", "action": "Open windows midday", "benefit": "-30% PM2.5"}],
        }

    monkeypatch.setattr("app.main.generate_air_quality_plan", mock_plan)
    res = client.post(
        "/api/generate-plan",
        json={"city": "Guntur", "aqi": 120, "routine": "Bike commute", "home_setup": "2BHK flat"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["plan"]["low_emission_routines"]) == 1