import asyncio
import logging
import time

import httpx
from fastapi import HTTPException

from app.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MAX_RETRIES,
    OPENROUTER_MODEL,
    OPENROUTER_RETRY_BASE_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
)
from app.normalization import extract_tasks_from_content

RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


logger = logging.getLogger("ai-orchestrator-service")


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


async def generate_plan(goal: str) -> list[str]:
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
