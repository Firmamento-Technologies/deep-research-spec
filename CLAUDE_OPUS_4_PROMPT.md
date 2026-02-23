# 🤖 Claude Opus 4 Development Prompt — DRS Implementation

> **Target Model:** Claude Opus 4 (Anthropic)  
> **Context:** Deep Research System (DRS) v3.0 implementation  
> **Repository:** [lucadidomenicodopehubs/deep-research-spec](https://github.com/lucadidomenicodopehubs/deep-research-spec)  
> **Branch:** `struct`  
> **Last Updated:** 2026-02-23  

---

## 📊 Current Implementation Status (75% Complete)

You are joining an **advanced stage** of DRS development. The codebase is **NOT empty** — significant infrastructure already exists.

### ✅ What's Already Implemented

```
src/
├── llm/
│   ├── client.py           ✅ Unified LLM client with Anthropic/OpenAI support
│   └── pricing.py          ✅ MODEL_PRICING table (§28.4)
├── graph/
│   ├── state.py            ✅ DocumentState TypedDict (complete with RAG+SHINE fields)
│   ├── graph.py            ✅ LangGraph topology (32 nodes, 11 routers)
│   ├── nodes/              ✅ 25 nodes implemented (see breakdown below)
│   └── routers/            ✅ 11 conditional routers implemented
├── connectors/             ✅ 10 data source connectors
│   ├── memvid_connector.py     ✅ Local RAG (Memvid)
│   ├── academic.py             ✅ ArXiv, Semantic Scholar
│   ├── institutional.py        ✅ Gov, WHO, UN sources
│   ├── web_general.py          ✅ Sonar-pro, Tavily, Brave
│   ├── user_upload.py          ✅ PDF/DOCX processing
│   └── ...                     ✅ 5 more connectors
├── budget/                 ✅ Budget tracking system
├── config/                 ✅ Configuration management
├── models/                 ✅ TypedDict definitions
├── security/               ✅ Input sanitization
├── storage/                ✅ PostgreSQL + S3 interfaces
└── shine/                  ✅ SHINE integration wrapper

tests/
├── test_memvid_connector.py    ✅ RAG tests
├── test_shine_adapter.py       ✅ SHINE tests
├── test_rag_fallback.py        ✅ Fallback tests
└── test_rag_shine_e2e.py       ✅ End-to-end tests
```

### ✅ Implemented Nodes (25 out of 32)

| Node | Status | Implementation Quality |
|------|--------|----------------------|
| **Phase 0: RAG + SHINE** | | |
| `shine_adapter` | ✅ 5.6KB | Parametric compression with fallback |
| **Phase 1: MVP Pipeline** | | |
| `planner` | ✅ 4.7KB | Outline generation |
| `researcher` | ✅ 4.7KB | Multi-source research with memvid priority |
| `researcher_targeted` | ✅ 3.4KB | Gap-driven research |
| `citation_manager` | ✅ 4.5KB | Citation extraction |
| `citation_verifier` | ✅ 4.8KB | HTTP + NLI verification |
| `source_sanitizer` | ✅ 2.4KB | Ghost source removal |
| `source_synthesizer` | ✅ 4.2KB | Corpus creation |
| `context_compressor` | ✅ 10.5KB | Tiered compression |
| `writer` | ✅ 6.7KB | Draft generation with SHINE support |
| `section_checkpoint` | ✅ 17.8KB | PostgreSQL persistence |
| `budget_controller` | ✅ 8.7KB | Cost tracking |
| **Phase 2: Jury System** | | |
| `jury_base` | ✅ 3.3KB | Abstract judge class |
| `judge_r` | ✅ 2.3KB | Reasoning judges (R1-R3) |
| `judge_f` | ✅ 4.5KB | Factual judges (F1-F3) |
| `judge_s` | ✅ 2.6KB | Style judges (S1-S3) |
| `jury` | ✅ 4.4KB | Parallel orchestration |
| `jury_mock` | ✅ 1.3KB | MVP fallback |
| `aggregator` | ✅ 4.3KB | CSS computation |
| **Phase 3: Iteration Loop** | | |
| `reflector` | ✅ 6.5KB | Feedback synthesis |
| `style_linter` | ✅ 4.8KB | L1/L2 violation detection |
| `style_fixer` | ✅ 3.6KB | Auto-correction |
| `oscillation_check` | ✅ 4.7KB | CSS/semantic oscillation detector |

### ❌ Missing Critical Nodes (7 stubs)

These nodes are **registered in graph.py** but implemented as **pass-through stubs**:

```python
# Current stub implementation (src/graph/graph.py lines 68-76)
def _make_stub(name: str):
    def _stub(state: dict) -> dict:
        return {}  # ← No-op placeholder
    return _stub
```

**Your task is to replace these 7 stubs with real implementations:**

| Stub Node | File | Priority | Specs Reference |
|-----------|------|----------|----------------|
| `preflight` | `nodes/preflight.py` | 🔴 CRITICAL | §4.2, §19.1 |
| `budget_estimator` | `nodes/budget_estimator.py` | 🔴 CRITICAL | §19.1 |
| `await_outline` | `nodes/await_outline.py` | 🔴 CRITICAL | §4.2 |
| `post_draft_analyzer` | `nodes/post_draft_analyzer.py` | 🟡 HIGH | §5.11 |
| `metrics_collector` | `nodes/metrics_collector.py` | 🟡 HIGH | §5.8 |
| `await_human` | `nodes/await_human.py` | 🟢 MEDIUM | §4.3 |
| `feedback_collector` | `nodes/feedback_collector.py` | 🟢 LOW | §5.20 |

---

## 🎯 Your Mission: Complete MVP in 5-7 Days

**Goal:** Implement the 7 missing stub nodes to achieve **end-to-end MVP** functionality.

**Success Criteria:**
- ✅ User provides topic → System outputs approved 1st section
- ✅ All nodes execute (no more stubs)
- ✅ Graph compiles without errors
- ✅ Tests pass for each new node

---

## 📋 Implementation Roadmap

### **Day 1-2: Critical Path Nodes (Entry/Exit)**

#### Task 1.1: Implement Preflight Node
**File:** `src/graph/nodes/preflight.py` (CREATE NEW)

**Purpose:** Entry point. Validates user input, initializes DocumentState, loads config preset.

**Specs:** Read `docs/04_architecture.md` §4.2 (Phase A)

**Implementation Guide:**
```python
"""Preflight node — entry point and state initialization (§4.2)."""

from src.graph.state import DocumentState, BudgetState
from src.security.sanitizer import sanitize_user_input
from src.config.presets import load_preset
import logging

logger = logging.getLogger(__name__)

def preflight_node(state: dict) -> dict:
    """Initialize DocumentState from user input.
    
    Input (raw user dict):
        - topic: str
        - target_words: int (5000-50000)
        - quality_preset: "Economy"|"Balanced"|"Premium"
        - style_profile: str (optional)
        - max_budget_dollars: float (≤500)
    
    Output (initialized DocumentState):
        - All required fields populated
        - Config loaded from preset
        - Security validation passed
    """
    
    # 1. Security: sanitize user input
    topic = sanitize_user_input(state.get("topic", ""))
    if not topic:
        raise ValueError("Topic cannot be empty")
    
    target_words = state.get("target_words", 10000)
    if not (5000 <= target_words <= 50000):
        raise ValueError(f"target_words must be 5000-50000, got {target_words}")
    
    max_budget = state.get("max_budget_dollars", 100.0)
    if max_budget > 500:
        raise ValueError(f"max_budget cannot exceed $500, got ${max_budget}")
    
    quality_preset = state.get("quality_preset", "Balanced")
    if quality_preset not in ["Economy", "Balanced", "Premium"]:
        raise ValueError(f"Invalid preset: {quality_preset}")
    
    # 2. Load preset config (§19.1)
    preset_config = load_preset(quality_preset)
    
    # 3. Initialize BudgetState
    budget = BudgetState(
        max_dollars=max_budget,
        spent_dollars=0.0,
        projected_final=0.0,
        regime=quality_preset,
        css_content_threshold=preset_config["css_content_threshold"],
        css_style_threshold=0.80,
        css_panel_threshold=0.50,
        max_iterations=preset_config["max_iterations"],
        jury_size=preset_config["jury_size"],
        mow_enabled=preset_config["mow_enabled"],
        alarm_70_fired=False,
        alarm_90_fired=False,
        hard_stop_fired=False
    )
    
    # 4. Initialize DocumentState
    import uuid
    doc_id = str(uuid.uuid4())
    
    logger.info(f"✅ Preflight: initialized doc_id={doc_id}, preset={quality_preset}, budget=${max_budget}")
    
    return {
        "doc_id": doc_id,
        "thread_id": state.get("thread_id", doc_id),
        "user_id": state.get("user_id", "anonymous"),
        "status": "initializing",
        "config": preset_config,
        "quality_preset": quality_preset,
        "style_profile": state.get("style_profile", preset_config["default_style"]),
        "style_exemplar": None,  # Loaded later if provided
        "topic": topic,
        "target_words": target_words,
        "budget": budget,
        "outline": [],
        "outline_approved": False,
        "current_section_idx": 0,
        "total_sections": 0,
        "current_sources": [],
        "current_draft": "",
        "current_iteration": 0,
        "approved_sections": [],
        "shine_active": False,
        "shine_lora": None,
        "rag_local_sources": [],
        # ... other defaults (see state.py for full schema)
    }
```

**Testing:**
```bash
pytest tests/unit/test_preflight.py -v
# Expected: Valid input → initialized state, invalid input → ValueError
```

**Acceptance Criteria:**
- [ ] Validates topic, target_words, max_budget_dollars
- [ ] Raises ValueError on invalid input
- [ ] Loads preset config from `config/presets.py`
- [ ] Initializes BudgetState with correct thresholds
- [ ] Returns populated DocumentState dict

---

#### Task 1.2: Implement Budget Estimator
**File:** `src/graph/nodes/budget_estimator.py` (CREATE NEW)

**Purpose:** Estimate total cost before starting. Alert user if exceeds budget.

**Specs:** Read `docs/19_budget_controller.md` §19.1

**Implementation Guide:**
```python
"""Budget Estimator — pre-flight cost check (§19.1)."""

from src.graph.state import DocumentState
from src.llm.pricing import cost_usd
import logging

logger = logging.getLogger(__name__)

def budget_estimator_node(state: DocumentState) -> dict:
    """Estimate total cost based on target_words and preset.
    
    Formula (§19.1):
        - Assume ~200 words per section → N sections
        - Per section: Research (3k tokens) + Writer (8k tokens) + Jury (6k tokens) × iterations
        - Total tokens × pricing from MODEL_PRICING
    """
    
    target_words = state["target_words"]
    quality_preset = state["quality_preset"]
    max_budget = state["budget"]["max_dollars"]
    
    # Estimate sections (200-1500 words each depending on doc length)
    if target_words < 8000:
        avg_section_words = 800
    elif target_words < 20000:
        avg_section_words = 1200
    else:
        avg_section_words = 1500
    
    estimated_sections = max(1, target_words // avg_section_words)
    
    # Token estimates per section (§19.1 table)
    if quality_preset == "Economy":
        tokens_per_section = 8000  # Lighter models
        avg_iterations = 1.5
    elif quality_preset == "Balanced":
        tokens_per_section = 15000  # Mid-tier models
        avg_iterations = 2.0
    else:  # Premium
        tokens_per_section = 25000  # Heavy models + MoW
        avg_iterations = 2.5
    
    total_tokens = int(estimated_sections * tokens_per_section * avg_iterations)
    
    # Cost estimate (use average model pricing $0.01/1k tokens as baseline)
    estimated_cost = (total_tokens / 1000) * 0.01
    
    # Add 20% buffer for overhead (reflector, linters, etc.)
    estimated_cost *= 1.20
    
    logger.info(f"💰 Budget estimate: {estimated_sections} sections × {avg_iterations:.1f} iter = ${estimated_cost:.2f} (budget: ${max_budget})")
    
    # Alert if close to budget
    if estimated_cost > max_budget * 0.90:
        logger.warning(f"⚠️ Estimated cost ${estimated_cost:.2f} is 90%+ of budget ${max_budget}")
    
    return {
        "budget": {
            **state["budget"],
            "projected_final": estimated_cost
        }
    }
```

**Testing:**
```bash
pytest tests/unit/test_budget_estimator.py -v
# Expected: Reasonable cost estimate, warning if >90% budget
```

---

#### Task 1.3: Implement Await Outline Node
**File:** `src/graph/nodes/await_outline.py` (CREATE NEW)

**Purpose:** Human approval gate for outline. For MVP, auto-approve.

**Specs:** Read `docs/04_architecture.md` §4.2

**Implementation Guide:**
```python
"""Await Outline — human approval gate (§4.2)."""

from src.graph.state import DocumentState
import logging

logger = logging.getLogger(__name__)

def await_outline_node(state: DocumentState) -> dict:
    """Wait for human approval of outline.
    
    MVP: Auto-approve (skip human-in-loop for now).
    Future: Integrate with UI for approval.
    """
    
    outline = state["outline"]
    
    # MVP: Auto-approve
    logger.info(f"✅ Outline auto-approved: {len(outline)} sections")
    
    return {
        "outline_approved": True,
        "total_sections": len(outline)
    }

# Future: Add human approval logic
# def await_outline_node_with_human(state):
#     if state.get("outline_approved"):
#         return {"outline_approved": True}
#     else:
#         # Pause execution, return interrupt signal
#         raise NodeInterrupt("Waiting for outline approval")
```

**Testing:**
```bash
pytest tests/unit/test_await_outline.py -v
# Expected: Always returns outline_approved=True for MVP
```

---

### **Day 3-4: Iteration Support Nodes**

#### Task 2.1: Implement Post Draft Analyzer
**File:** `src/graph/nodes/post_draft_analyzer.py` (CREATE NEW)

**Purpose:** Detect gaps/contradictions in draft. Trigger targeted research if needed.

**Specs:** Read `docs/05_agents.md` §5.11

**Implementation Guide:**
```python
"""Post Draft Analyzer — gap detection (§5.11)."""

from src.graph.state import DocumentState
from src.llm.client import llm_client
import json
import logging

logger = logging.getLogger(__name__)

def post_draft_analyzer_node(state: DocumentState) -> dict:
    """Analyze draft for gaps, contradictions, weak claims.
    
    Output:
        - post_draft_gaps: list[dict] with gap descriptions
        - Route: "gap" if issues found (iteration==1 only), else "no_gap"
    """
    
    draft = state["current_draft"]
    section_scope = state["outline"][state["current_section_idx"]]["scope"]
    current_iteration = state.get("current_iteration", 1)
    
    # Skip gap analysis after iteration 1 (§5.11)
    if current_iteration > 1:
        logger.info("Iteration >1: skipping gap analysis")
        return {"post_draft_gaps": []}
    
    prompt = f"""Analyze this draft for knowledge gaps or weak claims.

Section scope: {section_scope}

Draft:
{draft}

Identify:
1. Claims without citations
2. Vague statements needing specifics
3. Missing context
4. Contradictions

Return JSON:
{{
  "gaps": [
    {{"type": "missing_citation", "claim": "...", "query": "search query"}},
    {{"type": "vague", "claim": "...", "query": "..."}}
  ]
}}
"""
    
    response = llm_client.call(
        model="google/gemini-2.5-pro",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=2048
    )
    
    try:
        gaps_data = json.loads(response["text"])
        gaps = gaps_data.get("gaps", [])
    except json.JSONDecodeError:
        gaps = []
    
    logger.info(f"Post-draft analysis: {len(gaps)} gaps detected")
    
    return {
        "post_draft_gaps": gaps,
        "targeted_research_active": len(gaps) > 0
    }
```

**Router Update (in `src/graph/routers/post_draft_gap.py`):**
```python
def route_post_draft_gap(state):
    if state.get("post_draft_gaps") and state["current_iteration"] == 1:
        return "gap"  # → researcher_targeted
    else:
        return "no_gap"  # → style_linter
```

---

#### Task 2.2: Implement Metrics Collector
**File:** `src/graph/nodes/metrics_collector.py` (CREATE NEW)

**Purpose:** Compute draft embeddings, word count, citation count. Used by OscillationCheck.

**Specs:** Read `docs/05_agents.md` §5.8

**Implementation Guide:**
```python
"""Metrics Collector — draft metrics (§5.8)."""

from src.graph.state import DocumentState
from FlagEmbedding import FlagModel
import logging

logger = logging.getLogger(__name__)

# Global embedder (lazy load)
_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = FlagModel('BAAI/bge-m3', use_fp16=True)
    return _embedder

def metrics_collector_node(state: DocumentState) -> dict:
    """Compute draft metrics for oscillation detection.
    
    Output:
        - draft_embeddings: list (bounded to last 4)
        - word_count: int
        - citations_used: list[str]
    """
    
    draft = state["current_draft"]
    
    # 1. Word count
    word_count = len(draft.split())
    
    # 2. Citation extraction
    import re
    citations_used = list(set(re.findall(r"\[(\w+)\]", draft)))
    
    # 3. Embedding (for oscillation detection §13)
    embedder = get_embedder()
    embedding = embedder.encode(draft).tolist()
    
    logger.info(f"Metrics: {word_count} words, {len(citations_used)} citations, embedding computed")
    
    return {
        "word_count": word_count,
        "citations_used": citations_used,
        "draft_embeddings": state.get("draft_embeddings", []) + [embedding]  # Bounded by §29.5
    }
```

**Testing:**
```bash
pytest tests/unit/test_metrics_collector.py -v
# Expected: Correct word count, citations, embedding shape
```

---

### **Day 5-6: Human-in-Loop & Output**

#### Task 3.1: Implement Await Human Node
**File:** `src/graph/nodes/await_human.py` (CREATE NEW)

**Purpose:** Pause execution for human intervention (conflicts, vetos).

**Specs:** Read `docs/04_architecture.md` §4.3

**Implementation Guide:**
```python
"""Await Human — human intervention gate (§4.3)."""

from src.graph.state import DocumentState
from langgraph.checkpoint import Interrupt
import logging

logger = logging.getLogger(__name__)

def await_human_node(state: DocumentState) -> dict:
    """Pause execution and wait for human resolution.
    
    MVP: Raise interrupt. LangGraph will pause and resume when user provides input.
    """
    
    escalation = state.get("active_escalation", {})
    escalation_type = escalation.get("type", "unknown")
    
    logger.warning(f"⚠️ Human intervention required: {escalation_type}")
    
    # LangGraph interrupt: pauses execution
    raise Interrupt(
        value={
            "message": f"Human approval needed: {escalation_type}",
            "escalation": escalation
        }
    )
    
    # When resumed, return empty (state already has user's resolution)
    return {}
```

**Testing:**
```bash
# Test requires LangGraph checkpointer setup
pytest tests/integration/test_await_human.py -v
# Expected: Interrupt raised, execution paused
```

---

#### Task 3.2: Implement Feedback Collector
**File:** `src/graph/nodes/feedback_collector.py` (CREATE NEW)

**Purpose:** Collect post-delivery feedback (optional, low priority).

**Specs:** Read `docs/05_agents.md` §5.20

**Implementation Guide:**
```python
"""Feedback Collector — post-delivery (§5.20)."""

from src.graph.state import DocumentState
import logging

logger = logging.getLogger(__name__)

def feedback_collector_node(state: DocumentState) -> dict:
    """Collect user feedback after document delivery.
    
    MVP: No-op. Future: Send survey, track satisfaction.
    """
    
    doc_id = state["doc_id"]
    
    logger.info(f"📝 Document {doc_id} delivered. Feedback collection pending.")
    
    # TODO: Integrate with feedback API
    # - Send email with survey link
    # - Track user rating (1-5 stars)
    # - Store in PostgreSQL for analytics
    
    return {
        "status": "completed"
    }
```

---

### **Day 7: Integration Testing & Bug Fixes**

#### Task 4.1: Update Graph — Remove Stubs
**File:** `src/graph/graph.py` (UPDATE)

**Instructions:**
1. Replace `_REAL_NODES` dict with new implementations:
   ```python
   _REAL_NODES: dict[str, callable] = {
       # ... existing nodes ...
       "preflight": preflight_node,                  # NEW
       "budget_estimator": budget_estimator_node,    # NEW
       "await_outline": await_outline_node,          # NEW
       "post_draft_analyzer": post_draft_analyzer_node,  # NEW
       "metrics_collector": metrics_collector_node,  # NEW
       "await_human": await_human_node,              # NEW
       "feedback_collector": feedback_collector_node, # NEW
   }
   ```

2. Verify graph compiles:
   ```bash
   python -c "from src.graph.graph import build_graph; g = build_graph(); print('✅ Graph compiled')"
   ```

---

#### Task 4.2: End-to-End MVP Test
**File:** `tests/integration/test_mvp_e2e.py` (CREATE NEW)

**Test Case:**
```python
"""End-to-end MVP test."""

import pytest
from src.graph.graph import build_graph

def test_mvp_single_section():
    """Test: topic → 1 approved section."""
    
    graph = build_graph()
    
    input_state = {
        "topic": "Impact of AI on education",
        "target_words": 5000,
        "quality_preset": "Balanced",
        "max_budget_dollars": 50.0
    }
    
    result = graph.invoke(input_state)
    
    # Assertions
    assert result["status"] == "completed"
    assert len(result["approved_sections"]) == 1
    assert result["budget"]["spent_dollars"] < 50.0
    assert result["outline_approved"] is True
    
    print(f"✅ MVP test passed: {len(result['approved_sections'])} section approved")
```

**Run:**
```bash
pytest tests/integration/test_mvp_e2e.py -v --tb=short
```

---

## 🔧 Development Guidelines

### Code Style
- **Follow existing patterns:** Check `src/graph/nodes/planner.py`, `writer.py` for reference structure
- **Type hints:** Use `DocumentState` from `src/graph/state.py`
- **Logging:** Use `logger.info()` for important events, `logger.debug()` for details
- **Error handling:** Wrap LLM calls in try/except, provide fallbacks

### Testing Strategy
1. **Unit tests first:** Test each node in isolation
2. **Mock LLM calls:** Use `unittest.mock.patch` to avoid API costs
3. **Integration tests:** Run end-to-end after all nodes implemented

### Commit Conventions
```bash
git commit -m "feat(preflight): implement state initialization and validation"
git commit -m "feat(budget): add cost estimation logic"
git commit -m "test(mvp): add end-to-end single-section test"
```

---

## 📚 Key Reference Documents

**Read these specs carefully before implementing each node:**

| Node | Spec File | Section |
|------|-----------|---------|
| Preflight | `docs/04_architecture.md` | §4.2 Phase A |
| Budget Estimator | `docs/19_budget_controller.md` | §19.1 |
| Await Outline | `docs/04_architecture.md` | §4.2 |
| Post Draft Analyzer | `docs/05_agents.md` | §5.11 |
| Metrics Collector | `docs/05_agents.md` | §5.8 |
| Await Human | `docs/04_architecture.md` | §4.3 |
| Feedback Collector | `docs/05_agents.md` | §5.20 |

**General references:**
- State schema: `docs/04_architecture.md` §4.6
- LLM client: Check `src/llm/client.py` for API
- Routing: Check `src/graph/routers/*.py` for conditional logic patterns

---

## 🎯 Success Metrics

**After completing all 7 nodes:**
- [ ] Graph compiles without stub warnings
- [ ] `test_mvp_e2e.py` passes
- [ ] Budget estimate within ±20% of actual cost
- [ ] No crashes on invalid user input (preflight catches errors)
- [ ] Human-in-loop interrupt works (await_human)

**Performance targets:**
- Single section run: <2 minutes (without jury delays)
- Cost per section: $2-8 depending on preset
- Graph state size: <500KB after 1 section

---

## 🚨 Common Pitfalls to Avoid

1. **Don't mutate state directly:** LangGraph expects `return dict` with updates, not `state[key] = value`
2. **Don't skip error handling:** LLM calls fail. Always have try/except + fallback
3. **Don't hardcode values:** Use `state["config"]` for preset-specific params
4. **Don't forget logging:** Every node should log success/failure
5. **Don't ignore specs:** If spec says "bounded to 4", use `MaxLen(4)` reducer

---

## 💬 Questions? Check Existing Code First

**Before asking:**
1. Check similar nodes: `planner.py`, `writer.py`, `jury.py` have good patterns
2. Check routers: `src/graph/routers/*.py` for conditional logic examples
3. Check state: `src/graph/state.py` for field definitions
4. Check tests: `tests/unit/test_*.py` for assertion patterns

**If still unclear:**
- Search specs: `grep -r "§5.11" docs/` to find relevant section
- Check graph.py: See how node is connected to understand inputs/outputs

---

## 🏁 Final Checklist Before Submitting

- [ ] All 7 stub nodes implemented (no more `pass` or `return {}`)
- [ ] Each node has docstring with purpose + specs reference
- [ ] Each node has unit test in `tests/unit/test_[node].py`
- [ ] `test_mvp_e2e.py` passes
- [ ] Graph compiles: `python -c "from src.graph.graph import build_graph; build_graph()"`
- [ ] No import errors: All dependencies in `requirements.txt`
- [ ] Logging is informative (can trace execution flow)

---

**Good luck! You're 75% there — just 7 nodes to complete MVP! 🚀**
