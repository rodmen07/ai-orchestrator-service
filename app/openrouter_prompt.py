from fastapi import HTTPException


def build_plan_prompt(goal: str) -> str:
    return (
        "You are a planning assistant. Return JSON only with shape "
        '{"tasks":["Task 1","Task 2"]}. '
        "Generate 4 to 8 actionable tasks for this goal: "
        f"{goal}"
    )


def extract_content_from_payload(payload: dict) -> str:
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise HTTPException(status_code=502, detail="Unexpected LLM response format") from error
