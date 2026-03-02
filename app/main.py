import json
import os
import re
from typing import List

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=1000)


class PlanResponse(BaseModel):
    tasks: List[str]


class HealthResponse(BaseModel):
    status: str


APP_TITLE = "ai-orchestrator-service"
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-3-4b-it:free")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

app = FastAPI(title=APP_TITLE)


def normalize_task(task: str) -> str:
    return re.sub(r"^\s*(?:\d+[\).:-]\s*|[-*•]\s*)+", "", task).strip()


def normalize_tasks(tasks: List[str]) -> List[str]:
    return [clean for clean in (normalize_task(task) for task in tasks) if clean]


def extract_json_payload(content: str) -> str | None:
    trimmed = content.strip()

    if trimmed.startswith("```"):
        first_newline = trimmed.find("\n")
        if first_newline != -1:
            trimmed = trimmed[first_newline + 1 :]
        if trimmed.endswith("```"):
            trimmed = trimmed[:-3].strip()

    if trimmed.startswith("{") and trimmed.endswith("}"):
        return trimmed

    start = trimmed.find("{")
    end = trimmed.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    return trimmed[start : end + 1]


def extract_tasks_from_content(content: str) -> List[str]:
    content = content.strip()
    json_payload = extract_json_payload(content)

    if json_payload:
        try:
            payload = json.loads(json_payload)
            tasks = payload.get("tasks", [])
            if isinstance(tasks, list):
                return normalize_tasks([str(task) for task in tasks])
        except json.JSONDecodeError:
            pass

    try:
        payload = json.loads(content)
        tasks = payload.get("tasks", [])
        if isinstance(tasks, list):
            return normalize_tasks([str(task) for task in tasks])
    except json.JSONDecodeError:
        pass

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return normalize_tasks(lines)


async def generate_plan(goal: str) -> List[str]:
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY missing")

    prompt = (
        "You are a planning assistant. Return JSON only with shape "
        '{"tasks":["Task 1","Task 2"]}. '
        "Generate 4 to 8 actionable tasks for this goal: "
        f"{goal}"
    )

    body = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=body,
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Upstream LLM request failed")

    payload = response.json()
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(status_code=502, detail="Unexpected LLM response format")

    tasks = extract_tasks_from_content(content)
    if not tasks:
        raise HTTPException(status_code=502, detail="No tasks returned by LLM")

    return tasks


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/plan", response_model=PlanResponse)
async def plan(request: PlanRequest) -> PlanResponse:
    tasks = await generate_plan(request.goal)
    return PlanResponse(tasks=tasks)
