import logging
from fastapi import FastAPI, HTTPException

from app.agent import run_agent
from app.config import APP_TITLE, LOG_LEVEL
from app.guardrails import check_goal
from app.openrouter import generate_plan
from app.schemas import AgentRequest, AgentResponse, HealthResponse, PlanRequest, PlanResponse

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(APP_TITLE)

app = FastAPI(title=APP_TITLE)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/agent", response_model=AgentResponse)
async def agent(request: AgentRequest) -> AgentResponse:
    result = await run_agent(request.prompt, request.bearer_token)
    return AgentResponse(result=result)


@app.post("/plan", response_model=PlanResponse)
async def plan(request: PlanRequest) -> PlanResponse:
    error = check_goal(request.goal)
    if error:
        raise HTTPException(status_code=422, detail=error)

    tasks = await generate_plan(
        request.goal,
        existing_tasks=request.existing_tasks,
        context_tasks=request.context_tasks,
        feedback=request.feedback,
        target_count=request.target_count,
    )
    return PlanResponse(tasks=tasks)
