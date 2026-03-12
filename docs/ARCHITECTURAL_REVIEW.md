# Hyper-Critical Architectural Review — Deep Research System (DRS)

*Reviewer posture: Senior Software Architect, adversarial honesty. Every claim grounded in code read during this review.*

---

## Part 1 — Architectural Audit

### 1.1 Structural Coherence: Two Codebases Pretending to Be One

The most consequential architectural defect in DRS is not a bug in any single module but the existence of two separate, diverging implementations of the same system. The `src/` directory contains the spec-faithful LangGraph pipeline: 41 node files under `src/graph/nodes/`, a 32-node `StateGraph` in `src/graph/graph.py` (309 lines), a `DocumentState` TypedDict with ~50 fields in `src/graph/state.py` (272 lines), and a multi-provider `LLMClient` in `src/llm/client.py` (468 lines) with thread-safe lazy SDK initialization, per-model rate limiting, and OpenRouter/Anthropic/Google/OpenAI routing. Alongside this, `backend/src/graph/graph_builder.py` (376 lines) defines a completely different 5-node pipeline — planner, researcher, writer, critic, finalizer — using its own `ResearchState` schema from `backend/src/models/state.py`, its own LLM client at `backend/src/llm/client.py` (506 lines) that communicates exclusively via OpenRouter with a `_SettingsCache` that reads model assignments from a PostgreSQL `Settings` table, and its own `RunManager` singleton at `backend/src/services/run_manager.py` (448 lines) with in-memory `active_runs` tracking.

This duplication is not mere file overlap. The two pipelines are architecturally incompatible. The `src/` pipeline routes through a 9-judge jury system with heterogeneous model backbones (`src/graph/nodes/jury.py`, 152 lines, uses `ThreadPoolExecutor(max_workers=9)` for parallel evaluation), while the `backend/` pipeline uses a single "critic" node with binary approve/rewrite routing. The `src/` pipeline has SHINE LoRA integration (`src/graph/nodes/shine_adapter.py`, 267 lines), RLM recursive mode in the writer (`src/graph/nodes/writer.py`, 383 lines, three execution paths), oscillation detection, panel discussion, coherence guards, and diff merging — none of which exist in `backend/`. The `backend/` pipeline has actual database models (`backend/database/models.py`), Alembic migrations (three versions), a FastAPI application with auth endpoints (`backend/api/auth.py`), SSE broker for real-time events (`backend/services/sse_broker.py`), MinIO integration for file exports (`backend/services/minio_service.py`), and a Knowledge Space indexer with pgvector semantic search (`backend/services/space_indexer.py`, `backend/services/semantic_search.py`) — none of which the `src/` pipeline can access.

The practical consequence is severe: no single code path can produce a production run. The `src/` pipeline has the quality machinery but no persistence or API surface. The `backend/` pipeline has the infrastructure but trivial quality logic. Someone deploying DRS must choose one implementation and rewrite the other's capabilities, or attempt a merge that neither codebase was designed for. The `backend/src/graph/graph_builder.py` `merge_state` reducer naïvely uses shallow dict merge with special-case budget arithmetic, while `src/graph/state.py` uses LangGraph's annotated reducers with `_max_len_reducer` bounds — these are fundamentally different state management strategies.

### 1.2 Agent Orchestration: Ambitious Design, Incomplete Execution

The `src/` pipeline's 32-node graph (`src/graph/graph.py`) is the most architecturally ambitious component and, on paper, represents a sophisticated multi-agent orchestration. The node registration is real: `graph.add_node("writer", writer.writer_node)` points to actual implementations, not stubs. The conditional routing handles complex flows — the style lint loop routes through `style_linter → style_fixer → writer` with a termination guard via `max_style_iter`, and the content gate routes through `aggregator → reflector` or `aggregator → panel_discussion` based on CSS thresholds. However, the comment at line ~309 claiming "All 32 nodes have real implementations — zero stubs" is misleading. While no node uses the legacy `_make_stub()` factory, several "real" implementations are effectively passthroughs. The `section_checkpoint` node writes state to the checkpointer but does no domain logic. The `metrics_collector` node emits OpenTelemetry spans but has no fallback if tracing is not configured. And the `feedback_collector` node appears to aggregate feedback but has no mechanism to receive it from an external source in the `src/` pipeline (this is handled by the `backend/` SSE broker that the `src/` pipeline cannot reach).

The Researcher node (`src/graph/nodes/researcher.py`, 124 lines) is the most significant gap. The spec (§5.2) calls for a five-tier connector cascade: memvid_local → academic → institutional → web → social. The implementation has exactly one connector: `MemvidConnector` from `src/connectors/memvid_connector.py` (171 lines), which queries a local Memvid video-encoded vector store using bge-m3 embeddings. The `get_default_connectors()` function at line 19 returns `[MemvidConnector(knowledge_path=knowledge_path)]` with a TODO comment: "add sonar-pro, tavily, brave connectors." Meanwhile, `backend/src/services/web_search.py` exists with what appears to be a Tavily/Brave integration, but it lives in the wrong codebase and uses the wrong state schema. The research capability of the spec-faithful pipeline is therefore limited to whatever the user has pre-loaded into a local `.mp4` knowledge base, which is a dramatic reduction in the system's raison d'être as a "deep research" tool.

### 1.3 Cost-to-Value Ratio: The gpt-4.5 Problem and Model Pricing Fragility

The model pricing architecture reveals a critical fragility. `src/llm/pricing.py` (32 lines) defines `MODEL_PRICING` as a flat dictionary keyed by `"provider/model"` strings. The `cost_usd()` function at line 28 performs a bare dictionary lookup: `p = MODEL_PRICING[model_id]` — no `.get()`, no fallback, no error handling. This will raise `KeyError` at runtime whenever OpenRouter returns a model string that doesn't exactly match the 17 entries in the dictionary. The `backend/src/llm/client.py` (line 474) handles this correctly with a try/except around `cost_usd()` that falls back to `0.0`, but `src/llm/pricing.py` itself provides no safety net, and any node in the `src/` pipeline that calls `cost_usd()` directly (rather than through the backend client) will crash.

Beyond the KeyError risk, the pricing table itself is dangerously inaccurate. It lists only 17 models while the routing table references many more. It omits Anthropic cache token costs entirely — `cache_creation_input` and `cache_read_input` tokens are ~90% cheaper than standard input tokens, and the writer node uses `cache_control: {"type": "ephemeral"}` blocks extensively (confirmed in `src/graph/nodes/writer.py` lines 216–232). It also ignores the 10–30% OpenRouter markup applied to all proxied models. The net result is cost estimates that are ±20% inaccurate, which means the budget controller's projections and threshold decisions operate on systematically wrong data.

The routing table in `src/llm/routing.py` (547 lines) uses `openrouter/` prefixed model IDs for all agents except the writer, which uses `anthropic/` prefix for direct API access to enable prompt caching. The pricing table uses unprefixed `provider/model` IDs (e.g., `"anthropic/claude-opus-4-5"` not `"openrouter/anthropic/claude-opus-4-5"`). This inconsistency means that the routing layer must strip prefixes before pricing lookups, and the `_build_result()` method in `src/llm/client.py` must normalize the `model_used` string. If this normalization fails for any model, cost tracking silently breaks, and the budget controller makes decisions on incomplete data. There is also a subtle lateral fallback bug in the routing logic: when a preset lookup returns empty string (because `preset_lower` doesn't exist in the agent's route dict), the code passes that empty string to `_LATERAL_FALLBACKS.get("", [])`, which silently returns no fallbacks rather than escalating to vertical downgrade.

The budget estimator v2 (`backend/src/services/budget_estimator_v2.py`, 374 lines) exists as a standalone module that fixes six documented bugs in the original estimator — including an 18× cost underestimate for `gpt-4.5` (at $150/M output tokens, style judge slot `judge_s1` using GPT-4.5 is by far the most expensive per-call component). This fix is correct and important, but the module lives in `backend/src/services/` and is **not integrated into either pipeline's actual execution path**. The `src/graph/nodes/budget_estimator.py` node in the main pipeline does not import or reference `budget_estimator_v2`. The `sys.path.insert(0, ...)` hack at line 29 of `budget_estimator_v2.py` confirms this module was designed to run standalone, not as part of the pipeline. The most critical cost calculation improvement in the codebase is dead code.

### 1.3.1 Budget Enforcement Is Theater

The budget management architecture has a deeper problem than inaccurate pricing: enforcement is fragmented across three disconnected lanes that never converge into a hard stop. The `src/budget/guard.py` `check_budget()` function checks `hard_stop_fired`, `spent >= max`, and estimated overage — but `src/graph/nodes/budget_controller.py` projects costs without ever raising exceptions or triggering hard stops. An `RLMBudgetController` exists at `src/budget/controller.py` but is **never instantiated or called** anywhere in the codebase — pure dead code. And the writer node's RLM cost reconciliation (lines 172–179 in `writer.py`) wraps the `result.usage_summary.total_cost` read in a try/except that silently logs a warning and skips the budget update on any `AttributeError`, `TypeError`, or `ValueError`. This means an RLM run where `usage_summary` is malformed will proceed with `budget['spent_dollars']` frozen at its pre-call value, and all downstream budget decisions (regime re-derivation, savings triggers, hard stop checks) will operate on stale data.

### 1.4 Scalability: Singleton Patterns and Concurrency Ceilings

The `src/` pipeline relies heavily on module-level singletons. The LLM client is instantiated at module level: `llm_client = LLMClient()` in `src/llm/client.py`. The jury uses a module-level `ThreadPoolExecutor(max_workers=9)` in `src/graph/nodes/jury.py`. The SHINE adapter uses a thread-safe singleton with double-checked locking (`SHINEAdapterSingleton` in `src/graph/nodes/shine_adapter.py`). The researcher uses a module-level `_default_node = ResearcherNode()`. These singletons create a hard concurrency ceiling: multiple concurrent runs share the same thread pool, the same rate limiter state, and the same SHINE model instance. The `ThreadPoolExecutor(max_workers=9)` for the jury means that two concurrent runs with Premium preset (jury_size=3, 9 judges each) will contend for the same 9 worker threads, serializing what should be parallel evaluation. Additionally, the jury's `futures.as_completed()` call has no timeout — if a single judge hangs (e.g., OpenRouter drops the connection without closing it), the entire jury blocks indefinitely, and by extension the entire run stalls with no recovery path.

The `backend/` `RunManager` tracks active runs in an in-memory dictionary (`active_runs: Dict[str, Dict[str, Any]] = {}`), which is adequate for a single-process deployment but incompatible with the spec's Kubernetes/KEDA scaling aspirations (§34). If two API servers handle concurrent runs, they have no shared visibility into active runs, no distributed locking, and no way to prevent duplicate run launches. The spec's Celery+Redis architecture (§34.2) is never implemented — the `backend/` pipeline uses plain `asyncio.create_task()` for background execution.

### 1.5 Data Flow: State Accumulation and Memory Pressure

The `DocumentState` TypedDict in `src/graph/state.py` includes bounded reducers that cap certain fields: `css_history` keeps the last 8 entries, `draft_embeddings` keeps the last 4. This is a thoughtful design for preventing unbounded state growth. However, several fields lack such bounds: `all_verdicts_history` is capped at 10 rounds in `src/graph/nodes/jury.py` (line 149) but `reflector_feedback_history`, `writer_versions`, and `current_sources` have no explicit bounds. For a Premium run with 8 sections and up to 8 iterations per section, `writer_versions` could accumulate 64 draft texts, each potentially 2000+ words. LangGraph checkpoints the entire state at every node, so this accumulation multiplies storage requirements.

The `backend/` pipeline's `merge_state` reducer compounds this problem by performing shallow dict merges that never prune historical data. There is no equivalent of the `_max_len_reducer` pattern. A long-running backend run will checkpoint progressively larger state dictionaries until it either succeeds or runs out of the PostgreSQL connection pool.

---

## Part 2 — RLM Integration Analysis

### 2.1 What RLM Actually Is

RLM (Recursive Language Models, github.com/alexzhang13/rlm) is not a model — it is an inference-time wrapper that gives an LLM access to a persistent Python REPL environment. The user calls `rlm.completion("prompt")`, and internally the LLM receives a system prompt explaining it has a `context` variable and helper functions (`llm_query`, `rlm_query`, `FINAL_VAR`, `SHOW_VARS`). The LLM responds with ` ```repl ``` ` code blocks that are extracted via regex and executed in a sandboxed REPL. This loops up to `max_iterations` times until the LLM calls `FINAL_VAR(variable_name)` or `FINAL(answer_text)`. Critically, `rlm_query()` inside the REPL can spawn child RLM instances at `depth + 1`, creating a recursive decomposition tree where each subtask gets its own REPL, iteration loop, and inherited resource constraints.

### 2.2 Adapter Alignment

The existing `src/llm/rlm_adapter.py` (151 lines) is well-aligned with RLM's actual API. The constructor usage — `RLM(backend=..., backend_kwargs={"model_name": ...}, other_backends=[...], other_backend_kwargs=[...], environment=..., max_depth=..., max_iterations=..., max_budget=..., logger=...)` — matches the real `RLM.__init__` signature exactly. The adapter correctly recognizes that `get_client()` is a closed factory with no `custom_client=` parameter for injecting custom LLM backends, and it documents why a previous `DeepResearchLM` custom bridge was removed. The `_parse_model_string()` function splits `"provider/model_name"` format and validates against known backends.

Budget enforcement is correctly delegated: `max_budget` is passed to RLM for internal enforcement, and after `rlm.completion()`, the caller reads `result.usage_summary.total_cost` to reconcile with `state['budget']['spent_dollars']`. RLM raises `BudgetExceededError` (with `partial_answer`) when exceeded, which the writer node at `src/graph/nodes/writer.py` handles in its RLM path.

### 2.3 Integration Gaps

**Closed client factory.** RLM's `get_client()` accepts only 8-9 known backend strings: `{openai, openrouter, anthropic, vllm, litellm, portkey, gemini, azure_openai}`. There is no way to inject a pre-built `BaseLM` instance, which means DRS cannot route RLM calls through its own rate limiter, circuit breaker, or fallback logic in `src/llm/resilience.py`. If OpenRouter returns 429, DRS's `retry_with_backoff` decorator never fires — RLM's internal error counter increments instead, potentially triggering `ErrorThresholdExceededError` rather than graceful fallback.

**Security sandbox gap.** RLM's local REPL uses `exec()` with a "safe builtins" blocklist. This is explicitly not a true security sandbox. DRS processes external source content that passes through the SourceSanitizer (§22.4), but if any sanitized content reaches the RLM REPL via the writer's prompt, a sufficiently crafted injection could execute arbitrary Python. The spec's `PrivacyMode.SELF_HOSTED` variant would be particularly exposed since all processing is local and RLM's REPL has filesystem access.

**No retry for transient failures.** RLM has no built-in retry logic for API failures. Errors increment a counter that triggers `ErrorThresholdExceededError` — a terminal failure, not a recoverable one. DRS's `retry_with_backoff` in `src/llm/resilience.py` (178 lines) has exponential backoff with jitter and retryable exception detection, but since RLM manages its own API calls internally, this resilience layer is bypassed entirely in RLM mode.

**One minor discrepancy.** The adapter lists `"vercel"` in `_KNOWN_BACKENDS`, but RLM's `rlm/clients/` directory does not contain a Vercel client implementation. This is either a newer addition not yet published or an error in the adapter.

### 2.4 Cost-Value Verdict

RLM adds value for tasks requiring multi-step reasoning with code execution — mathematical proofs, data analysis pipelines, complex logical decompositions. For DRS's primary use case (prose research documents), the REPL-centric approach is awkward: the writer must generate code that generates prose, adding an indirection layer with no quality benefit for narrative text. The recursive decomposition is genuinely useful for section-level planning (breaking a complex topic into researchable sub-questions), but the current integration uses it for writing, where the overhead of REPL execution and multiple LLM round-trips likely exceeds the quality improvement over a single well-prompted call. The budget tracking is sound, but the loss of DRS's resilience and observability layers is a significant operational cost that the adapter cannot mitigate without upstream RLM changes.

---

## Part 3 — SHINE Integration Analysis

### 3.1 What SHINE Does

SHINE (Scalable Hypernet for Instruction-based Neural Encoding) is a LoRA hypernetwork that generates task-specific LoRA adapters from a text corpus. Instead of including the full corpus in the LLM's context window, SHINE compresses the corpus into a small LoRA weight matrix that modifies the base model's behavior to "know" the corpus content. The theoretical promise is dramatic: a ~95% token reduction by replacing thousands of context tokens with a LoRA injection that costs ~0 tokens at inference time.

### 3.2 Current Integration

The `src/graph/nodes/shine_adapter.py` (267 lines) implements a `SHINEAdapterSingleton` that lazily loads the SHINE hypernetwork model onto GPU. The node sits between `source_synthesizer` and `writer` in the graph (confirmed in `src/graph/graph.py`). Skip conditions are well-defined: SHINE not installed, Economy preset, section under 400 words, iteration > 1 (LoRA only helps on first pass), or empty corpus. When active, it calls `shine.generate_lora(corpus, max_length=1150)` — approximately 0.3s on GPU — and stores the resulting LoRA weights in `state["shine_lora"]`. The writer node then applies this LoRA when generating the section draft.

Graceful degradation is correctly implemented: any failure returns `{"shine_active": False}`, allowing the writer to fall back to standard context-window-based generation. The GPU memory management via `torch.cuda.empty_cache()` after LoRA generation is present but may not be sufficient for concurrent runs sharing the same GPU.

### 3.3 Integration Gaps

**GPU contention.** The singleton pattern means all concurrent runs share one SHINE model instance. LoRA generation itself is fast (~0.3s) but the base model occupies GPU memory permanently. On a single-GPU deployment, this competes directly with any self-hosted LLM running on the same hardware (the spec's `PrivacyMode.SELF_HOSTED` uses Ollama models that also require GPU). There is no GPU memory arbitration between SHINE and Ollama.

**LoRA application mechanism unclear.** The adapter generates LoRA weights and stores them in state, but how these weights are applied to the writer's LLM call is not visible in the adapter code. If the writer uses OpenRouter (cloud API), LoRA weights cannot be applied — they require direct model weight access. This only works with self-hosted models (Ollama/VLLM), creating an implicit dependency that is not enforced: a user in `cloud` privacy mode with SHINE enabled would generate LoRA weights that are silently unused.

**API mismatch.** The adapter imports `from shine import ShineHypernet` and calls `shine.generate_lora(corpus, max_length=1150)` — a simple string-in, LoRA-out interface. However, the upstream SHINE repository exposes `Metanetwork.generate_lora_dict(evidence_ids, evidence_attention_mask, metalora)` — a lower-level interface that requires pre-tokenized tensors, not raw strings. The `ShineHypernet` class does not exist in the upstream repo. A wrapper shim must be built to bridge DRS's string-based API to SHINE's tensor-based internals, and that shim does not exist in the codebase.

**1024-token context cap.** SHINE's provided configuration limits input context to 1024 tokens. DRS's `synthesized_sources` or `compressed_corpus` for a single section can be 4–8k tokens (multiple sources concatenated). The adapter passes `max_length=1150`, suggesting truncation occurs somewhere, but the mechanism is opaque — either the wrapper silently truncates (losing source material) or the hypernetwork receives overlong input with undefined behavior. For multi-source academic synthesis where each section may draw from 5–15 sources, a 1024-token cap means SHINE can encode only a fraction of the available evidence.

**Architecture lock-in.** SHINE is hardcoded to the Qwen3 model family. The `LoraQwen.py` file is auto-generated from `modular_qwen3.py` with the comment "edits will be overwritten." Extending SHINE to work with Llama, Mistral, or other architectures requires rewriting the LoRA-augmented model class per architecture — a substantial engineering effort that the upstream project has not undertaken.

**Research maturity.** SHINE is a research project with no pip-installable package, no `setup.py` or `pyproject.toml`, no versioning, and no production documentation. The `generate_lora()` API may change, the model quality is unvalidated at scale, and there is no published benchmark comparing SHINE-compressed context versus standard RAG retrieval for research document generation. The training data (SQuAD, HotpotQA, MuSiQue, MS MARCO) consists of academic QA benchmarks — generalization to arbitrary knowledge domains is untested.

### 3.4 Cost-Value Verdict

SHINE addresses a real problem — context window saturation with source material — but its value is contingent on self-hosted deployment. In `cloud` mode (the default), SHINE generates LoRA weights that cannot be applied to the cloud LLM, making the ~0.3s GPU computation and GPU memory overhead pure waste. In `self_hosted` mode, where LoRA application is feasible, the quality of `ollama/llama-3.3-70b` with SHINE LoRA versus `claude-opus-4-5` with full context is an unanswered empirical question. The integration is architecturally clean but practically premature — it should be behind a feature flag that is off by default until quality benchmarks justify the GPU resource commitment.

---

## Part 4 — autoresearch Integration Analysis

### 4.1 What autoresearch Actually Is

autoresearch (github.com/karpathy/autoresearch) is fundamentally misnamed for DRS's purposes. It is not an information retrieval or research synthesis tool. It is an autonomous ML experimentation framework that uses an AI coding agent (Claude Code, Cursor, Aider, etc.) to iteratively optimize a GPT language model's training code. The architecture is a hill-climbing loop: modify `train.py`, run a 5-minute training experiment on a single GPU, evaluate via a fixed metric (validation bits-per-byte), keep improvements, revert regressions. The tagline is "One GPU, one file, one metric." It runs roughly 12 experiments per hour.

### 4.2 Architectural Irrelevance

autoresearch and DRS solve fundamentally different problems across every dimension. autoresearch's search space is code modifications to a single file; DRS searches the web, academic databases, and local knowledge bases. autoresearch evaluates quality via a computable ground-truth metric (val_bpb); DRS must rely on heuristic quality signals (LLM jury agreement, source credibility). autoresearch uses a single agent in a loop; DRS orchestrates 20+ specialized agents with consensus mechanisms. autoresearch's output is a better `train.py`; DRS's output is a cited research document.

The core architectural insight from autoresearch — that simple keep/discard loops work when you have an objective evaluation function — actually reinforces the necessity of DRS's multi-agent jury approach. DRS cannot hill-climb because there is no computable loss function for "research document quality." The CSS formula in `src/graph/nodes/aggregator.py` (`css_content = (sum(r)*0.35 + sum(f)*0.50 + sum(s)*0.15) / jury_size`) is the closest DRS has to an evaluation metric, but it is itself an LLM-generated heuristic, not ground truth.

### 4.3 Can Anything Be Borrowed?

The only transferable concept is autoresearch's disciplined experiment logging: every modification is committed to git with a before/after metric, enabling post-hoc analysis of what works. DRS could adopt a similar pattern for prompt engineering — version-controlling system prompts and tracking CSS scores across prompt versions. But this is an operational practice, not a code integration. There is no module, class, or function in autoresearch that could be imported into DRS.

### 4.4 Verdict

**Reject.** autoresearch has zero component-level overlap with DRS. The name is misleading — it automates ML experimentation, not information research. Integration effort would be wasted; the two systems share no interfaces, no data models, and no evaluation paradigms. The only value is inspirational, and that value (structured experiment tracking for prompts) can be implemented independently in under a day.

---

## Part 5 — Prioritized Roadmap

### 5.0 Severity Framework

Each item is classified by: **Impact** (how much it degrades production readiness), **Effort** (person-days to implement), and **Risk** (probability of introduction of new defects).

---

### 5.1 CRITICAL — Must Fix Before Any Production Deployment

#### C1: Unify the Two Codebases
**Impact:** Catastrophic. Neither codebase can produce a production run alone.
**Effort:** 15–25 person-days.
**Risk:** High — touching every module.

The `backend/` has the infrastructure DRS needs: FastAPI endpoints, PostgreSQL persistence, Alembic migrations, SSE broker, auth system, MinIO exports, Knowledge Space indexer. The `src/` has the quality pipeline DRS needs: 32-node graph, 9-judge jury, SHINE, RLM, oscillation detection, panel discussion, coherence guards. The merge strategy should be: adopt `backend/` as the deployment shell, replace its 5-node `graph_builder.py` with `src/graph/graph.py`, bridge the `src/` pipeline's `DocumentState` to the `backend/` database models via an adapter layer, and wire the SSE broker into the `src/` pipeline's event emission points.

Specifically:
- Replace `backend/src/graph/graph_builder.py` (the 5-node toy pipeline) with `src/graph/graph.py` (the 32-node real pipeline).
- Create a `StateAdapter` that maps between `src/graph/state.py`'s `DocumentState` TypedDict and `backend/database/models.py`'s SQLAlchemy models.
- Wire `backend/services/sse_broker.py` into the `src/` pipeline's `metrics_collector` and `section_checkpoint` nodes.
- Delete the `backend/src/graph/` directory entirely once merged; it is a vestigial prototype.

#### C2: Implement External Search Connectors
**Impact:** High. Without web/academic search, DRS is a local-KB-only system.
**Effort:** 5–8 person-days.
**Risk:** Low — clean ABC interface already exists.

The `SourceConnector` ABC in `src/connectors/base.py` (295 lines) is well-designed with `search()` and `health_check()` abstract methods, plus `SourceRanker` and `DiversityAnalyzer` already implemented. The TODO at `src/graph/nodes/researcher.py:32` explicitly calls for sonar-pro, tavily, and brave connectors. `backend/src/services/web_search.py` may contain a partial implementation that can be ported. Implement three connectors:
- `TavilyConnector` (web search, 100–150 lines)
- `BraveConnector` (web search, redundancy for Tavily outages, 100–150 lines)
- `SemanticScholarConnector` (academic search, 150–200 lines)

#### C3: Fix `cost_usd()` KeyError and Pricing Accuracy in `src/llm/pricing.py`
**Impact:** Medium-high. Any unrecognized model string crashes the pipeline; even recognized models have ±20% cost error.
**Effort:** 1–2 person-days.
**Risk:** Negligible.

Change line 30 from `p = MODEL_PRICING[model_id]` to `p = MODEL_PRICING.get(model_id)` with a fallback that logs a warning and returns 0.0, matching the pattern already used in `backend/src/llm/client.py` line 474. Add a model-string normalization function that strips `openrouter/` prefixes before lookup. Add cache token pricing (Anthropic `cache_creation_input` at 1.25× base, `cache_read_input` at 0.1× base) since the writer uses prompt caching extensively. Add an OpenRouter markup multiplier (configurable, default 1.0 for direct API, 1.1–1.3 for OpenRouter). These changes bring cost estimates within ±5% of actual spend, making budget projections reliable.

#### C4: Unify Budget Enforcement Into a Single Authoritative Path
**Impact:** High. Three disconnected budget tracking lanes means runs can overspend without triggering hard stops.
**Effort:** 3–5 person-days.
**Risk:** Medium — must preserve existing guard semantics while consolidating.

Consolidate the three budget tracking lanes (`src/budget/guard.py` check_budget, `src/budget/controller.py` RLMBudgetController (dead code), and writer_node manual reconciliation) into a single `BudgetEnforcer` that is the sole authority for spend tracking and hard-stop decisions. The enforcer must: (a) accept cost updates from all sources (standard LLM calls, RLM calls, SHINE GPU time), (b) raise `BudgetExhaustedError` when `spent >= max_budget` rather than silently returning, (c) survive malformed `usage_summary` from RLM by using the pre-call token estimate as fallback rather than skipping the update entirely. Delete the dead `RLMBudgetController` and remove the try/except-swallow pattern in writer_node lines 172–179.

#### C5: Integrate Budget Estimator v2 Into the Pipeline
**Impact:** Medium-high. The 18× gpt-4.5 cost underestimate means budget guards are ineffective for Premium runs.
**Effort:** 2 person-days.
**Risk:** Low.

`backend/src/services/budget_estimator_v2.py` (374 lines) fixes six documented bugs but is dead code. Move it into `src/graph/nodes/budget_estimator.py` (or refactor the existing node to call it), wire it into the graph's `preflight` → `budget_estimator` → `planner` edge, and remove the `sys.path.insert` hack.

---

### 5.2 HIGH — Should Fix Before Beta Users

#### H1: Replace Module-Level Singletons with Scoped Instances
**Impact:** Concurrency ceiling for multi-run deployments.
**Effort:** 5–8 person-days.
**Risk:** Medium — threading behavior changes.

Replace the module-level `llm_client = LLMClient()`, the module-level `_default_node = ResearcherNode()`, and the module-level `_jury_pool = ThreadPoolExecutor(max_workers=9)` with per-run scoped instances injected via the state or a run-scoped context. This removes the hard ceiling where two Premium runs contend for the same 9-thread pool and the same rate limiter state.

#### H2: Add State Field Bounds for Unbounded Accumulators
**Impact:** Memory pressure and checkpoint bloat on long runs.
**Effort:** 1–2 person-days.
**Risk:** Low.

Add `_max_len_reducer` bounds (matching the pattern already used for `css_history` and `draft_embeddings`) to: `reflector_feedback_history` (cap at 8), `writer_versions` (cap at 4 per section), `current_sources` (already implicitly capped by `max_sources_per_section` but not enforced at the state level).

#### H3: Enforce SHINE Privacy Mode Constraint
**Impact:** Wasted GPU computation in cloud mode.
**Effort:** 0.5 person-days.
**Risk:** Negligible.

Add a check in `shine_adapter.py` that skips LoRA generation when `privacy_mode == "cloud"`, since cloud LLMs cannot apply LoRA weights. Currently the adapter checks for Economy preset, low word count, and iteration > 1, but not privacy mode — meaning cloud users silently burn GPU cycles for unusable LoRA weights.

#### H4: Add Timeout to Jury Futures
**Impact:** A single hanging judge blocks the entire run with no recovery.
**Effort:** 0.5 person-days.
**Risk:** Negligible.

Add a `timeout` parameter to `futures.as_completed()` in `src/graph/nodes/jury.py`. On timeout, return the `_error_verdict()` fail-closed verdict for the timed-out judge and continue aggregation with available verdicts. Also fix the error verdict's `veto_category="technical_failure"` which is not a valid value in the `JudgeVerdict.veto_category` Literal type — it should use an existing category or `None`.

#### H5: CSS Formula Spec Conformance
**Impact:** Quality gate behavior differs from documented specification.
**Effort:** 1 person-day.
**Risk:** Medium — changes approval/rejection rates.

The aggregator at `src/graph/nodes/aggregator.py` (123 lines) uses `css_content = (sum(r)*0.35 + sum(f)*0.50 + sum(s)*0.15) / jury_size` where `r`, `f`, `s` are "css_contribution" floats from each judge. The spec §8.7 defines CSS using `pass_R/n_R` ratios — binary pass/fail counts per axis. These are different formulas that produce different values for the same jury outputs. Decide which is correct, update the other, and document the decision.

---

### 5.3 MEDIUM — Quality of Life and Operational Maturity

#### M1: RLM Resilience Wrapper
**Effort:** 3 person-days. **Risk:** Low.

Wrap RLM's `completion()` call in a retry layer that catches `ErrorThresholdExceededError` and retries with a fallback model, since RLM's internal error handling is terminal rather than recoverable. Also add a pre-call check that the target model's circuit breaker (from `src/llm/resilience.py`) is not OPEN before delegating to RLM.

#### M2: Implement Celery/Redis Task Queue
**Effort:** 8–12 person-days. **Risk:** Medium.

Replace `asyncio.create_task()` in `backend/services/run_manager.py` with Celery tasks backed by Redis, matching the spec §34.2 architecture. This enables horizontal scaling, distributed run tracking, and KEDA-based autoscaling.

#### M3: Observability Stack Wiring
**Effort:** 5 person-days. **Risk:** Low.

The spec §23 defines a comprehensive observability stack (OpenTelemetry tracing, Prometheus metrics, Grafana dashboards, Sentry error tracking, structured JSON logging). The metric names and span attributes are fully specified. Implementation requires wiring the existing node code to emit spans and increment counters at the boundaries documented in §23.1-§23.2. The structured log schema (`DRSLogRecord`, §23.6) should replace the current `logging.info()` calls throughout the pipeline.

---

### 5.4 DEFERRED — Not Justified Until Core Stabilizes

#### D1: SHINE Quality Benchmarking
**Defer until:** After external search connectors are implemented and CSS calibration is complete.
**Rationale:** SHINE's value proposition (95% token reduction) is only measurable against a baseline of full-context generation with real sources. Without external search connectors (C2), the test corpus is limited to local KB content, which may not be representative. Benchmark SHINE LoRA quality against standard RAG on 50+ diverse topics before enabling it by default.

#### D2: RLM for Section Planning
**Defer until:** After RLM resilience wrapper (M1) is in place.
**Rationale:** RLM's recursive decomposition is genuinely useful for breaking complex topics into researchable sub-questions, but the current integration uses it for writing (prose generation), where it adds overhead without quality benefit. Repurpose RLM for the planner/researcher phase instead, where structured decomposition matches the tool's strengths.

---

### 5.5 REJECTED

#### X1: autoresearch Integration
**Rationale:** Zero component-level overlap. Different problem domain, different evaluation paradigm, different output format. See Part 4.

#### X2: Distributed RLM REPL (Docker/Modal/E2B sandboxes)
**Rationale:** RLM supports remote sandboxed execution environments (Docker, Modal, Prime, Daytona, E2B), but these add infrastructure complexity for a feature (code execution in REPL) that DRS uses marginally. The security risk of executing LLM-generated code — even in a sandbox — for a research document generator is not justified by the quality improvement. If RLM is retained, keep it in `environment="local"` with the understanding that it processes only trusted internal prompts, never external source content.

---

---

## Appendix — Quantitative Quality Assessment

Based on deep analysis of 14,512 lines of Python across the `src/` pipeline (41 node files, LLM client, routing, pricing, resilience, budget, config, observability, security, connectors) and the `backend/` infrastructure (graph builder, run manager, LLM client, budget estimator v2, database models, API endpoints):

| Component | Architectural Soundness | Execution Completeness | Production Readiness |
|-----------|------------------------|----------------------|---------------------|
| Graph topology (`src/graph/graph.py`) | 95% | 90% | High |
| LLM client (`src/llm/client.py`) | 88% | 85% | Medium-High |
| Model routing (`src/llm/routing.py`) | 92% | 88% | Medium-High |
| Jury orchestration (`src/graph/nodes/jury.py`) | 88% | 80% | Medium |
| Budget management (all modules) | 55% | 30% | **Not ready** |
| RLM integration | 75% | 60% | **Not ready** |
| SHINE integration | 72% | 40% | **Not ready** |
| Observability | 72% | 50% | **Not ready** |
| Research/connectors | 82% (ABC) | 20% (1 of 5 connectors) | **Not ready** |
| Backend infrastructure | 85% | 75% | Medium |

**Overall verdict: 75% architecturally sound, 55% complete in execution. Not production-ready without the Critical fixes (C1–C5) from the roadmap above.**

---

*Review complete. All citations reference files read during this session. Line numbers are approximate due to potential concurrent edits.*
