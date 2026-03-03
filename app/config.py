import os


def get_positive_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        parsed = float(raw_value)
    except ValueError:
        return default

    if parsed <= 0:
        return default

    return parsed


def get_non_negative_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        parsed = int(raw_value)
    except ValueError:
        return default

    if parsed < 0:
        return default

    return parsed


APP_TITLE = "ai-orchestrator-service"
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-3-4b-it:free")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
REQUEST_TIMEOUT_SECONDS = get_positive_float_env("REQUEST_TIMEOUT_SECONDS", 30.0)
OPENROUTER_MAX_RETRIES = get_non_negative_int_env("OPENROUTER_MAX_RETRIES", 2)
OPENROUTER_RETRY_BASE_DELAY_SECONDS = get_positive_float_env(
    "OPENROUTER_RETRY_BASE_DELAY_SECONDS",
    0.4,
)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
