"""Prompt guardrails for the AI orchestrator.

Validates goal strings before they reach the LLM to prevent prompt injection
and other forms of adversarial input.
"""

from __future__ import annotations

import re

# Patterns indicative of prompt-injection attempts.
# Checked case-insensitively against the goal string.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(previous|prior|above|all)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(previous|prior|above|all)\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all|previous|prior)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+prompt\b", re.IGNORECASE),
    re.compile(r"\bpretend\s+(you\s+are|to\s+be)\b", re.IGNORECASE),
    re.compile(r"\broleplay\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"\bbypass\s+(safety|filter|restriction|guideline)", re.IGNORECASE),
    re.compile(r"\boverride\s+(your|the)\s+(instruction|directive|rule)", re.IGNORECASE),
    re.compile(r"<\s*(system|user|assistant)\s*>", re.IGNORECASE),
    re.compile(r"\[INST\]|\[/INST\]", re.IGNORECASE),
]


def check_goal(goal: str) -> str | None:
    """Return an error message if *goal* fails guardrail checks, else ``None``.

    Callers should reject the request with HTTP 422 when a non-None value is
    returned and use the returned string as the error detail.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(goal):
            return "goal contains disallowed content"
    return None
