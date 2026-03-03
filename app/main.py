import logging
from fastapi import FastAPI

from app.config import APP_TITLE, LOG_LEVEL
from app.openrouter import generate_plan
from app.schemas import HealthResponse, PlanRequest, PlanResponse

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(APP_TITLE)

app = FastAPI(title=APP_TITLE)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/plan", response_model=PlanResponse)
async def plan(request: PlanRequest) -> PlanResponse:
    tasks = await generate_plan(request.goal)
    return PlanResponse(tasks=tasks)
