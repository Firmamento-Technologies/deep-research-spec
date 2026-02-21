# §38 — Operational Rules for the AI Builder

## §38.0 Rule Schema

```python
class BuilderRule(TypedDict):
    name: str
    description: str
    rationale: str
    correct_example: str   # Python code block reference
    wrong_example: str     # Python code block reference
    consequence_if_violated: str
```

---

## §38.1 PREFLIGHT-MANDATORY

**NAME:** `PREFLIGHT_THREAD_ID_IMMEDIATE`

**DESCRIPTION:** `thread_id` MUST be persisted to PostgreSQL `runs` table atomically before any LLM call, source fetch, or state mutation. The preflight node is always the graph entry point (see §4.1, §21.2).

**RATIONALE:** If the process crashes after the first LLM call but before `thread_id` is written, the run is unrecoverable — no checkpoint can be resumed because LangGraph's `AsyncPostgresSaver` keys recovery on `thread_id`.

```python
# CORRECT
async def preflight_node(state: DocumentState) -> DocumentState:
    thread_id = str(uuid4())
    await db.execute(
        "INSERT INTO runs (id, thread_id, status, config) VALUES ($1,$2,'initializing',$3)",
        state["run_id"], thread_id, json.dumps(state["config"])
    )
    return {**state, "thread_id": thread_id, "status": "initializing"}
```

```python
# WRONG — thread_id written after first LLM call
async def preflight_node(state: DocumentState) -> DocumentState:
    outline = await call_llm("planner", ...)          # crash here = unrecoverable
    thread_id = str(uuid4())
    await db.execute("INSERT INTO runs ...", thread_id)
    return {**state, "thread_id": thread_id, "outline": outline}
```

**CONSEQUENCE_IF_VIOLATED:** Crashed runs produce orphaned LLM spend with no recovery path. `GET /v1/runs/{id}` returns 404. Partial sections already approved are lost.

---

## §38.2 PYDANTIC-MANDATORY

**NAME:** `PYDANTIC_PARSE_NO_JSON_LOADS`

**DESCRIPTION:** Every LLM response that produces structured data MUST be parsed via a Pydantic model. `json.loads()` direct on LLM output is NEVER permitted. On `ValidationError` the node MUST default to FAIL state, log the raw string, and trigger the error handling path (see §20.1).

**RATIONALE:** LLMs emit malformed JSON, partial JSON, markdown-wrapped JSON, and truncated JSON. Silent parse failure propagates corrupt state downstream (e.g., a `None` CSS value bypasses all routing logic).

```python
# CORRECT
from pydantic import BaseModel, ValidationError

class JudgeVerdict(BaseModel):
    pass_fail: bool
    css_contribution: float
    veto_category: Literal["fabricated_source","factual_error",
                           "logical_contradiction","plagiarism"] | None
    confidence: Literal["low","medium","high"]
    comments: str

async def parse_judge_output(raw: str) -> JudgeVerdict:
    try:
        data = json.loads(raw)           # extract dict first
        return JudgeVerdict(**data)       # validate via Pydantic
    except (json.JSONDecodeError, ValidationError) as e:
        log.error("judge_parse_error", raw=raw[:500], error=str(e))
        return JudgeVerdict(             # FAIL safe default
            pass_fail=False,
            css_contribution=0.0,
            veto_category=None,
            confidence="low",
            comments=f"PARSE_ERROR: {str(e)[:200]}"
        )
```

```python
# WRONG — no validation, silent corruption
async def parse_judge_output(raw: str) -> dict:
    return json.loads(raw)   # KeyError or None propagates silently
```

**CONSEQUENCE_IF_VIOLATED:** `None` or partial dict in `DocumentState.jury_verdicts` causes `KeyError` in Aggregator CSS formula (§9.1). Entire run crashes at aggregation with no actionable error message.

---

## §38.3 ASYNC-PARALLELISM

**NAME:** `ASYNC_PARALLELISM_RULES`

**DESCRIPTION:** Three parallelism rules with no exceptions:

| Operation | Rule | Implementation |
|---|---|---|
| Three mini-juries (R, F, S) | ALWAYS parallel | `asyncio.gather()` |
| MoW Writers (W-A, W-B, W-C) | ALWAYS parallel | `asyncio.gather()` |
| Reflector analysis | ALWAYS sequential | single `await` |

Never `await` inside a `for` loop over parallelizable operations.

```python
# CORRECT — juries in parallel
async def jury_node(state: DocumentState) -> DocumentState:
    r_verdicts, f_verdicts, s_verdicts = await asyncio.gather(
        run_mini_jury_reasoning(state["current_draft"], state),
        run_mini_jury_factual(state["current_draft"], state),
        run_mini_jury_style(state["current_draft"], state),
    )
    return {**state, "jury_verdicts": r_verdicts + f_verdicts + s_verdicts}

# CORRECT — MoW writers in parallel
async def mow_node(state: DocumentState) -> DocumentState:
    draft_a, draft_b, draft_c = await asyncio.gather(
        call_writer(state, angle="coverage",      temperature=0.30),
        call_writer(state, angle="argumentation", temperature=0.60),
        call_writer(state, angle="readability",   temperature=0.80),
    )
    return {**state, "mow_drafts": [draft_a, draft_b, draft_c]}

# CORRECT — Reflector is sequential (reads full verdict history)
async def reflector_node(state: DocumentState) -> DocumentState:
    result = await call_llm("reflector", build_reflector_prompt(state))
    feedback = await parse_reflector_output(result["content"])
    return {**state, "reflector_output": feedback}
```

```python
# WRONG — sequential jury loop wastes 2/3 of available latency
async def jury_node(state: DocumentState) -> DocumentState:
    all_verdicts = []
    for jury_fn in [run_mini_jury_reasoning, run_mini_jury_factual, run_mini_jury_style]:
        verdicts = await jury_fn(state["current_draft"], state)   # sequential!
        all_verdicts.extend(verdicts)
    return {**state, "jury_verdicts": all_verdicts}
```

**CONSEQUENCE_IF_VIOLATED:** Sequential jury triples per-section latency (3× API RTT). A 90-minute run becomes 270 minutes. `asyncio.gather` is not optional.

---

## §38.4 WEBSOCKET-VIA-REDIS-PUBSUB

**NAME:** `WEBSOCKET_REDIS_PUBSUB_NO_POLLING`

**DESCRIPTION:** Progress events MUST follow the publish/subscribe pattern:
1. Celery worker publishes event to Redis channel `run:{run_id}:events`
2. FastAPI SSE endpoint subscribes and forwards to client
3. Client receives push. Polling of any endpoint for progress is NEVER permitted in production.

Event types: `Literal["SECTION_APPROVED","JURY_VERDICT","REFLECTOR_FEEDBACK","ESCALATION_REQUIRED","BUDGET_WARNING","RUN_COMPLETED"]`

```python
# CORRECT — Celery worker publishes
from redis.asyncio import Redis

async def publish_event(redis: Redis, run_id: str, event: dict) -> None:
    await redis.publish(f"run:{run_id}:events", json.dumps(event))

# Called inside any LangGraph node after state update:
await publish_event(redis, state["run_id"], {
    "type": "SECTION_APPROVED",
    "section_idx": state["current_section_idx"],
    "css": state["css_history"][-1],
    "cost_accumulated_usd": state["budget"]["spent_dollars"],
    "timestamp": datetime.utcnow().isoformat(),
})

# CORRECT — FastAPI SSE endpoint subscribes
from fastapi.responses import StreamingResponse

@router.get("/v1/runs/{run_id}/stream")
async def stream_run(run_id: str, redis: Redis = Depends(get_redis)):
    async def event_generator():
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"run:{run_id}:events")
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield f"data: {message['data'].decode()}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

```python
# WRONG — client polling endpoint every N seconds
@router.get("/v1/runs/{run_id}/poll")
async def poll_run(run_id: str):
    return await db.fetchrow("SELECT status, current_section FROM runs WHERE id=$1", run_id)
# Client calls this in a setInterval loop — N×M database hits, stale data, no backpressure
```

**CONSEQUENCE_IF_VIOLATED:** Polling under load (100 concurrent runs × 30s polling interval) generates 200 req/min of unnecessary DB reads. SSE with Redis pub/sub is O(1) fan-out regardless of client count.

---

## §38.5 DI-MANDATORY

**NAME:** `DEPENDENCY_INJECTION_NO_DIRECT_IMPORTS`

**DESCRIPTION:**
- `import openai`, `import anthropic`, `import httpx` are NEVER written inside `src/agents/` files.
- Every agent class MUST accept all external clients (`LLMClient`, `SearchClient`, `DBClient`) via `__init__` constructor injection.
- `MockLLMClient` implementing the same protocol MUST be injectable with zero code changes.
- Production wiring happens in `src/graph/graph.py` only.

```python
# CORRECT — agent accepts injected client
# src/agents/writer.py
from src.llm.protocols import LLMClientProtocol

class WriterAgent:
    def __init__(self, llm_client: LLMClientProtocol) -> None:
        self._llm = llm_client

    async def run(self, state: DocumentState) -> DocumentState:
        result = await self._llm.call(
            model=state["config"]["models"]["writer"],
            system_prompt=build_writer_system_prompt(state),
            user_prompt=build_writer_user_prompt(state),
        )
        draft = result["content"]
        return {**state, "current_draft": draft}

# src/llm/protocols.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class LLMClientProtocol(Protocol):
    async def call(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict[str, str | int | float]: ...

# src/llm/mock_client.py  — used in ALL tests
class MockLLMClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses  # model -> canned response

    async def call(self, model: str, **_) -> dict[str, str | int | float]:
        return {
            "content": self._responses.get(model, '{"pass_fail": true}'),
            "model_used": model, "tokens_in": 100, "tokens_out": 50, "cost_usd": 0.0,
        }

# tests/test_writer.py
async def test_writer_produces_non_empty_draft():
    mock_llm = MockLLMClient({"anthropic/claude-opus-4-5": "Draft content here."})
    agent = WriterAgent(llm_client=mock_llm)
    result = await agent.run(make_test_state())
    assert len(result["current_draft"]) > 0
```

```python
# WRONG — direct import inside agent module
# src/agents/writer.py
import openai                          # FORBIDDEN in src/agents/

async def run(state: DocumentState) -> DocumentState:
    client = openai.AsyncOpenAI(api_key=os.environ["OPENROUTER_API_KEY"])
    resp = await client.chat.completions.create(...)   # untestable without network
```

**CONSEQUENCE_IF_VIOLATED:** Unit tests require live API keys and network. CI costs accumulate. A single `openai` import in `src/agents/` breaks §25.3 (Mock LLM test layer) and makes §25.11 smoke suite impossible to run in <2 minutes.

---

## §38.6 Cross-Rule Dependency Matrix

| Rule | Enforced by | Verified by test layer |
|---|---|---|
| §38.1 PREFLIGHT | LangGraph entry point | §25.3 Integration + §25.11 Smoke |
| §38.2 PYDANTIC | `parse_*` helpers in `src/agents/` | §25.2 Unit (all parsers) |
| §38.3 ASYNC | Code review + `asyncio` lint rule | §25.2 timing assertion |
| §38.4 WS-REDIS | `src/api/routes/stream.py` | §25.3 Integration (mock Redis) |
| §38.5 DI | `import` linter in CI (`src/agents/` scope) | §25.3 all agents with MockLLMClient |

<!-- SPEC_COMPLETE -->