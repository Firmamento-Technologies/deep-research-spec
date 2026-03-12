# 🛑 This File is Deprecated

## ➡️ Use This Instead:

**📘 [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md)** ← Single Source of Truth

---

## Why the Change?

This file (`CLAUDE_OPUS_4_PROMPT.md`) contained **outdated implementation status** (claimed 75% complete, missing only stubs).

The **actual state** (as of 2026-02-23) requires:
- ✅ Phase 0: RAG + SHINE infrastructure (MemvidConnector, ShineAdapter)
- ✅ Phase 1: MVP pipeline (Writer, Planner, LLM Client with caching)
- ✅ Phase 2: Real jury system (9 judges + aggregator)
- ✅ Phase 3: Iteration loop (Reflector, oscillation detection)

**All details, code skeletons, and acceptance criteria are in:**

👉 **[`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md)**

---

## Quick Start for Claude Opus 4

```markdown
Read and implement following:

https://github.com/lucadidomenicodopehubs/deep-research-spec/blob/struct/docs/AI_CODING_PLAN.md

Start with Phase 0, Task 0.1: MemvidConnector

Supporting docs:
- docs/COST_OPTIMIZATION_ROADMAP.md (why optimizations matter)
- docs/RAG_SHINE_INTEGRATION.md (RAG + SHINE architecture)
- docs/29_performance_optimizations.md (technical specs)
```

---

## Migration Notes

**Old structure** (this file):
- Claimed: "75% complete, 7 stub nodes remaining"
- Missing: RAG integration, SHINE adapter, cost optimizations

**New structure** ([`AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md)):
- Phase 0-4 roadmap with accurate status
- Integrated with Cost Optimization Roadmap (81% reduction)
- Code skeletons with §29.1 prompt caching, §29.5 state optimization
- Cross-references to all spec files

---

**Last updated:** 2026-02-23  
**Maintainer:** Luca Di Domenico (luca.di.domenico@dopehubs.com)  
**Replacement:** [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md)
