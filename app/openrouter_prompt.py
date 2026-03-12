from fastapi import HTTPException


SYSTEM_PROMPT = (
    "You are a senior cloud architect advisor. When given a cloud-related project idea, "
    "generate a concrete, ordered roadmap of exactly {target_count} milestones covering "
    "the end-to-end journey from initial setup to production.\n\n"
    "Rules:\n"
    "- Each item is one specific, actionable milestone (not a topic or category)\n"
    "- Cover the full arc: infrastructure, networking, security, application, CI/CD, observability, and cost\n"
    "- Reference real cloud services and patterns (e.g. \"Configure VPC with public/private subnets and NAT gateway\")\n"
    "- Order items logically — dependencies before dependents\n"
    "- No markdown formatting, no bullet prefixes, no numbering in the text itself\n"
    '- Return ONLY valid JSON: {"tasks": ["milestone 1", "milestone 2", ...]}'
)


def build_plan_prompt(goal: str, target_count: int = 16) -> tuple[str, str]:
    """Returns (system_prompt, user_message) for the cloud roadmap request."""
    system = SYSTEM_PROMPT.replace("{target_count}", str(target_count))
    user = f"Cloud project idea: {goal}"
    return system, user


def extract_content_from_payload(payload: dict[str, object]) -> str:
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise HTTPException(status_code=502, detail="Unexpected LLM response format") from error
