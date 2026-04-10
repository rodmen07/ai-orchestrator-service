import json
import logging
import time
from collections.abc import AsyncGenerator

import google.generativeai as genai
from fastapi import HTTPException

from app.config import GEMINI_MODEL, GOOGLE_API_KEY
from app.consult_prompt import CONSULT_SYSTEM_PROMPT

logger = logging.getLogger("ai-orchestrator-service")


def _configured_model() -> genai.GenerativeModel:
    if not GOOGLE_API_KEY:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY not configured")
    genai.configure(api_key=GOOGLE_API_KEY)
    return genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=CONSULT_SYSTEM_PROMPT,
    )


def _to_gemini_history(messages: list[dict]) -> tuple[list[dict], str]:
    """
    Split messages into history (all but last user turn) and the final user prompt.
    Gemini uses 'user'/'model' roles (not 'assistant').
    """
    role_map = {"user": "user", "assistant": "model"}
    history = []
    for msg in messages[:-1]:
        history.append({"role": role_map.get(msg["role"], msg["role"]), "parts": [msg["content"]]})
    last_prompt = messages[-1]["content"] if messages else ""
    return history, last_prompt


async def generate_consult_gemini(messages: list[dict]) -> str:
    model = _configured_model()
    history, prompt = _to_gemini_history(messages)

    started_at = time.monotonic()

    try:
        chat = model.start_chat(history=history)
        response = await chat.send_message_async(prompt)
    except Exception as exc:
        logger.error("Gemini API error: %s", exc)
        raise HTTPException(status_code=502, detail="Gemini API error") from exc

    content = response.text or ""
    if not content.strip():
        raise HTTPException(status_code=502, detail="Empty response from Gemini")

    logger.info(
        "gemini consult generated model=%s duration_ms=%.2f turns=%d",
        GEMINI_MODEL,
        (time.monotonic() - started_at) * 1000,
        len([m for m in messages if m["role"] == "user"]),
    )

    return content


async def generate_consult_stream_gemini(messages: list[dict]) -> AsyncGenerator[str, None]:
    """
    Streaming version. Yields SSE-formatted chunks matching the Claude stream format:
      data: {"token": "..."}\n\n
      data: [DONE]\n\n
      data: {"error": "..."}\n\n
    """
    if not GOOGLE_API_KEY:
        yield f"data: {json.dumps({'error': 'GOOGLE_API_KEY not configured'})}\n\n"
        return

    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=CONSULT_SYSTEM_PROMPT,
    )
    history, prompt = _to_gemini_history(messages)

    started_at = time.monotonic()

    try:
        chat = model.start_chat(history=history)
        async for chunk in await chat.send_message_async(prompt, stream=True):
            text = chunk.text or ""
            if text:
                yield f"data: {json.dumps({'token': text})}\n\n"
    except Exception as exc:
        logger.error("Gemini streaming error: %s", exc)
        yield f"data: {json.dumps({'error': 'Gemini API error — try again'})}\n\n"
        return

    logger.info(
        "gemini consult streamed model=%s duration_ms=%.2f turns=%d",
        GEMINI_MODEL,
        (time.monotonic() - started_at) * 1000,
        len([m for m in messages if m["role"] == "user"]),
    )

    yield "data: [DONE]\n\n"
