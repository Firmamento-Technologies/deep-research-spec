# 🤖 Claude Opus 4.6 Development Prompt — DRS Phase 1

> **Target:** Implement critical MVP nodes for end-to-end pipeline  
> **Repository:** [lucadidomenicodopehubs/deep-research-spec](https://github.com/lucadidomenicodopehubs/deep-research-spec/tree/struct)  
> **Branch:** `struct`  
> **Date:** 2026-02-23

---

## 📊 Current State

**✅ Already Implemented (75% complete):**
- Graph topology: 32 nodes defined + 11 routers
- State schema: complete with bounded reducers
- RAG + SHINE integration: memvid_connector + shine_adapter
- Jury system: 9 judges + aggregator + CSS computation
- Iteration loop: reflector + style_linter + oscillation_check
- 10 connectors: academic, web, local RAG, user uploads
- LLM client: unified wrapper with prompt caching support

**❌ Critical Gaps (MVP Blockers):**
- 15 node implementations are stubs (empty functions)
- Infrastructure: config presets, storage interfaces
- End-to-end testing: no working pipeline yet

---

## 🎯 Your Mission

**Implement Phase 1 Critical Path** — nodes required for MVP single-section run:

```
Topic → Planner → Researcher → Citations → Synthesizer 
→ ShineAdapter → Writer → PostDraftAnalyzer → Jury → Aggregator 
→ SectionCheckpoint → Output
```

**Timeline:** Complete in order. Test after each node.

---

## 📝 Implementation Tasks

### **TASK 1: Preflight Node** ⚡ HIGH PRIORITY
**File:** `src/graph/nodes/preflight.py` (NEW)

**Purpose:** Validate user input, load config preset, initialize state.

**Specs:** `docs/04_architecture.md` §4.2 (Phase A)

**Implementation:**
```python
"""Preflight — Input validation & config initialization (§4.2)."""

from src.graph.state import DocumentState
from src.config.presets import QUALITY_PRESETS
import logging

logger = logging.getLogger(__name__)

def preflight_node(state: DocumentState) -> dict:
    """Validate inputs and initialize config.
    
    Inputs:
        - topic (str): user query
        - target_words (int): total document length
        - quality_preset (str): Economy|Balanced|Premium
        - max_budget_dollars (float): hard cap (default 500)
    
    Returns:
        - config (dict): loaded preset parameters
        - status (str): "running"
        - doc_id (str): generated UUID
    """
    
    # Validate inputs
    topic = state.get("topic", "")
    if not topic or len(topic) < 10:
        raise ValueError("Topic must be ≥10 characters")
    
    target_words = state.get("target_words", 5000)
    if not (500 <= target_words <= 50000):
        raise ValueError("target_words must be 500-50000")
    
    quality_preset = state.get("quality_preset", "Balanced")
    if quality_preset not in QUALITY_PRESETS:
        raise ValueError(f"Invalid preset: {quality_preset}")
    
    max_budget = state.get("max_budget_dollars", 500.0)
    if max_budget > 500.0:
        logger.warning(f"Budget {max_budget} exceeds $500 cap — clamping")
        max_budget = 500.0
    
    # Load preset config
    config = QUALITY_PRESETS[quality_preset].copy()
    config["max_budget_dollars"] = max_budget
    config["target_words"] = target_words
    
    # Generate doc_id
    import uuid
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    
    logger.info(f"✅ Preflight OK: {topic[:50]}... | {quality_preset} | ${max_budget}")
    
    return {
        "doc_id": doc_id,
        "status": "running",
        "config": config,
        "quality_preset": quality_preset,
        "target_words": target_words
    }
```

**Dependencies:**
- Create `src/config/presets.py` with QUALITY_PRESETS dict (Economy/Balanced/Premium params)
- Reference: `docs/19_budget_controller.md` §19.2 for preset thresholds

**Test:**
```python
state = {"topic": "machine learning", "target_words": 5000, "quality_preset": "Premium"}
result = preflight_node(state)
assert result["status"] == "running"
assert result["config"]["quality_preset"] == "Premium"
```

---

### **TASK 2: Budget Estimator Node** ⚡ HIGH PRIORITY
**File:** `src/graph/nodes/budget_estimator.py` (NEW)

**Purpose:** Pre-flight cost estimation (§19.1).

**Specs:** `docs/19_budget_controller.md` §19.1

**Implementation:**
```python
"""BudgetEstimator — Pre-flight cost projection (§19.1)."""

from src.graph.state import DocumentState
from src.llm.pricing import MODEL_PRICING
import logging

logger = logging.getLogger(__name__)

def budget_estimator_node(state: DocumentState) -> dict:
    """Estimate total cost and set regime parameters.
    
    Returns:
        - budget (BudgetState): initialized budget tracking
    """
    
    target_words = state["target_words"]
    quality_preset = state["quality_preset"]
    config = state["config"]
    
    # Estimate sections (rough: 1 section per 1000 words)
    estimated_sections = max(3, target_words // 1000)
    
    # Cost model (simplified):
    # - Research per section: ~$1-3
    # - Writer per section: ~$2-5 (depends on SHINE active)
    # - Jury per section: ~$3-8 (depends on jury_size)
    # - Iterations: avg 2x per section
    
    if quality_preset == "Economy":
        cost_per_section = 3.0  # Gemini Flash models
        jury_size = 1
        max_iterations = 2
    elif quality_preset == "Balanced":
        cost_per_section = 8.0  # Mix of models
        jury_size = 2
        max_iterations = 3
    else:  # Premium
        cost_per_section = 15.0  # Claude Opus 4.5 + o3
        jury_size = 3
        max_iterations = 4
    
    projected_final = cost_per_section * estimated_sections * 1.5  # Buffer
    
    logger.info(f"📊 Budget estimate: {estimated_sections} sections × ${cost_per_section:.2f} = ${projected_final:.2f}")
    
    # Load thresholds from config
    css_content_threshold = config.get("css_content_threshold", 0.70)
    css_style_threshold = config.get("css_style_threshold", 0.80)
    
    return {
        "budget": {
            "max_dollars": state["config"]["max_budget_dollars"],
            "spent_dollars": 0.0,
            "projected_final": projected_final,
            "regime": quality_preset,
            "css_content_threshold": css_content_threshold,
            "css_style_threshold": css_style_threshold,
            "css_panel_threshold": 0.50,
            "max_iterations": max_iterations,
            "jury_size": jury_size,
            "mow_enabled": quality_preset == "Premium",
            "alarm_70_fired": False,
            "alarm_90_fired": False,
            "hard_stop_fired": False
        }
    }
```

**Test:**
```python
state = {"target_words": 5000, "quality_preset": "Premium", "config": {"max_budget_dollars": 500}}
result = budget_estimator_node(state)
assert result["budget"]["jury_size"] == 3
assert result["budget"]["max_iterations"] == 4
```

---

### **TASK 3: Await Outline Node** ⚡ MEDIUM PRIORITY
**File:** `src/graph/nodes/await_outline.py` (NEW)

**Purpose:** Wait for human approval of outline (MVP: auto-approve).

**Implementation:**
```python
"""AwaitOutline — Human approval gate (MVP: auto-approve)."""

from src.graph.state import DocumentState

def await_outline_node(state: DocumentState) -> dict:
    """MVP: Auto-approve outline. Production: wait for human input."""
    
    # TODO Production: integrate with Run Companion (§6) for approval UI
    # For MVP: always approve
    
    return {
        "outline_approved": True
    }
```

---

### **TASK 4: Post-Draft Analyzer** ⚡ HIGH PRIORITY
**File:** `src/graph/nodes/post_draft_analyzer.py` (NEW)

**Purpose:** Detect gaps in draft vs section scope (§5.11).

**Specs:** `docs/05_agents.md` §5.11

**Implementation:**
```python
"""PostDraftAnalyzer — Gap detection after Writer (§5.11)."""

from src.llm.client import llm_client
from src.graph.state import DocumentState
import json
import logging

logger = logging.getLogger(__name__)

def post_draft_analyzer_node(state: DocumentState) -> dict:
    """Detect missing topics in draft vs section scope.
    
    Returns:
        - post_draft_gaps (list[dict]): [{\"topic\": \"...\", \"evidence_needed\": \"...\"}, ...]
    """
    
    # Skip if iteration > 1 (only run on first draft)
    if state.get("current_iteration", 1) > 1:
        logger.info("Iteration >1 — skipping gap analysis")
        return {"post_draft_gaps": []}
    
    draft = state["current_draft"]
    section_scope = state["outline"][state["current_section_idx"]]["scope"]
    
    prompt = f"""
Analyze if this draft fully covers the section scope.

Section scope:
{section_scope}

Draft:
{draft}

Identify any topics mentioned in the scope that are missing or under-developed in the draft.

Return JSON:
{{
  "gaps": [
    {{"topic": "...", "evidence_needed": "..."}},
    ...
  ]
}}

Return empty array if no gaps.
"""
    
    response = llm_client.call(
        model="google/gemini-2.5-flash",  # Fast + cheap for gap detection
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1024
    )
    
    try:
        result = json.loads(response["text"])
        gaps = result.get("gaps", [])
    except json.JSONDecodeError:
        logger.warning("Gap analyzer returned invalid JSON — assuming no gaps")
        gaps = []
    
    if gaps:
        logger.info(f"⚠️ Detected {len(gaps)} gaps: {[g['topic'] for g in gaps]}")
    else:
        logger.info("✅ No gaps detected")
    
    return {
        "post_draft_gaps": gaps
    }
```

**Test:**
```python
state = {
    "current_draft": "Machine learning is...",
    "outline": [{"scope": "Overview of ML and deep learning applications"}],
    "current_section_idx": 0,
    "current_iteration": 1
}
result = post_draft_analyzer_node(state)
assert isinstance(result["post_draft_gaps"], list)
```

---

### **TASK 5: Metrics Collector** ⚡ MEDIUM PRIORITY
**File:** `src/graph/nodes/metrics_collector.py` (UPDATE EXISTING)

**Purpose:** Compute draft embeddings + metrics (§5.8).

**Current Status:** File exists at 4.5KB — verify completeness.

**Required Updates:**
1. Ensure bge-m3 embeddings (from Phase 0 Task 0.5)
2. Add word count, citation count metrics
3. Append to `draft_embeddings` (bounded to 4 items per §29.5)

**Verification:**
```python
# Check if implementation exists
from src.graph.nodes.metrics_collector import metrics_collector_node
state = {"current_draft": "test " * 100}
result = metrics_collector_node(state)
assert "draft_embeddings" in result  # Should return list of embeddings
```

**If missing/incomplete:** Implement per `docs/05_agents.md` §5.8 spec.

---

### **TASK 6: Config Presets** ⚡ CRITICAL DEPENDENCY
**File:** `src/config/presets.py` (NEW)

**Purpose:** Define Economy/Balanced/Premium parameters (§19.2).

**Implementation:**
```python
"""Quality presets configuration (§19.2)."""

QUALITY_PRESETS = {
    "Economy": {
        "css_content_threshold": 0.65,
        "css_style_threshold": 0.80,
        "max_iterations": 2,
        "jury_size": 1,
        "mow_enabled": False,
        "models": {
            "planner": "google/gemini-2.5-flash",
            "researcher": "perplexity/sonar-pro",
            "writer": "google/gemini-2.5-pro",
            "jury_r": "google/gemini-2.5-pro",
            "jury_f": "google/gemini-2.5-flash",
            "jury_s": "google/gemini-2.5-flash",
            "reflector": "google/gemini-2.5-pro"
        }
    },
    "Balanced": {
        "css_content_threshold": 0.70,
        "css_style_threshold": 0.80,
        "max_iterations": 3,
        "jury_size": 2,
        "mow_enabled": False,
        "models": {
            "planner": "google/gemini-2.5-pro",
            "researcher": "perplexity/sonar-pro",
            "writer": "anthropic/claude-opus-4-5",
            "jury_r": "openai/o3",
            "jury_f": "google/gemini-2.5-pro",
            "jury_s": "google/gemini-2.5-pro",
            "reflector": "anthropic/claude-opus-4-5"
        }
    },
    "Premium": {
        "css_content_threshold": 0.78,
        "css_style_threshold": 0.85,
        "max_iterations": 4,
        "jury_size": 3,
        "mow_enabled": True,
        "models": {
            "planner": "google/gemini-2.5-pro",
            "researcher": "perplexity/sonar-pro",
            "writer": "anthropic/claude-opus-4-5",
            "jury_r": "openai/o3",
            "jury_f": "google/gemini-2.5-pro",
            "jury_s": "anthropic/claude-opus-4-5",
            "reflector": "anthropic/claude-opus-4-5"
        }
    }
}

def get_model_for_task(preset: str, task: str) -> str:
    """Get model assignment for task in given preset."""
    return QUALITY_PRESETS[preset]["models"].get(task, "google/gemini-2.5-flash")
```

**Reference:** `docs/19_budget_controller.md` §19.2, `docs/28_llm_assignments.md`

---

### **TASK 7: Publisher Node** ⚡ MEDIUM PRIORITY
**File:** `src/graph/nodes/publisher.py` (NEW)

**Purpose:** Output final document (§5.19).

**Specs:** `docs/05_agents.md` §5.19

**Implementation (MVP: Markdown only):**
```python
"""Publisher — Output generation (§5.19)."""

from src.graph.state import DocumentState
import logging

logger = logging.getLogger(__name__)

def publisher_node(state: DocumentState) -> dict:
    """Generate final output document.
    
    MVP: Markdown only. Future: DOCX, PDF, LaTeX.
    """
    
    doc_id = state["doc_id"]
    approved_sections = state.get("approved_sections", [])
    
    if not approved_sections:
        logger.error("No approved sections — cannot publish")
        return {"output_paths": {}, "status": "failed"}
    
    # Generate Markdown
    markdown = f"# {state.get('topic', 'Document')}\\n\\n"
    
    for section in approved_sections:
        markdown += f"## {section['title']}\\n\\n"
        markdown += section['content'] + "\\n\\n"
    
    # Write to file
    output_path = f"output/{doc_id}.md"
    with open(output_path, "w") as f:
        f.write(markdown)
    
    logger.info(f"✅ Published: {output_path}")
    
    return {
        "output_paths": {"markdown": output_path},
        "status": "completed"
    }
```

**Test:**
```python
state = {
    "doc_id": "test123",
    "topic": "Test Doc",
    "approved_sections": [{"title": "Intro", "content": "test content"}]
}
result = publisher_node(state)
assert result["status"] == "completed"
assert "markdown" in result["output_paths"]
```

---

## 🔧 Implementation Guidelines

### **1. Pattern to Follow**

All nodes follow this structure (see existing `src/graph/nodes/*.py`):

```python
"""NodeName — Brief description (§spec_ref)."""

from src.graph.state import DocumentState
from src.llm.client import llm_client  # If LLM call needed
import logging

logger = logging.getLogger(__name__)

def node_name_node(state: DocumentState) -> dict:
    """Docstring with inputs/outputs."""
    
    # 1. Extract inputs from state
    input_value = state["key"]
    
    # 2. Process
    result = do_work(input_value)
    
    # 3. Return dict with changed keys only
    return {
        "output_key": result
    }
```

### **2. Error Handling**

**CRITICAL:** All LLM calls must have try/except:

```python
try:
    response = llm_client.call(...)
    result = json.loads(response["text"])
except (json.JSONDecodeError, KeyError, Exception) as e:
    logger.error(f"Node failed: {e}")
    # Return safe fallback
    return {"key": default_value}
```

### **3. Logging**

Use consistent log levels:
- `logger.info()` for normal flow
- `logger.warning()` for recoverable issues
- `logger.error()` for failures

### **4. Testing**

After each node:
```bash
# Test import
python -c "from src.graph.nodes.preflight import preflight_node; print('OK')"

# Unit test
pytest tests/unit/test_preflight.py -v

# Integration test (if graph updated)
python -c "from src.graph.graph import build_graph; g = build_graph(); print('Graph OK')"
```

---

## 🎯 Deliverable Checklist

**Phase 1 MVP Complete when:**

- [ ] All 7 tasks implemented (preflight, budget_estimator, await_outline, post_draft_analyzer, metrics_collector, config/presets, publisher)
- [ ] Graph compiles: `build_graph()` works without errors
- [ ] End-to-end test passes: topic → single approved section
- [ ] Cost tracking works: `budget.spent_dollars` updates correctly
- [ ] SHINE integration works: `shine_active` flag toggles based on preset

**Success Metrics:**
- Single-section run completes in <5min
- Cost per section: $2-8 (Economy), $8-15 (Balanced), $15-25 (Premium)
- Cache hit rate ≥50% (check llm_client logs)

---

## 📚 Reference Documents

**Must read before implementing:**
1. `docs/04_architecture.md` — Graph topology, node list
2. `docs/05_agents.md` — Agent specifications (§5.1-5.21)
3. `docs/19_budget_controller.md` — Budget tracking, presets
4. `docs/29_performance_optimizations.md` — §29.1 prompt caching, §29.5 bounded state
5. `docs/RAG_SHINE_INTEGRATION.md` — Local RAG + SHINE LoRA usage

**Existing code patterns:**
- `src/graph/nodes/researcher.py` — Shows LLM call + error handling
- `src/graph/nodes/writer.py` — Shows §29.1 prompt caching usage
- `src/graph/nodes/jury.py` — Shows parallel async execution
- `src/graph/state.py` — Complete state schema reference

---

## 🚀 Start Here

**First command:**
```bash
# 1. Verify current graph state
python -c "from src.graph.graph import build_graph; g = build_graph(); print(g.nodes)"

# 2. Check which nodes are stubs vs implemented
grep -r "def.*_node" src/graph/nodes/*.py | wc -l  # Should be ~25

# 3. Start with TASK 1 (preflight)
# Read: docs/04_architecture.md §4.2
# Implement: src/graph/nodes/preflight.py
# Test: pytest tests/unit/test_preflight.py
```

**Commit after each task:**
```bash
git add src/graph/nodes/preflight.py src/config/presets.py
git commit -m "feat(task-1): implement preflight node with config presets"
git push origin struct
```

---

## 🆘 If Stuck

**Problem:** Specs unclear  
**Solution:** Read full spec file in `docs/`. Search for §reference in all .md files.

**Problem:** Existing code conflicts  
**Solution:** Check `src/graph/nodes/` for similar patterns. Copy structure.

**Problem:** Test fails  
**Solution:** Run with verbose: `pytest tests/unit/test_X.py -vv -s`. Check logs in `logs/`.

**Problem:** Import error  
**Solution:** Verify dependencies: `pip install -r requirements-shine.txt`

---

**Last Updated:** 2026-02-23  
**Target Completion:** 7 tasks = ~3-4 days @ 1-2 tasks/day  
**Next Phase:** Phase 2 (Advanced features: MoW, Panel, Coherence Guard)
