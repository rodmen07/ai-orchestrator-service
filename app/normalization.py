import json
import re
from typing import List


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
