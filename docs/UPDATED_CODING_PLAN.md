# DRS Updated Implementation Plan — Post Gap Analysis

> **Status:** 75% Complete (as of 2026-02-23)  
> **Repository:** [lucadidomenicodopehubs/deep-research-spec](https://github.com/lucadidomenicodopehubs/deep-research-spec/tree/struct)  
> **Branch:** `struct`  
> **Target Audience:** Claude Opus 4.6 / AI coding agents  

---

## 📊 Current State Summary

### ✅ **COMPLETED INFRASTRUCTURE (75%)**

```
src/
├── llm/
│   ├── client.py                    ✅ COMPLETE (unified LLM client + §29.1 caching)
│   └── pricing.py                   ✅ COMPLETE (MODEL_PRICING table)
├── graph/
│   ├── state.py                     ✅ COMPLETE (DocumentState + bounded reducers §29.5)
│   ├── graph.py                     ✅ COMPLETE (32 nodes + 11 routers topology)
│   ├── nodes/
│   │   ├── planner.py                      ✅ COMPLETE
│   │   ├── researcher.py                   ✅ COMPLETE
│   │   ├── researcher_targeted.py          ✅ COMPLETE
│   │   ├── citation_manager.py             ✅ COMPLETE
│   │   ├── citation_verifier.py            ✅ COMPLETE
│   │   ├── source_sanitizer.py             ✅ COMPLETE
│   │   ├── source_synthesizer.py           ✅ COMPLETE
│   │   ├── shine_adapter.py                ✅ COMPLETE (Phase 0 RAG+SHINE)
│   │   ├── writer.py                       ✅ COMPLETE (§29.1 caching + SHINE support)
│   │   ├── jury_base.py                    ✅ COMPLETE
│   │   ├── judge_r.py                      ✅ COMPLETE
│   │   ├── judge_f.py                      ✅ COMPLETE
│   │   ├── judge_s.py                      ✅ COMPLETE
│   │   ├── jury.py                         ✅ COMPLETE (parallel 9 judges)
│   │   ├── jury_mock.py                    ✅ COMPLETE (temporary)
│   │   ├── aggregator.py                   ✅ COMPLETE (CSS + routing §9)
│   │   ├── reflector.py                    ✅ COMPLETE
│   │   ├── style_linter.py                 ✅ COMPLETE
│   │   ├── style_fixer.py                  ✅ COMPLETE
│   │   ├── oscillation_check.py            ✅ COMPLETE
│   │   ├── context_compressor.py           ✅ COMPLETE (10KB implementation)
│   │   ├── section_checkpoint.py           ✅ COMPLETE (17KB implementation)
│   │   └── budget_controller.py            ✅ COMPLETE (8KB implementation)
│   └── routers/                     ✅ COMPLETE (11 routers implemented)
│       ├── outline_approval.py
│       ├── post_aggregator.py
│       ├── post_reflector.py
│       ├── post_oscillation.py
│       ├── post_coherence.py
│       ├── next_section.py
│       ├── budget_route.py
│       ├── style_lint.py
│       ├── post_draft_gap.py
│       ├── post_qa.py
│       └── panel_loop.py
├── connectors/                      ✅ COMPLETE (10 connectors)
│   ├── memvid_connector.py                 ✅ Phase 0 RAG
│   ├── academic.py                         ✅ arxiv, scholar
│   ├── institutional.py                    ✅ gov, org
│   ├── web_general.py                      ✅ sonar-pro, tavily, brave
│   ├── user_upload.py                      ✅ PDF/DOCX
│   ├── scraper.py                          ✅ web scraping
│   └── social.py                           ✅ Twitter, Reddit
├── budget/                          ⚠️  NEEDS VERIFICATION
├── config/                          ⚠️  NEEDS VERIFICATION
├── models/                          ⚠️  NEEDS VERIFICATION
├── security/                        ⚠️  NEEDS VERIFICATION
├── storage/                         ⚠️  NEEDS VERIFICATION
└── shine/                           ⚠️  NEEDS VERIFICATION

tests/
├── test_memvid_connector.py         ✅ COMPLETE
├── test_shine_adapter.py            ✅ COMPLETE
├── test_rag_fallback.py             ✅ COMPLETE
└── test_rag_shine_e2e.py            ✅ COMPLETE
```

---

## ❌ **CRITICAL GAPS (MVP Blockers)**

### **Gap Category 1: STUB NODES (High Priority)**

23 nodes exist in `graph.py` but are **stub implementations** (return empty dict):

| Node | File | Effort | Blocking For |
|------|------|--------|--------------|
| `preflight` | ❌ Missing | 1d | Entry point |
| `budget_estimator` | ❌ Missing | 1d | Cost estimation |
| `await_outline` | ❌ Missing | 0.5d | Human approval gate |
| `post_draft_analyzer` | ❌ Missing | 1d | Gap detection (iteration 1) |
| `metrics_collector` | ❌ Missing | 0.5d | Draft metrics |
| `span_editor` | ❌ Missing | 2d | Surgical edits (§12.6) |
| `diff_merger` | ❌ Missing | 1d | Merge surgical edits |
| `panel_discussion` | ❌ Missing | 3d | CSS<0.50 fallback (§11) |
| `coherence_guard` | ❌ Missing | 2d | Cross-section conflicts |
| `await_human` | ❌ Missing | 1d | Escalation gate |
| `post_qa` | ❌ Missing | 1d | Final validation |
| `length_adjuster` | ❌ Missing | 1d | Word count fix |
| `publisher` | ❌ Missing | 1d | Output generation |
| `feedback_collector` | ❌ Missing | 0.5d | Post-delivery |

**Total effort (stubs):** ~15 giorni

---

### **Gap Category 2: INFRASTRUCTURE (Critical)**

Missing foundational components:

| Component | File | Effort | Needed For |
|-----------|------|--------|------------|
| **Config Presets** | `src/config/presets.py` | 0.5d | Economy/Balanced/Premium settings |
| **Style Profiles** | `src/config/style_profiles.py` | 1d | L1/L2 rules (§26) |
| **Budget Estimator** | `src/budget/estimator.py` | 1d | Pre-flight cost check |
| **DB Interface** | `src/storage/db.py` | 1d | PostgreSQL checkpoints |
| **S3 Interface** | `src/storage/s3.py` | 0.5d | Document storage |
| **Input Sanitizer** | `src/security/sanitizer.py` | 0.5d | XSS/injection prevention |

**Total effort (infra):** ~5 giorni

---

### **Gap Category 3: VERIFICATION NEEDED**

These files **exist** but need verification (may be partial stubs):

| File | Size | Status | Action |
|------|------|--------|--------|
| `researcher.py` | 4.7KB | ⚠️ Unknown | Verify completeness vs §5.1 |
| `researcher_targeted.py` | 3.4KB | ⚠️ Unknown | Verify vs §5.3 |
| `citation_manager.py` | 4.5KB | ⚠️ Unknown | Verify vs §24 |
| `citation_verifier.py` | 4.8KB | ⚠️ Unknown | Verify vs §24 |
| `source_sanitizer.py` | 2.4KB | ⚠️ Unknown | Verify vs §5.8 |
| `source_synthesizer.py` | 4.2KB | ⚠️ Unknown | Verify vs §5.9 |
| `context_compressor.py` | 10.5KB | ⚠️ Unknown | Verify vs §14 |

**Total effort (verification):** ~2 giorni

---

## 🎯 **UPDATED IMPLEMENTATION ROADMAP**

### **Phase 1: MVP Critical Path (Week 1-2) — 10d**

**Goal:** End-to-end pipeline: topic → 1 approved section

#### **Week 1: Entry Point + Research Pipeline (5d)**

**Day 1: Entry Point**
- [ ] Task 1.1: Implement `preflight.py` (entry validation, state init)
- [ ] Task 1.2: Implement `budget/estimator.py` (pre-flight cost estimation)
- [ ] Task 1.3: Implement `await_outline.py` (human approval gate stub)

**Day 2-3: Verify Research Pipeline**
- [ ] Task 1.4: **Verify** `researcher.py` completeness (§5.1)
- [ ] Task 1.5: **Verify** `citation_manager.py` + `citation_verifier.py` (§24)
- [ ] Task 1.6: **Verify** `source_sanitizer.py` + `source_synthesizer.py` (§5.8-5.9)
- [ ] Task 1.7: Fix any gaps found in verification

**Day 4-5: Post-Writer Pipeline**
- [ ] Task 1.8: Implement `post_draft_analyzer.py` (gap detection, iteration==1 guard)
- [ ] Task 1.9: Implement `metrics_collector.py` (draft metrics + embeddings)
- [ ] Task 1.10: **Verify** `researcher_targeted.py` (§5.3)

#### **Week 2: Infrastructure + Output (5d)**

**Day 6-7: Config + Storage**
- [ ] Task 1.11: Implement `config/presets.py` (Economy/Balanced/Premium)
- [ ] Task 1.12: Implement `config/style_profiles.py` (L1/L2 rules §26)
- [ ] Task 1.13: Implement `storage/db.py` (PostgreSQL checkpoint interface)
- [ ] Task 1.14: Implement `storage/s3.py` (MinIO/S3 document storage)
- [ ] Task 1.15: Implement `security/sanitizer.py` (input validation)

**Day 8-9: Output Pipeline**
- [ ] Task 1.16: Implement `publisher.py` (Markdown/DOCX/PDF output)
- [ ] Task 1.17: Implement `feedback_collector.py` (post-delivery metrics stub)

**Day 10: Integration Testing**
- [ ] Task 1.18: End-to-end test: topic → 1 approved section
- [ ] Task 1.19: Measure baseline: cost, latency, cache hit rate
- [ ] Task 1.20: Fix integration bugs

**Deliverable Phase 1:**
```
✅ MVP Pipeline Working:
   Topic → Preflight → BudgetEstimator → Planner → Researcher 
   → Citation* → Sanitizer → Synthesizer → ShineAdapter 
   → Writer → Jury (9 judges) → Aggregator → SectionCheckpoint
   → Publisher → Output

✅ Metrics:
   - Cost per section: ~$2-5 (target: <$3 with §29.1)
   - Latency: ~3-5min (1 section, no retries)
   - Cache hit rate: ≥50% (Writer + Jury cached prompts)
   - SHINE activation: 100% Premium, 0% Economy
```

---

### **Phase 2: Iteration Loop (Week 3) — 5d**

**Goal:** Reflector → Writer loop + oscillation detection

**Day 11-12: Advanced Routing**
- [ ] Task 2.1: Verify `context_compressor.py` logic (§14)
- [ ] Task 2.2: Implement `span_editor.py` (surgical edits §12.6)
- [ ] Task 2.3: Implement `diff_merger.py` (merge edits §12.7)

**Day 13-15: Iteration Guards**
- [ ] Task 2.4: Test Reflector → Writer loop (already implemented)
- [ ] Task 2.5: Test OscillationCheck (already implemented)
- [ ] Task 2.6: Implement `await_human.py` (escalation gate)
- [ ] Task 2.7: E2E test: 1 section with 1-3 iterations

**Deliverable Phase 2:**
```
✅ Iteration Loop Working:
   Aggregator → Reflector → (SpanEditor|Writer) → Jury → Aggregator
   Max 4 iterations before force_approve

✅ Metrics:
   - Avg iterations to approval: <2 (target)
   - Oscillation detection rate: 0 false positives
```

---

### **Phase 3: Advanced Features (Week 4-5) — 10d**

**Goal:** Panel Discussion + Coherence Guard + QA

**Day 16-18: Panel Discussion (§11)**
- [ ] Task 3.1: Implement `panel_discussion.py` (CSS<0.50 fallback)
- [ ] Task 3.2: Test panel self-loop (max 2 rounds)

**Day 19-20: Coherence + QA**
- [ ] Task 3.3: Implement `coherence_guard.py` (cross-section conflicts §5.17)
- [ ] Task 3.4: Implement `post_qa.py` (final validation §5.15)
- [ ] Task 3.5: Implement `length_adjuster.py` (word count fix §5.22)

**Day 21-25: Multi-Section Pipeline**
- [ ] Task 3.6: Test section loop (3-5 sections)
- [ ] Task 3.7: Test context compression between sections
- [ ] Task 3.8: Measure full document cost (10-20K words)

**Deliverable Phase 3:**
```
✅ Multi-Section Pipeline:
   - 3-5 sections sequentially
   - Context compression working
   - Panel Discussion activates on CSS<0.50
   - Coherence Guard prevents contradictions

✅ Metrics:
   - Cost per 10K-word document: <$50 (target: $30-40 with §29)
   - Total latency: <30min (5 sections, avg 2 iterations each)
```

---

### **Phase 4: Production Hardening (Week 6+) — Ongoing**

**Goal:** Error handling, monitoring, deployment

- [ ] Task 4.1: Add error handling to all nodes (try/except + fallback)
- [ ] Task 4.2: Implement logging + metrics (Prometheus/Grafana)
- [ ] Task 4.3: Docker deployment (docker-compose.yml)
- [ ] Task 4.4: CI/CD pipeline (GitHub Actions)
- [ ] Task 4.5: Load testing (10 concurrent documents)

---

## 🚀 **IMMEDIATE NEXT STEPS (This Week)**

### **Priority 1: Verification (Today, 2h)**

Run these checks **immediately** to assess actual completion:

```bash
# 1. Check if existing nodes are stubs or real implementations
for f in researcher citation_manager citation_verifier source_sanitizer source_synthesizer context_compressor researcher_targeted; do
    echo "=== Checking $f.py ==="
    grep -E "def.*node|return.*dict|pass|TODO|STUB" src/graph/nodes/$f.py | head -10
done

# 2. Test graph compilation
python -c "from src.graph.graph import build_graph; g = build_graph(); print('Graph OK')"

# 3. Check state schema
python -c "from src.graph.state import DocumentState; print('State fields:', len(DocumentState.__annotations__))"

# 4. Test RAG connector
python -c "from src.connectors.memvid_connector import MemvidConnector; print('Memvid OK')"
```

**Expected output:**
- If nodes contain `pass` or `TODO` → They are stubs, prioritize implementation
- If graph compiles → Topology is correct
- If state has ~50 fields → Schema is complete
- If memvid imports → RAG infrastructure ready

---

### **Priority 2: Implement Critical Stubs (Days 1-5)**

**Start with these 5 blockers:**

1. **Preflight** (entry point) — blocks everything
2. **BudgetEstimator** (cost gate) — blocks everything
3. **PostDraftAnalyzer** (gap detection) — blocks iteration
4. **MetricsCollector** (embeddings) — blocks oscillation detection
5. **Publisher** (output) — blocks deliverable

**Implementation order:**
```
Day 1: Preflight + BudgetEstimator (sequential dependency)
Day 2: PostDraftAnalyzer + MetricsCollector (parallel)
Day 3: Publisher (parallel with Day 4-5)
Day 4-5: Verify research pipeline nodes (7 files)
```

---

### **Priority 3: Integration Test (Day 10)**

**Goal:** Run end-to-end MVP once to validate all connections.

**Test case:**
```python
# tests/integration/test_mvp_e2e.py
def test_mvp_single_section():
    state = {
        "topic": "Machine learning basics",
        "target_words": 1000,
        "quality_preset": "Premium",
        "style_profile": "academic"
    }
    
    graph = build_graph()
    result = graph.invoke(state)
    
    # Assertions
    assert len(result["approved_sections"]) == 1
    assert 900 <= result["approved_sections"][0]["word_count"] <= 1100
    assert result["aggregator_verdict"]["verdict_type"] == "APPROVED"
    assert result["budget"]["spent_dollars"] < 5.0  # Cost gate
```

**If test fails:**
- Debug node by node (print state after each node)
- Check LLM API responses (verify no rate limits)
- Verify state updates (check all required keys returned)

---

## 📋 **EFFORT SUMMARY**

| Phase | Tasks | Effort | ETA |
|-------|-------|--------|-----|
| **Verification** | Check 7 nodes | 2d | Day 1-2 |
| **Phase 1 (MVP)** | 20 tasks | 10d | Week 1-2 |
| **Phase 2 (Iteration)** | 7 tasks | 5d | Week 3 |
| **Phase 3 (Advanced)** | 8 tasks | 10d | Week 4-5 |
| **Phase 4 (Production)** | Ongoing | ∞ | Week 6+ |
| **TOTAL (MVP)** | | **12d** | **2.5 weeks** |
| **TOTAL (Full)** | | **27d** | **5-6 weeks** |

---

## 🎯 **SUCCESS CRITERIA**

### **MVP Ready (Phase 1 Complete):**
- ✅ End-to-end: topic → 1 approved section works
- ✅ Cost per section: <$3 (with §29.1 caching)
- ✅ Cache hit rate: ≥50%
- ✅ SHINE activation: 100% on Premium preset
- ✅ No critical errors in logs

### **Production Ready (Phase 3 Complete):**
- ✅ Multi-section documents (3-5 sections) work
- ✅ Cost per 10K-word doc: <$50
- ✅ Total latency: <30min (5 sections)
- ✅ Panel Discussion activates correctly
- ✅ Coherence Guard prevents contradictions
- ✅ All 32 nodes implemented (no stubs)

---

## 📝 **NOTES FOR CLAUDE OPUS 4**

### **Context You Already Have:**

You have access to:
- ✅ Full repository structure (`src/`, `docs/`, `tests/`)
- ✅ Existing implementations (25 nodes already coded)
- ✅ Complete spec files (39 markdown files in `docs/`)
- ✅ Test suite (RAG + SHINE tests working)

### **What You Should Do First:**

1. **Run verification script** (see Priority 1 above) to check which nodes are real vs stubs
2. **Read critical specs:**
   - `docs/04_architecture.md` (graph topology §4.5, state schema §4.6)
   - `docs/05_agents.md` (node specifications §5.1-5.21)
   - `docs/29_performance_optimizations.md` (§29.1 caching, §29.5 state)
3. **Start with Preflight + BudgetEstimator** (blocking everything else)
4. **Test incrementally** after each node (don't wait for full pipeline)

### **Implementation Pattern (All Nodes):**

```python
"""NodeName agent (§X.Y spec reference)."""

from src.llm.client import llm_client
from src.graph.state import DocumentState
import logging

logger = logging.getLogger(__name__)

def node_name_node(state: DocumentState) -> dict:
    """Brief description matching §X.Y spec.
    
    Args:
        state: DocumentState with required fields [list them]
    
    Returns:
        dict with updated keys: [list them]
    """
    
    # 1. Extract inputs from state
    input_a = state["key_a"]
    input_b = state.get("optional_key", default_value)
    
    # 2. Main logic (call LLM if needed)
    try:
        response = llm_client.call(
            model="...",  # See §28 for model assignment
            system=[...],  # §29.1: use cache_control for repeated blocks
            messages=[...],
            temperature=0.3,
            max_tokens=4096
        )
        result = parse_response(response["text"])
    except Exception as e:
        logger.error(f"Node failed: {e}")
        # Fallback: return safe defaults
        result = get_fallback_result()
    
    # 3. Return state updates
    return {
        "output_key_1": result,
        "output_key_2": computed_value,
    }
```

### **Key Constraints:**

1. **Always use `llm_client.call()`** — never call APIs directly
2. **System prompts must use cache_control** (§29.1) for repeated blocks
3. **State updates are immutable** — return dict with changed keys only
4. **All LLM calls need try/except** — graceful degradation required
5. **Verify specs before coding** — don't guess implementation details

### **Common Pitfalls:**

❌ **DON'T:**
- Mutate `state` directly (it's immutable)
- Call Anthropic/OpenAI APIs directly (breaks cost tracking)
- Implement features not in specs (YAGNI principle)
- Skip error handling (production requires resilience)

✅ **DO:**
- Read referenced spec section before coding
- Copy patterns from existing nodes (consistency matters)
- Test with mock data before full pipeline
- Log important decisions (debugging aid)

---

## 🔗 **REFERENCES**

**Key Spec Files:**
- Architecture: `docs/04_architecture.md`
- Agents: `docs/05_agents.md`
- Jury System: `docs/08_jury_system.md`
- Aggregator: `docs/09_css_aggregator.md`
- Reflector: `docs/12_reflector.md`
- Budget: `docs/19_budget_controller.md`
- Style: `docs/26_style_enforcement.md` (if exists)
- Models: `docs/28_llm_assignments.md`
- Optimizations: `docs/29_performance_optimizations.md`
- RAG+SHINE: `docs/RAG_SHINE_INTEGRATION.md`

**Existing Code:**
- State: `src/graph/state.py`
- Graph: `src/graph/graph.py`
- LLM Client: `src/llm/client.py`
- Example Nodes: `src/graph/nodes/writer.py`, `src/graph/nodes/jury.py`

**Tests:**
- Unit: `tests/unit/test_*.py`
- Integration: `tests/integration/test_*.py`
- E2E: `tests/test_rag_shine_e2e.py`

---

**Last updated:** 2026-02-23 15:50 CET  
**Status:** 75% complete, 25 giorni to MVP  
**Next milestone:** Phase 1 complete (MVP pipeline working)