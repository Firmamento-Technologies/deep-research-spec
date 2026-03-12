# 🛠️ DRS Implementation Guide

> **Single entry point for developers and AI coding agents**

---

## 🎯 Quick Start

### For AI Coding Agents (Claude Opus, Cursor, Cline, etc.)

**📘 START HERE:** [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md)

This file contains:
- ✅ Phase 0-4 implementation roadmap
- ✅ Code skeletons for every component
- ✅ Task-by-task acceptance criteria
- ✅ Test commands
- ✅ Integration with cost optimization

**First command:**
```bash
cat docs/AI_CODING_PLAN.md
# Then implement Phase 0, Task 0.1: MemvidConnector
```

---

## 📚 Documentation Structure

### 🔴 Critical Files (Read First)

| File | Purpose | When to Read |
|------|---------|-------------|
| [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md) | **Implementation roadmap** | ⭐ Start here |
| [`docs/COST_OPTIMIZATION_ROADMAP.md`](docs/COST_OPTIMIZATION_ROADMAP.md) | Cost reduction strategy (81%) | After Phase 0 |
| [`docs/RAG_SHINE_INTEGRATION.md`](docs/RAG_SHINE_INTEGRATION.md) | RAG + SHINE architecture | Phase 0 tasks |
| [`docs/29_performance_optimizations.md`](docs/29_performance_optimizations.md) | Technical optimization specs | Phase 1-3 |

### 🟡 Agent Specifications

| Section | Files | Description |
|---------|-------|-------------|
| Architecture | `docs/04_architecture.md` | System phases, DocumentState schema |
| Agents | `docs/05_agents.md` | 21 agent specs (§5.1-5.22) |
| Jury System | `docs/08_jury_system.md` | 9 judges, CSS formula |
| Aggregator | `docs/09_css_aggregator.md` | Verdict routing logic |
| Budget Control | `docs/19_budget_controller.md` | Cost tracking, alarms |
| LLM Routing | `docs/28_llm_assignments.md` | Model selection per agent |

### 🔵 Reference Files

All other files in [`docs/`](docs/) contain detailed specifications for specific components.

---

## 📅 Implementation Timeline

### Week 1: Phase 0 - RAG + SHINE Foundation
**Goal:** Local knowledge retrieval + parametric compression infrastructure

**Tasks:**
- [x] Task 0.1: `MemvidConnector` — Local RAG
- [ ] Task 0.2: Update `Researcher` — memvid_local priority
- [ ] Task 0.3: `ShineAdapter` — LoRA generation
- [ ] Task 0.4: Update `DocumentState` — Add RAG + SHINE fields
- [ ] Task 0.5: Update `MetricsCollector` — Swap to bge-m3
- [ ] Task 0.6: Update `Graph` — Add SHINE node

**Deliverable:** RAG + SHINE operational with graceful fallbacks

---

### Week 2-3: Phase 1 - MVP Pipeline
**Goal:** End-to-end single-section run with cost baseline

**Tasks:**
- [ ] Task 1.1: `LLMClient` — Unified client with §29.1 prompt caching
- [ ] Task 1.2: `Writer` — Draft generation with SHINE support
- [ ] Task 1.3: `JuryMock` — Temporary auto-approval
- [ ] Task 1.4: `Planner` — Outline generation
- [ ] Task 1.5: Update `Graph` — MVP pipeline
- [ ] Task 1.6: Update `State` — §29.5 bounded fields

**Deliverable:** Topic → 1 approved section. Cost baseline: $2-5/section

---

### Week 4-5: Phase 2 - Real Jury System + Layer 1
**Goal:** Replace mock jury with 9-judge system + prompt caching

**Tasks:**
- [ ] Task 2.1: `JudgeBase` — Base class with caching
- [ ] Task 2.2-2.4: `JudgeR/F/S` — 3 judge types
- [ ] Task 2.5: `Jury` — Parallel orchestrator
- [ ] Task 2.6: `Aggregator` — CSS formula + routing
- [ ] Task 2.7: Update `Graph` — Remove mock, add real jury

**Deliverable:** Real jury works. Cost: $0.20-0.50/section (-81%)

---

### Week 6-7: Phase 3 - Iteration Loop + Layer 2
**Goal:** Reflector-driven improvements + model tiering

**Tasks:**
- [ ] Task 3.1: `Reflector` — Feedback synthesis
- [ ] Task 3.2: `StyleLinter` + `StyleFixer` — L1/L2 checks
- [ ] Task 3.3: `OscillationDetector` — CSS/semantic/whack-a-mole
- [ ] Task 3.4: Update `Graph` — Iteration loop
- [ ] Task 3.5: `ModelTiering` — §29.3 cascading

**Deliverable:** Iteration loop works. Cost: $0.10-0.20/section (-91%)

---

### Week 8+: Phase 4 - Production Ready + Layer 3
**Goal:** Advanced features + distillation

**Tasks:**
- [ ] Task 4.1: `MoW` — Mixture-of-Writers
- [ ] Task 4.2: `PanelDiscussion` — CSS < 0.50 fallback
- [ ] Task 4.3: `CoherenceGuard` — Cross-section conflicts
- [ ] Task 4.4: `Distillation` — §29.7 optional optimization

**Deliverable:** Production-ready. Cost: $0.05-0.15/section Economy (-94%)

---

## ✅ Success Criteria

### After Phase 0 (Week 1)
- [ ] Knowledge base built from `docs/` (>100 chunks)
- [ ] Researcher prioritizes local sources (>80% when KB populated)
- [ ] SHINE adapter runs without errors (fallback OK)
- [ ] bge-m3 embeddings active

### After Phase 1 (Week 2-3)
- [ ] Single-section run completes end-to-end
- [ ] **Baseline cost measured: $2-5/section**
- [ ] State size <500KB
- [ ] Cache hit rate: 0% (baseline, no optimizations yet)

### After Phase 2 (Week 4-5)
- [ ] Real jury with 9 judges works
- [ ] CSS formula matches spec
- [ ] **Cache hit rate: 50%+** (§29.1 active)
- [ ] **Cost: $0.20-0.50/section (-81%)**
- [ ] State size <200KB (§29.5 active)

### After Phase 3 (Week 6-7)
- [ ] Reflector → Writer loop works
- [ ] Max 4 iterations enforced
- [ ] Oscillation detector prevents infinite loops
- [ ] **Model tiering: 60% runs tier1 only**
- [ ] **Cost: $0.10-0.20/section (-91%)**

### After Phase 4 (Week 8+)
- [ ] MoW generates 3 diverse drafts
- [ ] Panel discussion activates correctly
- [ ] **Distillation active (Economy): 95% accuracy**
- [ ] **Cost: $0.05-0.15/section (-94%)**

---

## 🚨 Common Pitfalls

1. **Don't skip Phase 0** — RAG + SHINE are foundation for cost savings
2. **Don't guess implementation** — Read specs in `docs/*.md`
3. **Don't implement optimizations out of order** — Baseline first, then Layer 1, 2, 3
4. **Don't skip tests** — Run `pytest` after each task
5. **Don't mutate state** — LangGraph requires `return dict` updates

---

## 📊 Measurement Commands

**Track cache hit rate:**
```python
from src.llm.client import llm_client
stats = llm_client.get_cache_stats()
print(f"Cache hit rate: {stats['cache_read_tokens'] / stats['total_input_tokens']:.2%}")
```

**Measure state size:**
```python
import sys
from src.graph.state import DocumentState
state = {...}  # Load from checkpoint
print(f"State size: {sys.getsizeof(state) / 1024:.2f} KB")
```

**Cost per section (SQL):**
```sql
SELECT 
    section_idx,
    SUM(cost_usd) as total_cost,
    COUNT(DISTINCT iteration) as iterations
FROM costs
WHERE doc_id = 'doc_abc123'
GROUP BY section_idx;
```

---

## 📞 Questions?

1. **"Where do I start?"** → [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md) Phase 0, Task 0.1
2. **"What code pattern to use?"** → Check existing nodes in `src/graph/nodes/`
3. **"What model for agent X?"** → [`docs/28_llm_assignments.md`](docs/28_llm_assignments.md)
4. **"What fields in DocumentState?"** → [`docs/04_architecture.md`](docs/04_architecture.md) §4.6
5. **"Test failing?"** → `pytest tests/unit/test_X.py -vv`

---

## 📋 File Status Reference

### ✅ Active Files
- [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md) — **Primary implementation guide**
- [`docs/COST_OPTIMIZATION_ROADMAP.md`](docs/COST_OPTIMIZATION_ROADMAP.md) — Cost strategy
- [`docs/RAG_SHINE_INTEGRATION.md`](docs/RAG_SHINE_INTEGRATION.md) — RAG + SHINE specs
- [`docs/29_performance_optimizations.md`](docs/29_performance_optimizations.md) — Technical optimizations
- All other `docs/*.md` files — Component specifications

### 🛑 Deprecated Files (Redirects Only)
- `CLAUDE_OPUS_4_PROMPT.md` → Redirects to AI_CODING_PLAN.md
- `DEVELOPMENT_PLAN_2026-02-23.md` → Redirects to AI_CODING_PLAN.md
- `CLINE_SETUP_PROMPT.md` — Preliminary setup (one-time use)

---

**🚀 Ready to start? Open [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md) and begin with Phase 0!**

---

**Last updated:** 2026-02-23  
**Maintainer:** Luca Di Domenico (luca.di.domenico@dopehubs.com)  
**Repository:** [lucadidomenicodopehubs/deep-research-spec](https://github.com/lucadidomenicodopehubs/deep-research-spec/tree/struct)
