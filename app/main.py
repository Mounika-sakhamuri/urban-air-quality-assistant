from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app.ai_service import generate_air_quality_plan

app = FastAPI(title="Urban Air Quality Assistant", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")


class AirQualityRequest(BaseModel):
    city: str = Field(..., min_length=2, max_length=100)
    aqi: int = Field(..., ge=0, le=1000)
    routine: str = Field(..., min_length=3, max_length=300)
    home_setup: str = Field(..., min_length=3, max_length=300)


@app.get("/")
async def serve_home():
    return FileResponse("static/index.html")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/recommend")
async def get_recommendations(req: AirQualityRequest):
    try:
        return generate_air_quality_plan(
            city=req.city,
            aqi=req.aqi,
            routine=req.routine,
            home_setup=req.home_setup,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {str(e)}")