# 📅 DRS Development Plan — Updated 2026-02-23

> **Status:** 75% Complete — MVP Achievable in 5-7 Days  
> **Branch:** `struct`  
> **Last Gap Analysis:** 2026-02-23 15:00 CET  

---

## 📊 Executive Summary

### Current State

**What's Done (75%):**
- ✅ Graph topology: 32 nodes + 11 routers fully connected
- ✅ State schema: Complete with RAG + SHINE fields
- ✅ RAG infrastructure: Memvid connector + local knowledge priority
- ✅ SHINE integration: Parametric compression with fallback
- ✅ 25 nodes implemented (see breakdown below)
- ✅ 10 data connectors (academic, institutional, web, upload)
- ✅ Jury system: 9 judges + aggregator + CSS formula
- ✅ Iteration loop: Reflector + linters + oscillation detector
- ✅ Budget controller: Real-time tracking + alarms

**What's Missing (25%):**
- ❌ 7 stub nodes (currently pass-through no-ops)
- ❌ End-to-end integration tests
- ❌ Production deployment configs

### The 7 Critical Stub Nodes

These nodes are **registered in graph.py** but implemented as empty stubs:

| Node | File | Priority | Effort | Blocking |
|------|------|----------|--------|----------|
| `preflight` | `nodes/preflight.py` | 🔴 CRITICAL | 1 day | Entry point |
| `budget_estimator` | `nodes/budget_estimator.py` | 🔴 CRITICAL | 1 day | Pre-flight |
| `await_outline` | `nodes/await_outline.py` | 🔴 CRITICAL | 0.5 day | Approval gate |
| `post_draft_analyzer` | `nodes/post_draft_analyzer.py` | 🟡 HIGH | 1 day | Iteration support |
| `metrics_collector` | `nodes/metrics_collector.py` | 🟡 HIGH | 0.5 day | Oscillation detector |
| `await_human` | `nodes/await_human.py` | 🟢 MEDIUM | 0.5 day | Escalation gate |
| `feedback_collector` | `nodes/feedback_collector.py` | 🟢 LOW | 0.5 day | Post-delivery |

**Total effort:** 5 days (with parallelization possible)

---

## 🎯 Mission: Complete MVP in 7 Days

**Goal:** Implement 7 stub nodes → Achieve end-to-end functionality (topic → approved section)

**Success Criteria:**
1. ✅ User provides topic → System outputs 1 approved section
2. ✅ All nodes execute (no more stubs)
3. ✅ Graph compiles without errors
4. ✅ Tests pass for each new node
5. ✅ Budget tracking accurate within ±20%

---

## 🗃️ 7-Day Implementation Schedule

### **Day 1-2: Critical Path (Entry/Exit Points)**

**Focus:** Enable graph to start and initialize state properly.

#### Day 1 Morning: Preflight Node
**Task:** Implement `src/graph/nodes/preflight.py`

**Specs:** `docs/04_architecture.md` §4.2

**Deliverables:**
- [ ] Input validation (topic, target_words, max_budget)
- [ ] Security sanitization (prevent injection)
- [ ] Preset loading (Economy/Balanced/Premium)
- [ ] DocumentState initialization
- [ ] Unit test: `tests/unit/test_preflight.py`

**Acceptance:**
```bash
pytest tests/unit/test_preflight.py -v
# Expected: Valid input → initialized state, invalid → ValueError
```

**Effort:** 4 hours

---

#### Day 1 Afternoon: Budget Estimator
**Task:** Implement `src/graph/nodes/budget_estimator.py`

**Specs:** `docs/19_budget_controller.md` §19.1

**Deliverables:**
- [ ] Cost estimation formula (tokens × pricing)
- [ ] Section count estimation
- [ ] Budget alert (if >90% projected)
- [ ] Unit test: `tests/unit/test_budget_estimator.py`

**Formula:**
```python
estimated_sections = target_words / avg_section_words
tokens_per_section = research + writer + jury  # Preset-dependent
total_cost = (tokens_per_section * sections * iterations) / 1000 * model_price
```

**Effort:** 3 hours

---

#### Day 2 Morning: Await Outline
**Task:** Implement `src/graph/nodes/await_outline.py`

**Specs:** `docs/04_architecture.md` §4.2

**Deliverables:**
- [ ] MVP: Auto-approve outline (no human loop)
- [ ] Future: Interrupt for human approval (commented out)
- [ ] Unit test: `tests/unit/test_await_outline.py`

**Implementation:**
```python
def await_outline_node(state):
    # MVP: Auto-approve
    return {"outline_approved": True, "total_sections": len(state["outline"])}
```

**Effort:** 2 hours

---

#### Day 2 Afternoon: Integration Check
**Task:** Verify graph compiles with new nodes

**Steps:**
1. Update `src/graph/graph.py` to use real implementations
2. Run: `python -c "from src.graph.graph import build_graph; build_graph()"`
3. Fix import errors
4. Test entry flow: `preflight → budget_estimator → planner → await_outline`

**Deliverable:**
```bash
pytest tests/integration/test_phase_a.py -v
# Expected: Input → approved outline (no crashes)
```

**Effort:** 2 hours

---

### **Day 3-4: Iteration Support Nodes**

**Focus:** Enable draft improvement loop (post-jury feedback).

#### Day 3 Morning: Post Draft Analyzer
**Task:** Implement `src/graph/nodes/post_draft_analyzer.py`

**Specs:** `docs/05_agents.md` §5.11

**Deliverables:**
- [ ] Gap detection (missing citations, vague claims)
- [ ] LLM-based analysis (Gemini 2.5 Pro)
- [ ] Output: list of research queries for targeted search
- [ ] Router update: `post_draft_gap.py` (gap vs no_gap)
- [ ] Unit test: `tests/unit/test_post_draft_analyzer.py`

**Logic:**
- Run only on iteration 1 (skip on retries)
- If gaps found → route to `researcher_targeted`
- If no gaps → proceed to `style_linter`

**Effort:** 4 hours

---

#### Day 3 Afternoon: Metrics Collector
**Task:** Implement `src/graph/nodes/metrics_collector.py`

**Specs:** `docs/05_agents.md` §5.8

**Deliverables:**
- [ ] Word count extraction
- [ ] Citation count extraction
- [ ] Draft embedding (bge-m3) for oscillation detection
- [ ] Bounded state update (keep last 4 embeddings)
- [ ] Unit test: `tests/unit/test_metrics_collector.py`

**Integration:**
- Used by `oscillation_check` node (already implemented)
- Embeddings compared via cosine similarity

**Effort:** 3 hours

---

#### Day 4: Integration Testing
**Task:** Test iteration loop end-to-end

**Test Case:**
```python
# Draft → Jury (fail) → Reflector → PostDraftAnalyzer → ResearcherTargeted → Writer (v2)
def test_iteration_loop():
    state = {...}  # Mock state with failed draft
    result = graph.invoke(state)
    assert result["current_iteration"] == 2
    assert len(result["post_draft_gaps"]) > 0
```

**Deliverable:**
```bash
pytest tests/integration/test_iteration_loop.py -v
```

**Effort:** 4 hours

---

### **Day 5-6: Human-in-Loop & Polish**

**Focus:** Implement escalation gates and finalize MVP.

#### Day 5 Morning: Await Human Node
**Task:** Implement `src/graph/nodes/await_human.py`

**Specs:** `docs/04_architecture.md` §4.3

**Deliverables:**
- [ ] Interrupt mechanism (LangGraph `raise Interrupt`)
- [ ] Escalation context (veto, conflict, etc.)
- [ ] Unit test: `tests/unit/test_await_human.py`

**Implementation:**
```python
from langgraph.checkpoint import Interrupt

def await_human_node(state):
    escalation = state["active_escalation"]
    raise Interrupt(value={"message": f"Approval needed: {escalation['type']}"})
```

**Effort:** 2 hours

---

#### Day 5 Afternoon: Feedback Collector
**Task:** Implement `src/graph/nodes/feedback_collector.py`

**Specs:** `docs/05_agents.md` §5.20

**Deliverables:**
- [ ] MVP: Log "feedback pending" (no-op)
- [ ] Future: Send survey, track rating (commented out)
- [ ] Unit test: `tests/unit/test_feedback_collector.py`

**Implementation:**
```python
def feedback_collector_node(state):
    logger.info(f"Document {state['doc_id']} delivered. Feedback pending.")
    return {"status": "completed"}
```

**Effort:** 1 hour

---

#### Day 6: End-to-End MVP Test
**Task:** Full pipeline test (topic → approved section)

**Test Case:**
```python
def test_mvp_e2e():
    graph = build_graph()
    result = graph.invoke({
        "topic": "Impact of AI on education",
        "target_words": 5000,
        "quality_preset": "Balanced",
        "max_budget_dollars": 50.0
    })
    
    assert result["status"] == "completed"
    assert len(result["approved_sections"]) == 1
    assert result["budget"]["spent_dollars"] < 50.0
```

**Deliverable:**
```bash
pytest tests/integration/test_mvp_e2e.py -v --tb=short
```

**Effort:** Full day (6-8 hours with debugging)

---

### **Day 7: Bug Fixes & Documentation**

**Focus:** Stabilize MVP and document for handoff.

#### Morning: Bug Triage
**Tasks:**
- [ ] Fix any failures from Day 6 E2E test
- [ ] Handle edge cases (empty outline, budget exceeded)
- [ ] Improve error messages

#### Afternoon: Documentation
**Tasks:**
- [ ] Update `README.md` with "How to Run MVP"
- [ ] Add `TESTING.md` with test commands
- [ ] Update `CHANGELOG.md` with completed nodes
- [ ] Create `DEPLOYMENT.md` (production setup)

**Deliverable:**
```markdown
# README.md

## Quick Start (MVP)

```bash
# Install dependencies
pip install -r requirements.txt

# Build knowledge base (optional)
python scripts/build_memvid_kb.py --input docs/ --output drs_kb.mp4

# Run MVP
python -m src.cli run --topic "Your topic" --preset Balanced --budget 50
```
```

**Effort:** 4 hours

---

## 📑 Detailed Node Specifications

### 1. Preflight Node

**File:** `src/graph/nodes/preflight.py`

**Purpose:** Entry point. Validates input, initializes state.

**Inputs (from user):**
- `topic`: str (required)
- `target_words`: int (5000-50000, required)
- `quality_preset`: "Economy"|"Balanced"|"Premium" (required)
- `max_budget_dollars`: float (≤500, required)
- `style_profile`: str (optional, default from preset)

**Outputs (DocumentState updates):**
- `doc_id`: str (UUID)
- `status`: "initializing"
- `config`: dict (loaded from preset)
- `budget`: BudgetState (initialized)
- `outline`: [] (empty, populated later)
- All other DocumentState defaults

**Validation Rules:**
1. Topic: Non-empty, <500 chars, sanitized (no SQL injection)
2. Target words: 5000 ≤ value ≤ 50000
3. Budget: 0 < value ≤ 500
4. Preset: Must be in ["Economy", "Balanced", "Premium"]

**Error Handling:**
- Invalid input → `raise ValueError("Descriptive message")`
- Missing preset file → Fallback to "Balanced" + warning

**Dependencies:**
- `src/security/sanitizer.py`: `sanitize_user_input()`
- `src/config/presets.py`: `load_preset(quality_preset)`

**Testing:**
```python
# tests/unit/test_preflight.py

def test_preflight_valid_input():
    result = preflight_node({"topic": "AI", "target_words": 10000, ...})
    assert result["doc_id"] is not None
    assert result["status"] == "initializing"

def test_preflight_invalid_budget():
    with pytest.raises(ValueError, match="max_budget"):
        preflight_node({"max_budget_dollars": 600})
```

---

### 2. Budget Estimator Node

**File:** `src/graph/nodes/budget_estimator.py`

**Purpose:** Estimate total cost before starting work.

**Inputs (from state):**
- `target_words`: int
- `quality_preset`: str
- `budget.max_dollars`: float

**Outputs:**
- `budget.projected_final`: float (estimated cost)

**Estimation Formula:**

```python
# 1. Estimate sections
avg_section_words = {
    "<8000": 800,
    "<20000": 1200,
    ">20000": 1500
}[target_words]
estimated_sections = target_words / avg_section_words

# 2. Tokens per section (from §19.1 table)
tokens_per_section = {
    "Economy": 8000,   # Lighter models
    "Balanced": 15000,  # Mid-tier
    "Premium": 25000    # Heavy + MoW
}[quality_preset]

# 3. Average iterations
avg_iterations = {
    "Economy": 1.5,
    "Balanced": 2.0,
    "Premium": 2.5
}[quality_preset]

# 4. Total cost
total_tokens = estimated_sections * tokens_per_section * avg_iterations
estimated_cost = (total_tokens / 1000) * 0.01  # $0.01/1k baseline
estimated_cost *= 1.20  # Add 20% overhead
```

**Alert Logic:**
- If `estimated_cost > max_budget * 0.90` → Log warning
- If `estimated_cost > max_budget` → Suggest lower preset

**Testing:**
```python
def test_budget_estimator_balanced():
    state = {"target_words": 10000, "quality_preset": "Balanced", ...}
    result = budget_estimator_node(state)
    assert 0 < result["budget"]["projected_final"] < 100  # Reasonable range
```

---

### 3. Await Outline Node

**File:** `src/graph/nodes/await_outline.py`

**Purpose:** Human approval gate for outline (MVP: auto-approve).

**Inputs:**
- `outline`: list[OutlineSection]

**Outputs:**
- `outline_approved`: bool (True for MVP)
- `total_sections`: int

**MVP Implementation:**
```python
def await_outline_node(state):
    return {
        "outline_approved": True,
        "total_sections": len(state["outline"])
    }
```

**Future (Human-in-Loop):**
```python
from langgraph.checkpoint import Interrupt

def await_outline_node_with_human(state):
    if state.get("outline_approved"):  # User already approved
        return {"outline_approved": True}
    else:
        raise Interrupt(value={"message": "Outline approval needed", "outline": state["outline"]})
```

---

### 4. Post Draft Analyzer Node

**File:** `src/graph/nodes/post_draft_analyzer.py`

**Purpose:** Detect gaps/contradictions in draft. Trigger targeted research.

**Inputs:**
- `current_draft`: str
- `current_iteration`: int
- `outline[current_section_idx].scope`: str

**Outputs:**
- `post_draft_gaps`: list[dict] with structure:
  ```python
  {
      "type": "missing_citation" | "vague" | "contradiction",
      "claim": str,  # Problematic text
      "query": str   # Search query for researcher_targeted
  }
  ```
- `targeted_research_active`: bool

**Logic:**
1. **Skip if iteration > 1** (only analyze first draft)
2. Use LLM (Gemini 2.5 Pro) to identify:
   - Claims without citations
   - Vague statements ("many", "often", "significant")
   - Missing context
   - Internal contradictions
3. Generate search queries for each gap
4. If gaps found → route to `researcher_targeted`

**Prompt Template:**
```
Analyze this draft for knowledge gaps.

Section: {scope}
Draft: {draft}

Identify:
1. Claims without citations
2. Vague statements needing data
3. Missing context
4. Contradictions

Return JSON:
{
  "gaps": [
    {"type": "missing_citation", "claim": "...", "query": "..."}
  ]
}
```

**Router Integration:**
```python
# src/graph/routers/post_draft_gap.py
def route_post_draft_gap(state):
    if state.get("post_draft_gaps") and state["current_iteration"] == 1:
        return "gap"  # → researcher_targeted
    else:
        return "no_gap"  # → style_linter
```

---

### 5. Metrics Collector Node

**File:** `src/graph/nodes/metrics_collector.py`

**Purpose:** Compute draft metrics for oscillation detection.

**Inputs:**
- `current_draft`: str

**Outputs:**
- `word_count`: int
- `citations_used`: list[str]
- `draft_embeddings`: list (bounded to last 4)

**Implementation:**
```python
from FlagEmbedding import FlagModel
import re

_embedder = None  # Global lazy-loaded

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = FlagModel('BAAI/bge-m3', use_fp16=True)
    return _embedder

def metrics_collector_node(state):
    draft = state["current_draft"]
    
    # Word count
    word_count = len(draft.split())
    
    # Citation extraction
    citations_used = list(set(re.findall(r"\[(\w+)\]", draft)))
    
    # Embedding (for oscillation detection)
    embedder = get_embedder()
    embedding = embedder.encode(draft).tolist()
    
    return {
        "word_count": word_count,
        "citations_used": citations_used,
        "draft_embeddings": state.get("draft_embeddings", []) + [embedding]
    }
```

**Note:** `draft_embeddings` is bounded by §29.5 reducer (keeps last 4 only).

---

### 6. Await Human Node

**File:** `src/graph/nodes/await_human.py`

**Purpose:** Pause execution for human intervention (conflicts, vetos).

**Inputs:**
- `active_escalation`: dict with structure:
  ```python
  {
      "type": "veto" | "conflict" | "budget_exceeded",
      "details": {...},
      "options": [...]  # Possible resolutions
  }
  ```

**Outputs:**
- Interrupt (pauses execution)
- When resumed: state already has user's resolution

**Implementation:**
```python
from langgraph.checkpoint import Interrupt

def await_human_node(state):
    escalation = state.get("active_escalation", {})
    escalation_type = escalation.get("type", "unknown")
    
    logger.warning(f"Human intervention required: {escalation_type}")
    
    raise Interrupt(
        value={
            "message": f"Approval needed: {escalation_type}",
            "escalation": escalation
        }
    )
```

**Resume Flow:**
1. Graph pauses at interrupt
2. User provides input via API/CLI
3. State updated with user decision
4. Graph resumes from next node

---

### 7. Feedback Collector Node

**File:** `src/graph/nodes/feedback_collector.py`

**Purpose:** Collect post-delivery feedback (optional).

**Inputs:**
- `doc_id`: str
- `approved_sections`: list

**Outputs:**
- `status`: "completed"

**MVP Implementation:**
```python
def feedback_collector_node(state):
    doc_id = state["doc_id"]
    logger.info(f"Document {doc_id} delivered. Feedback pending.")
    return {"status": "completed"}
```

**Future (Full Implementation):**
```python
def feedback_collector_node(state):
    doc_id = state["doc_id"]
    user_id = state["user_id"]
    
    # Send survey email
    send_feedback_survey(user_id, doc_id)
    
    # Track in database
    db.feedback.insert({
        "doc_id": doc_id,
        "timestamp": datetime.now(),
        "status": "pending"
    })
    
    return {"status": "completed"}
```

---

## 🧰 Testing Strategy

### Unit Tests (Day 1-5)

Each node gets isolated test:

```bash
tests/unit/
├── test_preflight.py
├── test_budget_estimator.py
├── test_await_outline.py
├── test_post_draft_analyzer.py
├── test_metrics_collector.py
├── test_await_human.py
└── test_feedback_collector.py
```

**Pattern:**
```python
import pytest
from unittest.mock import patch
from src.graph.nodes.preflight import preflight_node

def test_preflight_valid():
    state = {"topic": "AI", "target_words": 10000, ...}
    result = preflight_node(state)
    assert "doc_id" in result
    assert result["status"] == "initializing"

def test_preflight_invalid_budget():
    with pytest.raises(ValueError):
        preflight_node({"max_budget_dollars": 600})
```

### Integration Tests (Day 4, 6)

**Phase A Test (Entry Flow):**
```python
# tests/integration/test_phase_a.py

def test_phase_a_initialization():
    graph = build_graph()
    result = graph.invoke({
        "topic": "Test",
        "target_words": 5000,
        "quality_preset": "Balanced",
        "max_budget_dollars": 50.0
    })
    
    assert result["outline_approved"] is True
    assert len(result["outline"]) > 0
```

**MVP E2E Test (Full Pipeline):**
```python
# tests/integration/test_mvp_e2e.py

def test_mvp_single_section():
    graph = build_graph()
    result = graph.invoke({...})
    
    assert result["status"] == "completed"
    assert len(result["approved_sections"]) >= 1
    assert result["budget"]["spent_dollars"] < result["budget"]["max_dollars"]
```

### Performance Tests (Day 7)

**Benchmarks:**
```python
import time

def test_single_section_latency():
    start = time.time()
    graph.invoke({...})
    elapsed = time.time() - start
    
    assert elapsed < 120  # <2 minutes
```

---

## 🔧 Developer Workflow

### Daily Routine

**Morning (Start of Day):**
1. Pull latest changes: `git pull origin struct`
2. Check task for the day in schedule above
3. Read relevant spec section (e.g., §4.2 for Preflight)
4. Create feature branch: `git checkout -b feat/preflight-node`

**During Development:**
1. Write node implementation
2. Write unit test
3. Run test: `pytest tests/unit/test_[node].py -v`
4. Fix failures
5. Commit: `git commit -m "feat(preflight): implement state initialization"`

**End of Day:**
1. Push branch: `git push origin feat/preflight-node`
2. Open PR to `struct` branch
3. Update `DEVELOPMENT_PLAN.md` with progress
4. Document blockers/questions

---

## 🚨 Common Issues & Solutions

### Issue 1: Import Errors
**Symptom:** `ModuleNotFoundError: No module named 'src'`

**Solution:**
```bash
# Add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use -m flag
python -m pytest tests/unit/test_preflight.py
```

---

### Issue 2: LLM Call Failures
**Symptom:** `APIError: Rate limit exceeded`

**Solution:**
```python
# Add retry logic
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential())
def call_llm_with_retry(...):
    return llm_client.call(...)
```

---

### Issue 3: State Mutation Errors
**Symptom:** `TypeError: 'DocumentState' object does not support item assignment`

**Solution:**
```python
# DON'T mutate state directly
state["key"] = value  # ❌ Wrong

# DO return updates dict
return {"key": value}  # ✅ Correct
```

---

### Issue 4: Graph Compilation Errors
**Symptom:** `ValueError: Node 'preflight' not found`

**Solution:**
```python
# Check graph.py _REAL_NODES dict
_REAL_NODES = {
    "preflight": preflight_node,  # ← Must import first
    ...
}
```

---

## 📚 Key References

### Specs to Read

| Task | Read First | Read Second |
|------|-----------|-------------|
| Preflight | `04_architecture.md` §4.2 | `19_budget_controller.md` §19.1 |
| Budget Estimator | `19_budget_controller.md` §19.1 | `28_llm_assignments.md` (pricing) |
| Await Outline | `04_architecture.md` §4.2 | - |
| Post Draft Analyzer | `05_agents.md` §5.11 | `04_architecture.md` §4.4 |
| Metrics Collector | `05_agents.md` §5.8 | `29_performance_optimizations.md` §29.5 |
| Await Human | `04_architecture.md` §4.3 | - |
| Feedback Collector | `05_agents.md` §5.20 | - |

### Code to Study

**Before implementing Preflight:**
- Read: `src/graph/nodes/planner.py` (similar input validation)
- Read: `src/config/presets.py` (preset loading)

**Before implementing Post Draft Analyzer:**
- Read: `src/graph/nodes/reflector.py` (similar feedback analysis)
- Read: `src/graph/routers/post_draft_gap.py` (routing logic)

**Before implementing Metrics Collector:**
- Read: `src/graph/nodes/oscillation_check.py` (embedding usage)
- Read: `src/graph/state.py` (bounded reducers)

---

## 🏁 Definition of Done

### Per-Node Checklist

- [ ] Implementation complete (no `pass` or `return {}`)
- [ ] Docstring with purpose + specs reference
- [ ] Type hints for inputs/outputs
- [ ] Error handling (try/except for LLM calls)
- [ ] Logging (info for success, warning for issues)
- [ ] Unit test passing
- [ ] Integrated in `graph.py` _REAL_NODES
- [ ] No import errors

### MVP Completion Checklist

- [ ] All 7 stub nodes implemented
- [ ] Graph compiles: `python -c "from src.graph.graph import build_graph; build_graph()"`
- [ ] Unit tests pass: `pytest tests/unit/ -v`
- [ ] Integration tests pass: `pytest tests/integration/ -v`
- [ ] E2E test passes: `pytest tests/integration/test_mvp_e2e.py -v`
- [ ] Documentation updated:
  - [ ] `README.md` (how to run)
  - [ ] `TESTING.md` (test commands)
  - [ ] `CHANGELOG.md` (completed features)
- [ ] No stub warnings in logs

---

## 🚀 Beyond MVP (Future Phases)

**After completing 7 nodes, next priorities:**

### Week 2: Advanced Features
- [ ] MoW (Mixture-of-Writers) implementation
- [ ] Panel Discussion (CSS < 0.50 fallback)
- [ ] Coherence Guard (cross-section conflicts)
- [ ] §29.3 Model Tiering (cost optimization)

### Week 3: Production Readiness
- [ ] PostgreSQL + S3 deployment
- [ ] Monitoring (Prometheus + Grafana)
- [ ] API endpoint (FastAPI)
- [ ] CLI improvements

### Week 4: Scale & Optimize
- [ ] Kubernetes deployment
- [ ] Load testing (10 concurrent requests)
- [ ] Cost optimization (§29 full implementation)
- [ ] UI (React + WebSocket for live updates)

---

## 📌 Summary

**Current Status:** 75% Complete (25 nodes done, 7 stubs remaining)

**7-Day Plan:**
- Day 1-2: Entry/exit nodes (preflight, budget, await_outline)
- Day 3-4: Iteration support (post_draft_analyzer, metrics_collector)
- Day 5-6: Human-in-loop + E2E testing
- Day 7: Bug fixes + documentation

**Success Metric:** Topic → Approved Section (end-to-end working)

**Effort:** 5 days implementation + 2 days testing/polish = **7 days total**

---

**Ready to start? Begin with Day 1 Morning: Preflight Node! 🚀**
