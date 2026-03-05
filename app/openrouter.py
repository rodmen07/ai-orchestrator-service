import logging
import time

import anthropic
from fastapi import HTTPException

from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MAX_RETRIES,
    ANTHROPIC_MODEL,
    REQUEST_TIMEOUT_SECONDS,
)
from app.normalization import extract_tasks_from_content
from app.openrouter_prompt import build_plan_prompt


logger = logging.getLogger("ai-orchestrator-service")


async def generate_plan(
    goal: str,
    existing_tasks: list[str] | None = None,
    context_tasks: list[str] | None = None,
    feedback: str = "",
    target_count: int = 7,
) -> list[str]:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY missing")

    prompt = build_plan_prompt(
        goal,
        existing_tasks=existing_tasks,
        context_tasks=context_tasks,
        feedback=feedback,
        target_count=target_count,
    )

    client = anthropic.AsyncAnthropic(
        api_key=ANTHROPIC_API_KEY,
        max_retries=ANTHROPIC_MAX_RETRIES,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    started_at = time.monotonic()

    try:
        message = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.RateLimitError as error:
        raise HTTPException(status_code=429, detail="Claude API rate limit reached") from error
    except anthropic.APIStatusError as error:
        raise HTTPException(status_code=502, detail=f"Claude API error: {error.status_code}") from error
    except anthropic.APIConnectionError as error:
        raise HTTPException(status_code=502, detail="Failed to connect to Claude API") from error

    content = message.content[0].text if message.content else ""
    tasks = extract_tasks_from_content(content)

    if not tasks:
        raise HTTPException(status_code=502, detail="No tasks returned by LLM")

    logger.info(
        "plan generated model=%s duration_ms=%.2f tasks=%s input_tokens=%s output_tokens=%s",
        ANTHROPIC_MODEL,
        (time.monotonic() - started_at) * 1000,
        len(tasks),
        message.usage.input_tokens,
        message.usage.output_tokens,
    )

    return tasks
