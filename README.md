# AI Orchestrator Service

A production-ready Python microservice that translates natural language goals into
structured task plans using LLMs — designed to be called as an internal service
from any backend.

**Live demo:** `https://ai-orchestrator-service-rodmen07.fly.dev/health`

```bash
curl -X POST https://ai-orchestrator-service-rodmen07.fly.dev/plan \
  -H "Content-Type: application/json" \
  -d '{"goal": "Ship an MVP in 6 weeks"}'

# → { "tasks": ["Define scope and success criteria", "Build core API", "..."] }
```

---

## Architecture

```
┌─────────────────┐     HTTP      ┌──────────────────────┐     HTTPS    ┌──────────────┐
│  backend-service │ ──────────── │  ai-orchestrator-service │ ─────────── │  OpenRouter  │
│    (Rust)        │  /plan       │      (Python/FastAPI)    │  /chat/     │  LLM API     │
└─────────────────┘              └──────────────────────┘  completions  └──────────────┘
```

**Why a separate service?**

Isolating LLM logic into its own microservice is a deliberate architectural
decision, not an accident of project structure:

- **Independent scaling** — LLM calls are slow and expensive; this service can
  scale independently from your core API
- **Provider portability** — swap models or providers by changing one env var,
  with zero changes to downstream services
- **Failure isolation** — LLM timeouts and upstream errors don't cascade into
  your core domain logic
- **Single implementation** — one canonical planner, consumed by any service
  that needs it

---

## Engineering Highlights

### Resilient LLM Integration
- Bounded retry with exponential backoff on transient upstream failures (`429`, `5xx`)
- Configurable timeout, retry count, and base delay via environment variables
- Explicit `503` on missing API key — fails fast at startup, not mid-request

### Robust Output Parsing
LLMs don't always return clean JSON. The parser handles:
- Raw JSON objects
- JSON wrapped in fenced code blocks
- Plain line-by-line text as a fallback

Task normalization strips leading bullets, numbering, and whitespace.
Empty tasks are filtered before response.

### Observability
Every plan generation logs: attempt count, model used, response duration,
and task count. `LOG_LEVEL` is configurable for production vs. debug verbosity.

### Validated I/O
Input and output shapes are enforced with Pydantic:
- `goal` field: `min_length=3`, `max_length=1000`
- Response always returns `{ "tasks": List[str] }`

---

## API

| Method | Endpoint  | Description                          |
|--------|-----------|--------------------------------------|
| GET    | `/health` | Health check → `{ "status": "ok" }` |
| POST   | `/plan`   | Generate tasks from a goal           |

**POST /plan**

Request:
```json
{ "goal": "Build a customer onboarding flow" }
```

Response:
```json
{
  "tasks": [
    "Map the current onboarding steps",
    "Identify drop-off points in the funnel",
    "Design the new flow wireframes",
    "..."
  ]
}
```

Error responses:
| Status | Cause                                      |
|--------|--------------------------------------------|
| 422    | Invalid request (goal too short/long)      |
| 502    | Upstream LLM failure or unparseable output |
| 503    | Missing `OPENROUTER_API_KEY`               |

---

## Running Locally

```bash
git clone https://github.com/rodmen07/ai-orchestrator-service
cd ai-orchestrator-service

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Add your OPENROUTER_API_KEY to .env

uvicorn app.main:app --reload --port 8081
```

Test it:
```bash
curl -X POST http://localhost:8081/plan \
  -H "Content-Type: application/json" \
  -d '{"goal": "Launch a new product feature"}'
```

Run tests:
```bash
pytest
```

---

## Deploying to Fly.io

```bash
fly launch --no-deploy
fly secrets set OPENROUTER_API_KEY=your_key_here
fly deploy
```

To wire up a downstream backend service:
```bash
fly secrets set AI_ORCHESTRATOR_PLAN_URL=https://ai-orchestrator-service-<your-app>.fly.dev/plan
```

---

## Configuration

| Variable                            | Default                          | Description                        |
|-------------------------------------|----------------------------------|------------------------------------|
| `OPENROUTER_API_KEY`                | —                                | Required. Your OpenRouter API key. |
| `OPENROUTER_MODEL`                  | `google/gemma-3-4b-it:free`      | Model to use for planning.         |
| `OPENROUTER_BASE_URL`               | `https://openrouter.ai/api/v1`   | Override for self-hosted models.   |
| `REQUEST_TIMEOUT_SECONDS`           | `30`                             | Per-request LLM timeout.           |
| `OPENROUTER_MAX_RETRIES`            | `2`                              | Max retry attempts on failure.     |
| `OPENROUTER_RETRY_BASE_DELAY_SECONDS` | `0.4`                          | Base delay for exponential backoff.|
| `LOG_LEVEL`                         | `INFO`                           | Logging verbosity.                 |
| `APP_PORT`                          | `8081`                           | Port the service binds to.         |

---

## Integrating with Your Backend

Replace direct LLM calls in your service with a single HTTP call:

```python
# Python example
import httpx

async def get_tasks(goal: str) -> list[str]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8081/plan",
            json={"goal": goal},
            timeout=35.0
        )
        response.raise_for_status()
        return response.json()["tasks"]
```

```rust
// Rust example (reqwest)
let response = client
    .post(&plan_url)
    .json(&serde_json::json!({ "goal": goal }))
    .send()
    .await?;
let plan: PlanResponse = response.json().await?;
```

---

## Stack

- **Runtime:** Python 3.11+
- **Framework:** FastAPI + Uvicorn
- **HTTP client:** httpx (async)
- **Validation:** Pydantic v2
- **LLM provider:** OpenRouter (model-agnostic)
- **Containerization:** Docker
- **Deployment:** Fly.io
- **CI/CD:** GitHub Actions

---

## Contributing

If parsing or normalization logic changes, extend `tests/test_normalization.py` first.
PRs welcome.
