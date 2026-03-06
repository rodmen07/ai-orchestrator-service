import json
import logging
import os
import time

import httpx
import anthropic
from fastapi import HTTPException

from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MAX_RETRIES,
    ANTHROPIC_MODEL,
    REQUEST_TIMEOUT_SECONDS,
)

logger = logging.getLogger("ai-orchestrator-service")

TASK_API_URL = os.getenv("TASK_API_URL", "http://localhost:3000")
ACCOUNTS_SERVICE_URL = os.getenv("ACCOUNTS_SERVICE_URL", "http://localhost:3010")
CONTACTS_SERVICE_URL = os.getenv("CONTACTS_SERVICE_URL", "http://localhost:3011")

TOOLS = [
    {
        "name": "list_tasks",
        "description": "List tasks from the task API. Returns a JSON array of task objects with id, title, description, status, priority, created_at.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "done"],
                    "description": "Filter by task status. Omit to return all statuses.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of tasks to return. Default 20.",
                },
            },
        },
    },
    {
        "name": "create_task",
        "description": "Create a new task in the task API.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short, actionable task title (required).",
                },
                "description": {
                    "type": "string",
                    "description": "Optional detailed description of the task.",
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority 1-10. Higher is more urgent. Default 5.",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_accounts",
        "description": "List CRM accounts. Returns a JSON array of account objects with id, name, domain, status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "inactive", "churned"],
                    "description": "Filter by account status.",
                },
                "q": {
                    "type": "string",
                    "description": "Search query to filter by company name or domain.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of accounts to return.",
                },
            },
        },
    },
    {
        "name": "list_contacts",
        "description": "List CRM contacts. Returns a JSON array of contact objects with id, first_name, last_name, email, phone, lifecycle_stage, account_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lifecycle_stage": {
                    "type": "string",
                    "enum": ["lead", "prospect", "customer", "churned", "evangelist"],
                    "description": "Filter by lifecycle stage.",
                },
                "q": {
                    "type": "string",
                    "description": "Search query to filter by name or email.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of contacts to return.",
                },
            },
        },
    },
]


async def _execute_tool(name: str, tool_input: dict, bearer_token: str) -> str:
    headers = {"Authorization": f"Bearer {bearer_token}"}
    async with httpx.AsyncClient(timeout=10.0) as http:
        try:
            if name == "list_tasks":
                params = {k: v for k, v in tool_input.items() if k in ("status", "limit")}
                resp = await http.get(f"{TASK_API_URL}/api/v1/tasks", params=params, headers=headers)
                resp.raise_for_status()
                return resp.text

            elif name == "create_task":
                body: dict = {"title": tool_input["title"]}
                if "description" in tool_input:
                    body["description"] = tool_input["description"]
                if "priority" in tool_input:
                    body["priority"] = tool_input["priority"]
                resp = await http.post(f"{TASK_API_URL}/api/v1/tasks", json=body, headers=headers)
                resp.raise_for_status()
                return resp.text

            elif name == "list_accounts":
                params = {k: v for k, v in tool_input.items() if k in ("status", "q", "limit")}
                resp = await http.get(f"{ACCOUNTS_SERVICE_URL}/api/v1/accounts", params=params, headers=headers)
                resp.raise_for_status()
                return resp.text

            elif name == "list_contacts":
                params = {k: v for k, v in tool_input.items() if k in ("lifecycle_stage", "q", "limit")}
                resp = await http.get(f"{CONTACTS_SERVICE_URL}/api/v1/contacts", params=params, headers=headers)
                resp.raise_for_status()
                return resp.text

            else:
                return json.dumps({"error": f"Unknown tool: {name}"})

        except httpx.HTTPStatusError as e:
            return json.dumps({"error": f"HTTP {e.response.status_code}", "detail": e.response.text[:300]})
        except httpx.RequestError as e:
            return json.dumps({"error": f"Request failed: {str(e)}"})


async def run_agent(prompt: str, bearer_token: str) -> str:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY missing")

    client = anthropic.AsyncAnthropic(
        api_key=ANTHROPIC_API_KEY,
        max_retries=ANTHROPIC_MAX_RETRIES,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    messages: list = [{"role": "user", "content": prompt}]
    started_at = time.monotonic()
    total_input_tokens = 0
    total_output_tokens = 0

    for iteration in range(10):
        try:
            response = await client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=4096,
                tools=TOOLS,
                messages=messages,
            )
        except anthropic.RateLimitError as e:
            raise HTTPException(status_code=429, detail="Claude API rate limit reached") from e
        except anthropic.APIStatusError as e:
            logger.error("Claude API error: status=%d body=%s", e.status_code, e.body)
            raise HTTPException(status_code=502, detail=f"Claude API error: {e.status_code}") from e
        except anthropic.APIConnectionError as e:
            raise HTTPException(status_code=502, detail="Failed to connect to Claude API") from e

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        if response.stop_reason == "end_turn":
            final_text = next((b.text for b in response.content if b.type == "text"), "Done.")
            logger.info(
                "agent completed model=%s iterations=%d duration_ms=%.2f input_tokens=%d output_tokens=%d",
                ANTHROPIC_MODEL,
                iteration + 1,
                (time.monotonic() - started_at) * 1000,
                total_input_tokens,
                total_output_tokens,
            )
            return final_text

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            return next((b.text for b in response.content if b.type == "text"), "Done.")

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in tool_use_blocks:
            logger.info("tool_call tool=%s input=%s", block.name, json.dumps(block.input)[:200])
            result = await _execute_tool(block.name, block.input, bearer_token)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    raise HTTPException(status_code=502, detail="Agent exceeded maximum iterations")
