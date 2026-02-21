# 24_api.md — REST API & External Integration

## §24.0 Transport Conventions

```python
BASE_URL: str = "https://api.drs.example.com"
API_VERSION: str = "v1"
PREFIX: str = f"{BASE_URL}/{API_VERSION}"

ContentType = Literal["application/json", "text/event-stream", "multipart/form-data"]
AuthScheme = Literal["X-DRS-Key", "Bearer"]
```

All requests: `Content-Type: application/json` unless noted. All responses: `Content-Type: application/json` unless noted. Timestamps: ISO 8601 UTC.

---

## §24.1 Authentication & Rate Limiting

### Auth Headers

| Scheme | Header | Use case |
|--------|--------|----------|
| `X-DRS-Key` | `X-DRS-Key: sk-drs-{uid_prefix}-{48_chars}` | Machine-to-machine |
| `Bearer` | `Authorization: Bearer {jwt}` | User sessions (24h TTL, 7d refresh) |

Both schemes accepted on all endpoints. Missing/invalid auth → `401`.

### Rate Limits (per API key)

| Scope | Limit | Window | Response |
|-------|-------|--------|----------|
| Global requests | 60 | 1 min | `429` + `Retry-After: N` |
| Unauthenticated (per IP) | 10 | 1 min | `429` |
| New runs per user | 5 | 1 hour | `429` + body below |
| Daily budget | configured | 24 hours | `402` |

```python
# 429 body
class RateLimitError(TypedDict):
    error: Literal["rate_limit_exceeded"]
    retry_after_seconds: int
    limit: int
    window_seconds: int
```

---

## §24.2 Core Run Endpoints

### POST /v1/runs

Start a new document run (async).

**Request**

```python
class RunCreateRequest(TypedDict):
    # Required
    topic: str                          # 10–2000 chars
    target_words: int                   # 1000–50000
    max_budget_usd: float               # > 0.0
    style_profile: Literal[
        "scientific_report", "business_report", "technical_documentation",
        "journalistic", "narrative_essay", "ai_instructions", "blog",
        "software_spec", "functional_spec", "technical_spec"
    ]

    # Optional
    quality_preset: Literal["economy", "balanced", "premium"]  # default: "balanced"
    language: str                        # BCP-47, default: "en"
    output_formats: list[Literal["docx", "pdf", "markdown", "latex", "json"]]
    custom_outline: list[dict]           # OutlineSection dicts; skips Planner if provided
    uploaded_source_ids: list[str]       # UUIDs from POST /v1/sources
    style_preset_id: str | None          # UUID of saved style preset
    custom_rules: dict | None            # extra L1/L2/L3 overrides; see §26
    privacy_mode: Literal["standard", "enhanced", "strict", "self_hosted"]
    notify_webhook: str | None           # HTTPS URL
    notify_email: str | None
    pipeline_context: dict | None        # for DRS chain; see §31
```

**Response 202**

```python
class RunCreateResponse(TypedDict):
    run_id: str                          # UUID
    status: Literal["initializing"]
    status_url: str                      # GET /v1/runs/{run_id}
    stream_url: str                      # GET /v1/runs/{run_id}/stream
    companion_url: str                   # POST /v1/runs/{run_id}/companion
    estimated_duration_minutes: float
    estimated_cost_usd: float
    created_at: str                      # ISO 8601
```

**HTTP codes**

| Code | Meaning |
|------|---------|
| 202 | Run accepted, processing async |
| 400 | Invalid request body (Pydantic error) |
| 401 | Missing/invalid auth |
| 402 | Daily budget exhausted |
| 422 | topic/target_words/budget out of range |
| 429 | Rate limit exceeded |

**curl**

```bash
curl -X POST https://api.drs.example.com/v1/runs \
  -H "X-DRS-Key: sk-drs-abc123-..." \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "AI Ethics in Healthcare",
    "target_words": 10000,
    "max_budget_usd": 50.0,
    "style_profile": "scientific_report",
    "quality_preset": "balanced",
    "output_formats": ["docx", "pdf"]
  }'
```

---

### GET /v1/runs/{run_id}

Poll run status.

**Response 200**

```python
RunStatus = Literal[
    "initializing", "running", "paused",
    "awaiting_approval", "completed", "failed", "cancelled"
]

class RunProgress(TypedDict):
    sections_completed: int
    total_sections: int
    current_section_title: str | None
    current_iteration: int
    current_phase: Literal[
        "preflight", "budget_estimation", "planning", "outline_approval",
        "researching", "writing", "jury", "reflecting", "panel_discussion",
        "post_qa", "publishing"
    ]

class RunStatusResponse(TypedDict):
    run_id: str
    status: RunStatus
    phase: str
    progress: RunProgress
    cost_accumulated_usd: float
    elapsed_minutes: float
    estimated_remaining_minutes: float | None
    escalation_pending: bool
    escalation_type: str | None          # "outline_approval" | "oscillation" | "coherence_conflict"
    document_id: str | None              # set when status == "completed"
    error_message: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
```

**HTTP codes**

| Code | Meaning |
|------|---------|
| 200 | Status returned |
| 401 | Auth failed |
| 403 | run_id belongs to different user |
| 404 | run_id not found |

**curl**

```bash
curl https://api.drs.example.com/v1/runs/run-uuid-here \
  -H "X-DRS-Key: sk-drs-abc123-..."
```

---

### DELETE /v1/runs/{run_id}

Cancel a running or paused run.

**Query params**

```python
purge: bool  # default False; if True, deletes approved sections too
```

**Response 200**

```python
class RunCancelResponse(TypedDict):
    run_id: str
    status: Literal["cancelled"]
    sections_preserved: int   # 0 if purge=True
    cost_final_usd: float
```

**HTTP codes**

| Code | Meaning |
|------|---------|
| 200 | Cancelled |
| 400 | Run already completed/failed |
| 403 | Not owner |
| 404 | Not found |

---

## §24.3 Streaming (SSE)

### GET /v1/runs/{run_id}/stream

Real-time event stream. Client connects immediately after `POST /v1/runs`.

**Headers required**

```
Accept: text/event-stream
Cache-Control: no-cache
```

**Reconnection**: send `Last-Event-ID: {event_id}` header; server resumes from that event.  
Stream closes automatically on `RUN_COMPLETED` or `RUN_FAILED` event.

### SSE Event Types

All events: `data: {JSON}` with `id: {monotonic_int}` and `event: {EventType}`.

```python
SSEEventType = Literal[
    "SECTION_APPROVED",
    "JURY_VERDICT",
    "REFLECTOR_FEEDBACK",
    "ESCALATION_REQUIRED",
    "BUDGET_WARNING",
    "RUN_COMPLETED",
    "RUN_FAILED",
    "HEARTBEAT"
]
```

**Typed payloads**

```python
class SectionApprovedEvent(TypedDict):
    event: Literal["SECTION_APPROVED"]
    run_id: str
    section_index: int
    section_title: str
    css_final: float
    iterations_used: int
    cost_usd: float
    approved_at: str

class JuryVerdictEvent(TypedDict):
    event: Literal["JURY_VERDICT"]
    run_id: str
    section_index: int
    iteration: int
    css_content: float
    css_style: float
    pass_reasoning: bool
    pass_factual: bool
    pass_style: bool
    veto_active: bool
    veto_category: str | None

class ReflectorFeedbackEvent(TypedDict):
    event: Literal["REFLECTOR_FEEDBACK"]
    run_id: str
    section_index: int
    iteration: int
    scope: Literal["SURGICAL", "PARTIAL", "FULL"]
    feedback_count: int
    critical_count: int

class EscalationRequiredEvent(TypedDict):
    event: Literal["ESCALATION_REQUIRED"]
    run_id: str
    escalation_type: Literal[
        "outline_approval", "oscillation", "coherence_conflict",
        "budget_exceeded", "full_rewrite_required"
    ]
    section_index: int | None
    message: str
    options: list[str]               # human-readable action labels
    approve_url: str                 # POST /v1/runs/{id}/approve

class BudgetWarningEvent(TypedDict):
    event: Literal["BUDGET_WARNING"]
    run_id: str
    spent_usd: float
    budget_usd: float
    pct_used: float                  # 0.70 | 0.90
    regime_active: str               # "balanced" | "economy"

class RunCompletedEvent(TypedDict):
    event: Literal["RUN_COMPLETED"]
    run_id: str
    document_id: str
    cost_total_usd: float
    word_count: int
    sections_count: int
    avg_css: float
    duration_minutes: float
    export_urls: dict[str, str]      # format -> pre-signed URL (15 min TTL)

class RunFailedEvent(TypedDict):
    event: Literal["RUN_FAILED"]
    run_id: str
    error_code: str
    error_message: str
    partial_document_id: str | None  # if some sections approved before failure

class HeartbeatEvent(TypedDict):
    event: Literal["HEARTBEAT"]
    timestamp: str                   # every 30s to keep connection alive
```

**Wire format example**

```
id: 42
event: SECTION_APPROVED
data: {"event":"SECTION_APPROVED","run_id":"run-uuid","section_index":2,"section_title":"Methods","css_final":0.87,"iterations_used":2,"cost_usd":6.20,"approved_at":"2026-01-15T14:22:11Z"}

id: 43
event: HEARTBEAT
data: {"event":"HEARTBEAT","timestamp":"2026-01-15T14:22:41Z"}
```

**curl**

```bash
curl -N https://api.drs.example.com/v1/runs/run-uuid/stream \
  -H "X-DRS-Key: sk-drs-abc123-..." \
  -H "Accept: text/event-stream"
```

---

## §24.4 Human-in-the-Loop Endpoints

### POST /v1/runs/{run_id}/approve

Respond to `ESCALATION_REQUIRED` events.

**Request**

```python
class ApproveRequest(TypedDict):
    escalation_type: Literal["outline_approval", "oscillation", "coherence_conflict"]

    # For outline_approval
    approved_outline: list[dict] | None   # modified OutlineSection list; None = accept as-is

    # For oscillation / coherence_conflict
    action: Literal[
        "provide_instructions", "approve_with_warning",
        "skip_section", "modify_scope", "abort"
    ] | None
    instructions: str | None              # free text fed to Writer/Reflector; max 2000 chars
    scope_override: str | None            # new scope text for the section
```

**Response 200**

```python
class ApproveResponse(TypedDict):
    run_id: str
    escalation_resolved: bool
    run_status: RunStatus
    message: str
```

**HTTP codes**

| Code | Meaning |
|------|---------|
| 200 | Escalation resolved, run resumed |
| 400 | No pending escalation or invalid action |
| 409 | Run not in `awaiting_approval` status |

---

### POST /v1/runs/{run_id}/pause

Pause after current section completes (does not interrupt mid-section).

**Response 200**

```python
class PauseResponse(TypedDict):
    run_id: str
    status: Literal["paused"]
    current_section_index: int
    cost_accumulated_usd: float
```

---

### POST /v1/runs/{run_id}/resume

Resume a paused run.

**Response 200**

```python
class ResumeResponse(TypedDict):
    run_id: str
    status: Literal["running"]
    resumed_at: str
```

---

## §24.5 Document Export Endpoint

### GET /v1/documents/{document_id}/export

**Query params**

```python
format: Literal["docx", "pdf", "markdown", "latex", "json"]  # required
```

**Response 303** — redirect to pre-signed S3/MinIO URL (TTL: 900 seconds).

**Response body (on 200 if redirect disabled)**

```python
class ExportResponse(TypedDict):
    document_id: str
    format: str
    download_url: str          # pre-signed, expires in 900s
    expires_at: str
    file_size_bytes: int
```

**HTTP codes**

| Code | Meaning |
|------|---------|
| 303 | Redirect to pre-signed URL |
| 400 | Unsupported format |
| 404 | document_id not found |
| 409 | Document not yet complete (`status != "complete"`) |
| 410 | Export URL expired; re-request |

**curl**

```bash
curl -L https://api.drs.example.com/v1/documents/doc-uuid/export?format=docx \
  -H "X-DRS-Key: sk-drs-abc123-..." \
  -o output.docx
```

---

## §24.6 Webhook Delivery

Sent on `run.completed` and `run.failed` to `notify_webhook` URL.

```python
class WebhookPayload(TypedDict):
    event: Literal["run.completed", "run.failed"]
    run_id: str
    document_id: str | None
    status: RunStatus
    cost_total_usd: float
    word_count: int | None
    document_url: str | None         # pre-signed, 900s TTL
    timestamp: str
    signature: str                   # HMAC-SHA256(secret, f"{run_id}.{timestamp}")
```

Retry policy: 3 attempts, backoff `[10s, 60s, 300s]`. Consumer must respond `200` within 5 seconds. Failed delivery → logged, no further retry.

---

## §24.7 API Agent Spec

AGENT: APIGateway [§24]  
RESPONSIBILITY: Validate, authenticate, and proxy requests to LangGraph Server  
MODEL: N/A (FastAPI, no LLM)  
INPUT:  
  `http_request: Request`  
OUTPUT: `Response`  
CONSTRAINTS:  
  MUST reject missing/invalid auth with `401` before touching DB  
  MUST enforce rate limits (see §24.1) before forwarding  
  NEVER proxy requests where `run.user_id != authenticated_user_id`  
  ALWAYS validate request body with Pydantic before forwarding  
  MUST set `Retry-After` header on every `429`  
ERROR_HANDLING:  
  `pydantic.ValidationError` -> `422` with field-level errors -> no fallback  
  `db_timeout > 3s` -> `503` with `Retry-After: 5` -> no fallback  
  `langgraph_server_unreachable` -> `503` -> alert Sentry  
CONSUMES: `[]` from DocumentState  
PRODUCES: `[]` → DocumentState  

<!-- SPEC_COMPLETE -->