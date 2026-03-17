import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator

import anthropic
import httpx
from fastapi import HTTPException

from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MAX_RETRIES,
    ANTHROPIC_MODEL,
    DASHBOARD_ADMIN_KEY,
    DASHBOARD_URL,
    REQUEST_TIMEOUT_SECONDS,
)
from app.classify import classify_prompt
from app.consult_prompt import CONSULT_SYSTEM_PROMPT
from app.normalization import extract_tasks_from_content
from app.openrouter_prompt import build_plan_prompt


logger = logging.getLogger("ai-orchestrator-service")


async def generate_plan(
    goal: str,
    existing_tasks: list[str] | None = None,
    context_tasks: list[str] | None = None,
    feedback: str = "",
    target_count: int = 16,
) -> list[str]:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY missing")

    system_prompt, user_message = build_plan_prompt(goal, target_count=target_count)

    client = anthropic.AsyncAnthropic(
        api_key=ANTHROPIC_API_KEY,
        max_retries=ANTHROPIC_MAX_RETRIES,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    started_at = time.monotonic()

    try:
        message = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.RateLimitError as error:
        raise HTTPException(status_code=429, detail="Claude API rate limit reached") from error
    except anthropic.APIStatusError as error:
        logger.error("Claude API error: status=%d body=%s", error.status_code, error.body)
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


async def _log_consult(prompt: str, response: str, model: str, input_tokens: int, output_tokens: int, duration_ms: float) -> None:
    if not DASHBOARD_URL or not DASHBOARD_ADMIN_KEY:
        return
    payload = {
        "id": str(uuid.uuid4()),
        "prompt": prompt,
        "response": response,
        "model": model,
        "topic": classify_prompt(prompt),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": round(duration_ms, 2),
        "logged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{DASHBOARD_URL}/ingest",
                json={"source": "ai-consult", "event_type": "consult", "payload": payload},
                headers={"X-Admin-Key": DASHBOARD_ADMIN_KEY},
            )
    except Exception as exc:
        logger.warning("Failed to log consult to dashboard: %s", exc)


async def generate_consult(messages: list[dict]) -> str:
    """
    Multi-turn consulting response. `messages` is a list of
    {"role": "user"|"assistant", "content": str} dicts in conversation order.
    """
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY missing")

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
            system=CONSULT_SYSTEM_PROMPT,
            messages=messages,
        )
    except anthropic.RateLimitError as error:
        raise HTTPException(status_code=429, detail="Claude API rate limit reached") from error
    except anthropic.APIStatusError as error:
        logger.error("Claude API error: status=%d body=%s", error.status_code, error.body)
        raise HTTPException(status_code=502, detail=f"Claude API error: {error.status_code}") from error
    except anthropic.APIConnectionError as error:
        raise HTTPException(status_code=502, detail="Failed to connect to Claude API") from error

    content = message.content[0].text if message.content else ""

    if not content.strip():
        raise HTTPException(status_code=502, detail="Empty response from LLM")

    duration_ms = (time.monotonic() - started_at) * 1000
    logger.info(
        "consult generated model=%s duration_ms=%.2f input_tokens=%s output_tokens=%s turns=%d",
        ANTHROPIC_MODEL,
        duration_ms,
        message.usage.input_tokens,
        message.usage.output_tokens,
        len([m for m in messages if m["role"] == "user"]),
    )

    # Log the last user prompt for the dashboard
    last_user_prompt = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    asyncio.create_task(_log_consult(
        prompt=last_user_prompt,
        response=content,
        model=ANTHROPIC_MODEL,
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
        duration_ms=duration_ms,
    ))

    return content


async def generate_consult_stream(messages: list[dict]) -> AsyncGenerator[str, None]:
    """
    Streaming version of generate_consult. Yields SSE-formatted chunks:
      data: {"token": "..."}\n\n   — one per streamed text delta
      data: [DONE]\n\n             — signals completion
      data: {"error": "..."}\n\n   — on failure
    """
    if not ANTHROPIC_API_KEY:
        yield f"data: {json.dumps({'error': 'ANTHROPIC_API_KEY missing'})}\n\n"
        return

    client = anthropic.AsyncAnthropic(
        api_key=ANTHROPIC_API_KEY,
        max_retries=0,  # no retries on streaming — surface errors immediately
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    started_at = time.monotonic()
    chunks: list[str] = []
    last_user_prompt = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )

    try:
        async with client.messages.stream(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=CONSULT_SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                chunks.append(text)
                yield f"data: {json.dumps({'token': text})}\n\n"

            final = await stream.get_final_message()

    except anthropic.RateLimitError:
        yield f"data: {json.dumps({'error': 'Rate limit reached — try again shortly'})}\n\n"
        return
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
        logger.error("Streaming API error: %s", exc)
        yield f"data: {json.dumps({'error': 'AI service error — try again'})}\n\n"
        return

    duration_ms = (time.monotonic() - started_at) * 1000
    full_response = "".join(chunks)

    logger.info(
        "consult streamed model=%s duration_ms=%.2f input_tokens=%s output_tokens=%s turns=%d",
        ANTHROPIC_MODEL,
        duration_ms,
        final.usage.input_tokens,
        final.usage.output_tokens,
        len([m for m in messages if m["role"] == "user"]),
    )

    asyncio.create_task(_log_consult(
        prompt=last_user_prompt,
        response=full_response,
        model=ANTHROPIC_MODEL,
        input_tokens=final.usage.input_tokens,
        output_tokens=final.usage.output_tokens,
        duration_ms=duration_ms,
    ))

    yield "data: [DONE]\n\n"
