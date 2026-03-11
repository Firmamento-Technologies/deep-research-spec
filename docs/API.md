# DRS API Reference

## Base URL

```
http://localhost:8000
```

## Authentication

Currently unauthenticated (development). Production should use API keys via `Authorization: Bearer <key>` header.

---

## Endpoints

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "uptime_seconds": 1234.5,
  "active_runs": 0,
  "version": "1.0.0"
}
```

---

### Start Pipeline Run

```http
POST /api/runs
Content-Type: application/json
```

**Request Body:**
```json
{
  "topic": "Climate change impacts on agriculture",
  "target_words": 10000,
  "quality_preset": "balanced",
  "style_profile": "academic",
  "sections": 5,
  "language": "en"
}
```

**Response (202 Accepted):**
```json
{
  "run_id": "abc-123-def",
  "status": "pending",
  "created_at": "2026-02-24T09:00:00Z"
}
```

---

### Get Run Status

```http
GET /api/runs/{run_id}
```

**Response:**
```json
{
  "run_id": "abc-123-def",
  "status": "running",
  "progress": {
    "current_section": 3,
    "total_sections": 5,
    "current_iteration": 2
  },
  "cost_usd": 1.23,
  "created_at": "2026-02-24T09:00:00Z",
  "updated_at": "2026-02-24T09:05:00Z"
}
```

**Status values:** `pending`, `running`, `completed`, `failed`, `cancelled`

---

### List Runs

```http
GET /api/runs
```

**Response:**
```json
{
  "runs": [
    {"run_id": "abc-123", "status": "completed", "topic": "..."},
    {"run_id": "def-456", "status": "running", "topic": "..."}
  ],
  "total": 2
}
```

---

### Cancel Run

```http
DELETE /api/runs/{run_id}
```

**Response (204 No Content)**

---

## Metrics Endpoint

```http
GET :9090/metrics
```

Returns Prometheus-formatted metrics:

```
# HELP drs_llm_calls_total Total LLM API calls
drs_llm_calls_total{agent="writer",model="anthropic/claude-sonnet-4-20250514",preset="balanced"} 42

# HELP drs_llm_cost_dollars_total Cumulative LLM cost in USD
drs_llm_cost_dollars_total{agent="writer",model="anthropic/claude-sonnet-4-20250514"} 3.14

# HELP drs_jury_pass_rate Jury approval rate
drs_jury_pass_rate{preset="balanced"} 0.78
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Run not found: abc-123"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Invalid request body |
| 404 | Resource not found |
| 422 | Validation error |
| 500 | Internal server error |
