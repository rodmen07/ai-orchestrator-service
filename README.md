# AI Orchestrator Service

Python microservice for goal-to-task planning that can be called by the Rust `backend-service`.

## Why this service

- Isolates AI provider logic from core task CRUD APIs
- Gives independent scaling and provider fallback in one place
- Keeps backend-service focused on business/domain rules

## API

- `GET /health` → `{ "status": "ok" }`
- `POST /plan`
  - Request: `{ "goal": "Ship MVP in 6 weeks" }`
  - Response: `{ "tasks": ["Define scope", "Build API", "..." ] }`

## Run locally

```bash
cd /home/rodmendoza07/Projects/ai-orchestrator-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload --port 8081
```

## Test

```bash
pytest
```

## Rust backend integration (recommended)

In `backend-service`, replace direct LLM calls with an internal HTTP call:

- URL: `http://localhost:8081/plan` (local)
- Body: `{ "goal": "..." }`
- Response passthrough: `{ "tasks": [...] }`

This keeps one canonical planner implementation while frontend and backend APIs remain stable.

## Environment

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (default: `google/gemma-3-4b-it:free`)
- `OPENROUTER_BASE_URL` (default: `https://openrouter.ai/api/v1`)
- `REQUEST_TIMEOUT_SECONDS` (default: `30`)
- `APP_PORT` (default: `8081`)

## Deploy (Fly.io)

This service includes `fly.toml`, `Dockerfile`, and `.dockerignore`.

```bash
cd /home/rodmendoza07/Projects/ai-orchestrator-service
fly launch --no-deploy
fly secrets set OPENROUTER_API_KEY=your_key_here
fly deploy
```

After deployment, set backend env:

```bash
cd /home/rodmendoza07/Projects/backend-service
fly secrets set AI_ORCHESTRATOR_PLAN_URL=https://ai-orchestrator-service-rodmen07.fly.dev/plan
fly deploy
```

## Working context from current code

### Request/response validation

- `PlanRequest.goal` is validated with Pydantic (`min_length=3`, `max_length=1000`).
- `POST /plan` returns `PlanResponse` with `tasks: List[str]`.
- `GET /health` returns `{"status":"ok"}` via typed response model.

### LLM integration behavior

- Service calls OpenRouter `POST /chat/completions` using `httpx.AsyncClient`.
- Prompt requires JSON output shape: `{"tasks":["Task 1", "Task 2"]}`.
- Default generation config currently uses `temperature: 0.2`.

### Output parsing and normalization

- Parser accepts multiple output formats from upstream model:
  - raw JSON,
  - JSON wrapped in fenced code blocks,
  - plain line-by-line fallback.
- Task normalization removes leading numbering/bullets and trims whitespace.
- Empty tasks are filtered out before returning response.

### Failure semantics

- Missing `OPENROUTER_API_KEY` returns HTTP `503`.
- Upstream HTTP failures or malformed payloads return HTTP `502`.
- If no actionable tasks are extracted, service returns HTTP `502` with clear detail.

### Contributor notes

- Current test coverage includes normalization behavior (`tests/test_normalization.py`).
- If parsing or normalization logic changes, extend tests in that file first.
