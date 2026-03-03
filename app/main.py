import asyncio
import json
import logging
import math
import os
import re
import time
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


def get_positive_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        parsed = float(raw_value)
    except ValueError:
        return default

    if not math.isfinite(parsed) or parsed <= 0:
        return default

    return parsed


def get_non_negative_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        parsed = int(raw_value)
    except ValueError:
        return default

    if parsed < 0:
        return default

    return parsed


REQUEST_TIMEOUT_SECONDS = get_positive_float_env("REQUEST_TIMEOUT_SECONDS", 30.0)
OPENROUTER_MAX_RETRIES = get_non_negative_int_env("OPENROUTER_MAX_RETRIES", 2)
OPENROUTER_RETRY_BASE_DELAY_SECONDS = get_positive_float_env(
    "OPENROUTER_RETRY_BASE_DELAY_SECONDS",
    0.4,
)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(APP_TITLE)

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


def should_retry_status(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES


async def post_chat_completion_with_retry(
    *,
    client: httpx.AsyncClient,
    endpoint: str,
    headers: dict[str, str],
    body: dict,
) -> tuple[httpx.Response, int]:
    attempts = OPENROUTER_MAX_RETRIES + 1
    last_network_error: httpx.RequestError | None = None

    for attempt_index in range(attempts):
        attempt_number = attempt_index + 1
        try:
            response = await client.post(endpoint, headers=headers, json=body)
        except httpx.RequestError as error:
            last_network_error = error

            if attempt_number >= attempts:
                break

            delay_seconds = OPENROUTER_RETRY_BASE_DELAY_SECONDS * attempt_number
            logger.warning(
                "openrouter network error attempt %s/%s (%s); retrying in %.2fs",
                attempt_number,
                attempts,
                error.__class__.__name__,
                delay_seconds,
            )
            await asyncio.sleep(delay_seconds)
            continue

        if response.status_code < 400:
            return response, attempt_number

        if should_retry_status(response.status_code) and attempt_number < attempts:
            delay_seconds = OPENROUTER_RETRY_BASE_DELAY_SECONDS * attempt_number
            logger.warning(
                "openrouter retryable status %s attempt %s/%s; retrying in %.2fs",
                response.status_code,
                attempt_number,
                attempts,
                delay_seconds,
            )
            await asyncio.sleep(delay_seconds)
            continue

        return response, attempt_number

    if last_network_error is not None:
        raise HTTPException(status_code=502, detail="Upstream LLM request failed")

    raise HTTPException(status_code=502, detail="Upstream LLM request failed")


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

    started_at = time.monotonic()
    endpoint = f"{OPENROUTER_BASE_URL}/chat/completions"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response, attempts_used = await post_chat_completion_with_retry(
            client=client,
            endpoint=endpoint,
            headers=headers,
            body=body,
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

    logger.info(
        "plan generated model=%s attempts=%s duration_ms=%.2f tasks=%s",
        OPENROUTER_MODEL,
        attempts_used,
        (time.monotonic() - started_at) * 1000,
        len(tasks),
    )

    return tasks


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/plan", response_model=PlanResponse)
async def plan(request: PlanRequest) -> PlanResponse:
    tasks = await generate_plan(request.goal)
    return PlanResponse(tasks=tasks)
