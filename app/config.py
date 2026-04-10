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
ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
]
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_MAX_RETRIES = get_non_negative_int_env("ANTHROPIC_MAX_RETRIES", 2)
REQUEST_TIMEOUT_SECONDS = get_positive_float_env("REQUEST_TIMEOUT_SECONDS", 30.0)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "").rstrip("/")
DASHBOARD_ADMIN_KEY = os.getenv("DASHBOARD_ADMIN_KEY", "")
CONTACTS_SERVICE_URL = os.getenv("CONTACTS_SERVICE_URL", "").rstrip("/")
AUTH_JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
