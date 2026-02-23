# DRS Implementation Instructions for Claude Opus 4

## Context

You are implementing the **Deep Research System (DRS)**, an advanced multi-agent document generation pipeline.

**Repository:** https://github.com/lucadidomenicodopehubs/deep-research-spec  
**Branch:** `struct`  
**Your role:** Senior AI engineer implementing the system following detailed specifications

---

## 📋 Required Reading (In Order)

All implementation details are in these files. Read them sequentially:

1. **`docs/AI_CODING_PLAN.md`** ← START HERE
   - Step-by-step implementation roadmap
   - Code skeletons for every component
   - Acceptance criteria per task
   - Test commands

2. **`docs/COST_OPTIMIZATION_ROADMAP.md`**
   - Why optimizations matter (81% cost reduction)
   - Timeline: Week 1-8 with cost targets
   - Layer 1-3 optimization breakdown

3. **`docs/RAG_SHINE_INTEGRATION.md`**
   - Local knowledge base (Memvid) setup
   - SHINE LoRA generation specs
   - Fallback rules

4. **`docs/04_architecture.md`**
   - System architecture overview
   - DocumentState TypedDict (§4.6)
   - Phase A/B/C flow

5. **`docs/05_agents.md`**
   - Agent specifications
   - §5.1 Planner, §5.7 Writer, etc.
   - Input/output contracts

6. **`docs/29_performance_optimizations.md`**
   - Technical optimization specs
   - §29.1 Prompt Caching implementation
   - §29.5 State optimization patterns

---

## 🎯 Your Mission

### Phase 0: RAG + SHINE Infrastructure (Week 1)

Implement **Tasks 0.1 to 0.6** from `docs/AI_CODING_PLAN.md`:

- Task 0.1: `src/connectors/memvid_connector.py` (NEW)
- Task 0.2: Update `src/graph/nodes/researcher.py`
- Task 0.3: `src/graph/nodes/shine_adapter.py` (NEW)
- Task 0.4: Update `src/graph/state.py`
- Task 0.5: Update `src/graph/nodes/metrics_collector.py`
- Task 0.6: Update `src/graph/graph.py`

**Deliverable:** Local RAG operational, SHINE adapter integrated with graceful fallback.

---

### Phase 1: MVP Pipeline (Week 2-3)

Implement **Tasks 1.1 to 1.6** from `docs/AI_CODING_PLAN.md`:

- Task 1.1: `src/llm/client.py` (NEW) ← **CRITICAL: §29.1 Prompt Caching**
- Task 1.2: `src/graph/nodes/writer.py` (NEW)
- Task 1.3: `src/graph/nodes/jury_mock.py` (NEW)
- Task 1.4: `src/graph/nodes/planner.py` (NEW)
- Task 1.5: Update `src/graph/graph.py` (MVP pipeline)
- Task 1.6: Update `src/graph/state.py` ← **CRITICAL: §29.5 State Optimization**

**Deliverable:** End-to-end single-section run completes. Cost baseline: $2-5/section.

---

## 📐 Implementation Rules

1. **Follow specs precisely** - All code skeletons are in `docs/AI_CODING_PLAN.md`
2. **Test after each task** - Commands provided in each task description
3. **Never mutate state** - Return `dict` with updated keys only
4. **Use unified LLM client** - `llm_client.call()` for all LLM interactions
5. **Prompt caching mandatory** - Use `cache_control` in system prompts (§29.1)
6. **Graceful fallbacks** - Every component must handle errors without crashing
7. **No premature optimization** - Week 1-3 = baseline measurement only

---

## ✅ Success Criteria

### After Phase 0 (Week 1):
- [ ] `pytest tests/unit/test_memvid_connector.py` passes
- [ ] Researcher logs show "memvid_local checked first"
- [ ] SHINE adapter node in graph (fallback OK if SHINE not installed)
- [ ] bge-m3 embeddings active in MetricsCollector

### After Phase 1 (Week 2-3):
- [ ] `python -m src.main --topic "machine learning" --target-words 1000 --preset economy` completes
- [ ] Output: 1 approved section in PostgreSQL
- [ ] Cost logged: $2-5/section (baseline)
- [ ] State size <500KB: `sys.getsizeof(state) < 500_000`
- [ ] Cache metrics in logs: `cache_creation_tokens > 0`

---

## 🚀 Getting Started

```bash
# 1. Clone repository
git clone https://github.com/lucadidomenicodopehubs/deep-research-spec.git
cd deep-research-spec
git checkout struct

# 2. Read the implementation plan
cat docs/AI_CODING_PLAN.md

# 3. Start with Task 0.1
# Create src/connectors/memvid_connector.py
# Code skeleton is in docs/AI_CODING_PLAN.md Task 0.1
```

---

## 📞 Questions?

- **"What code pattern should I use?"** → See existing nodes in `src/graph/nodes/`
- **"What model for agent X?"** → See `docs/28_llm_assignments.md` §28.3
- **"What fields in DocumentState?"** → See `docs/04_architecture.md` §4.6
- **"Test failing?"** → Run `pytest tests/unit/test_X.py -vv` for verbose output

---

**All implementation details are in `docs/AI_CODING_PLAN.md`. Follow it step-by-step. Test incrementally. Ask if specs unclear.**

Good luck! 🚀
