# AI Orchestrator Service Instructions (Detailed)

Use this file as the repository-specific implementation contract for AI-assisted changes.

## 1) Repository role

- This service converts high-level goals into actionable task lists.
- Stack: Python microservice (FastAPI/Uvicorn runtime from repo README).
- This is the only place where AI provider-specific logic should live.

## 2) Service boundaries

- Keep backend-service decoupled from provider APIs and keys.
- Keep frontend-service unaware of provider details.
- Expose stable, simple planning contract over HTTP.

## 3) API contract (must remain stable)

- GET /health
  - Response: { "status": "ok" }
- POST /plan
  - Request: { "goal": string }
  - Response: { "tasks": string[] }

Contract changes must be additive unless explicitly requested and coordinated across backend/frontend.

## 4) Environment and defaults

- APP_PORT default: 8081.
- OPENROUTER_API_KEY: required for provider calls.
- OPENROUTER_MODEL default: google/gemma-3-4b-it:free.
- OPENROUTER_BASE_URL default: https://openrouter.ai/api/v1.
- REQUEST_TIMEOUT_SECONDS default: 30.
- OPENROUTER_MAX_RETRIES default: 2.
- OPENROUTER_RETRY_BASE_DELAY_SECONDS default: 0.4.
- LOG_LEVEL default: INFO.

## 5) Integration compatibility requirements

- backend-service defaults to planner URL http://127.0.0.1:8081/plan.
- Preserve request/response field names and JSON shapes expected by backend.
- Use deterministic response formatting that backend can pass through safely.

## 6) Reliability and failure behavior

- Enforce request timeouts and return clear, bounded failures.
- Avoid leaking provider internals in user-facing error messages.
- Keep health endpoint lightweight and independent from provider uptime where possible.
- Ensure failure paths are test-covered for provider/network timeout cases.

## 7) Implementation guidance

- Isolate provider adapters from request/response transport logic.
- Keep prompt/planning internals configurable via env vars where practical.
- Prefer explicit schemas and strict validation over permissive parsing.
- Avoid introducing hidden state that causes non-repeatable outputs.

## 8) Quality gates before completion

Run and pass:
- pytest

If formatting/lint tools are present in repo config, run them as well before finalizing changes.

## 9) Documentation synchronization

When changing env vars, planner behavior, or API fields:
- update README.md,
- verify backend-service compatibility notes,
- include migration guidance when behavior changes materially.

## 10) Current code map (authoritative)

- Service entrypoint and routes: `app/main.py`
- Normalization/parsing helpers: `normalize_task`, `normalize_tasks`, `extract_json_payload`, `extract_tasks_from_content`
- Planner execution: `generate_plan`
- Current normalization tests: `tests/test_normalization.py`

## 11) Planner behavior constraints

- Keep request validation bounds (`goal` min/max length) unless all callers are coordinated.
- Maintain multi-shape extraction logic (fenced JSON, plain JSON, line fallback) for robustness.
- Preserve normalization of numbered/bulleted outputs before returning task arrays.
- Keep planner output non-empty guarantee; empty extraction should remain a failure.

## 12) Error handling constraints

- Missing provider key should continue returning `503` (configuration issue).
- Upstream/model response failures should remain `502` class errors.
- Keep error messages stable enough for backend and frontend user-message mapping.

## 13) Performance and reliability notes

- Respect `REQUEST_TIMEOUT_SECONDS` in all provider requests.
- Avoid adding synchronous network calls; keep async I/O path with `httpx.AsyncClient`.
- If retry logic is introduced, keep bounded retries and deterministic timeout ceilings.
- Keep retry behavior bounded and only for transient network/upstream status failures.
- Preserve structured log fields around planning duration/attempts for production troubleshooting.
