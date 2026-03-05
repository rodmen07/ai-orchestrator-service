from fastapi import HTTPException


def build_plan_prompt(
    goal: str,
    existing_tasks: list[str] | None = None,
    context_tasks: list[str] | None = None,
) -> str:
    base = (
        "You are a planning assistant. Return JSON only with shape "
        '{"tasks":["Task 1","Task 2"]}. '
        "Generate 4 to 8 actionable, specific tasks for this short-term goal. "
        "Do not suggest tasks that are already in progress or completed."
    )

    sections: list[str] = [base, f"\nGoal: {goal}"]

    if existing_tasks:
        listed = "\n".join(f"- {t}" for t in existing_tasks)
        sections.append(
            f"\nTasks already assigned to this goal (do not repeat or duplicate these):\n{listed}"
        )

    if context_tasks:
        listed = "\n".join(f"- {t}" for t in context_tasks[:10])
        sections.append(
            f"\nOther tasks currently in the system (use for broader context only):\n{listed}"
        )

    sections.append("\nReturn only the JSON object, no explanation.")
    return "".join(sections)


def extract_content_from_payload(payload: dict) -> str:
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise HTTPException(status_code=502, detail="Unexpected LLM response format") from error
