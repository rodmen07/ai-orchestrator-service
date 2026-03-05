import asyncio
import logging

import httpx
from fastapi import HTTPException

from app.config import OPENROUTER_MAX_RETRIES, OPENROUTER_RETRY_BASE_DELAY_SECONDS

RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}

logger = logging.getLogger("ai-orchestrator-service")


def should_retry_status(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES


async def post_chat_completion_with_retry(
    *,
    client: httpx.AsyncClient,
    endpoint: str,
    headers: dict[str, str],
    body: dict[str, object],
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
