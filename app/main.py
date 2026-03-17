import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.agent import run_agent
from app.config import ALLOWED_ORIGINS, APP_TITLE, LOG_LEVEL
from app.guardrails import check_goal
from app.openrouter import generate_consult, generate_consult_stream, generate_plan
from app.schemas import AgentRequest, AgentResponse, ConsultRequest, ConsultResponse, ConversationMessage, HealthResponse, PlanRequest, PlanResponse

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(APP_TITLE)

app = FastAPI(title=APP_TITLE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/agent", response_model=AgentResponse)
async def agent(request: AgentRequest) -> AgentResponse:
    result = await run_agent(request.prompt, request.bearer_token)
    return AgentResponse(result=result)


@app.post("/consult", response_model=ConsultResponse)
async def consult(request: ConsultRequest) -> ConsultResponse:
    try:
        msgs = request.resolved_messages()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    response = await generate_consult([{"role": m.role, "content": m.content} for m in msgs])
    return ConsultResponse(response=response)


@app.post("/consult/stream")
async def consult_stream(request: ConsultRequest) -> StreamingResponse:
    try:
        msgs = request.resolved_messages()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return StreamingResponse(
        generate_consult_stream([{"role": m.role, "content": m.content} for m in msgs]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
