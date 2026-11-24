from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)


def test_health_check():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}


@patch("app.main.generate_air_quality_plan")
def test_recommend_endpoint(mock_plan):
    mock_plan.return_value = {
        "risk_summary": "Moderate to poor air quality.",
        "low_emission_routines": [{"title": "Metro Shift", "action": "Take metro", "impact": "-2.1 kg CO2"}],
        "indoor_air_hacks": [{"title": "Cross Ventilation", "action": "Open windows at 2 PM", "benefit": "Reduces PM2.5"}]
    }
    res = client.post("/api/recommend", json={
        "city": "Hyderabad",
        "aqi": 140,
        "routine": "10km car commute",
        "home_setup": "1BHK apartment"
    })
    assert res.status_code == 200
    assert "low_emission_routines" in res.json()