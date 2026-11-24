# Urban Air Quality Assistant

## 1. Chosen Vertical
**Challenge 6: Urban Air Quality Assistant** — An AI-powered sustainability and health assistant designed to help urban residents lower their personal carbon/particulate footprint and improve indoor air quality.

## 2. Approach and Logic
- **Context-Aware Decision Making:** Users provide their city, current Air Quality Index (AQI), daily commute/lifestyle routine, and indoor home setup.
- **Severity-Driven Personalization:** The system evaluates AQI severity alongside user constraints to recommend three targeted low-emission routine shifts (with estimated CO2/emission savings) and three budget-friendly indoor air purification hacks.
- **Structured AI Output:** Uses Google Gemini (`gemini-2.5-flash`) with strict JSON schema enforcement and low temperature (`0.4`) for reliable, deterministic, and actionable responses.

## 3. How the Solution Works
1. **Frontend (`static/index.html`):** A responsive, accessible web interface using semantic HTML (`<main>`, `<label>`, `aria-live`) where users input their local air context.
2. **Backend (`app/main.py`):** A FastAPI server that validates input bounds (`Pydantic`) and routes requests safely.
3. **AI Service (`app/ai_service.py`):** Connects securely to the Gemini API via environment variables (`GEMINI_API_KEY`) and returns structured recommendations.
4. **Testing (`tests/test_api.py`):** Automated `pytest` suite validating health checks and recommendation endpoints.

### Local Setup
```bash
pip install -r requirements.txt
# Add GEMINI_API_KEY=your_key to .env
uvicorn app.main:app --reload