"""
Lead capture: saves a visitor's name and email to contacts-service as a CRM lead.
The orchestrator acts as a BFF — it holds the service-to-service JWT logic so the
frontend never needs credentials.

Fail-open: if CONTACTS_SERVICE_URL or AUTH_JWT_SECRET are not configured (e.g. local
dev), the call is skipped and the endpoint still returns success. This keeps the
portfolio site functional without requiring the full backend to be running.
"""

import logging
import time

import httpx
import jwt

from app.config import AUTH_JWT_SECRET, CONTACTS_SERVICE_URL

logger = logging.getLogger("ai-orchestrator-service")


def _make_service_token() -> str:
    """Short-lived HS256 JWT for service-to-service calls."""
    now = int(time.time())
    return jwt.encode(
        {"sub": "ai-orchestrator", "iss": "auth-service", "iat": now, "exp": now + 300},
        AUTH_JWT_SECRET,
        algorithm="HS256",
    )


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(None, 1)
    return parts[0], parts[1] if len(parts) > 1 else "."


async def save_lead(name: str, email: str) -> bool:
    """
    POST to contacts-service. Returns True on success, False on any failure.
    Never raises — callers should treat failure as non-critical.
    """
    if not CONTACTS_SERVICE_URL or not AUTH_JWT_SECRET:
        logger.info("Lead capture skipped: CONTACTS_SERVICE_URL or AUTH_JWT_SECRET not configured")
        return True  # fail-open

    first_name, last_name = _split_name(name)
    token = _make_service_token()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{CONTACTS_SERVICE_URL}/api/v1/contacts",
                json={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "lifecycle_stage": "lead",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code in (200, 201):
                logger.info("Lead saved: email=%s", email)
                return True
            logger.warning("Lead save failed: status=%d body=%s", r.status_code, r.text[:200])
            return False
    except Exception as exc:
        logger.warning("Lead save error: %s", exc)
        return False
