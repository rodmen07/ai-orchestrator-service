import logging
import time

import httpx
from fastapi import HTTPException

from app.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    REQUEST_TIMEOUT_SECONDS,
)
from app.normalization import extract_tasks_from_content
from app.openrouter_prompt import build_plan_prompt, extract_content_from_payload
from app.openrouter_retry import post_chat_completion_with_retry


logger = logging.getLogger("ai-orchestrator-service")


async def generate_plan(
    goal: str,
    existing_tasks: list[str] | None = None,
    context_tasks: list[str] | None = None,
) -> list[str]:
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY missing")

    prompt = build_plan_prompt(goal, existing_tasks=existing_tasks, context_tasks=context_tasks)

    body: dict[str, object] = {
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
    content = extract_content_from_payload(payload)

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
