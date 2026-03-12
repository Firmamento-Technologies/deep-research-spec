# 🗺️ Documentation Map — DRS Project

> **Purpose:** Navigation guide for all instruction and spec files  
> **Last Updated:** 2026-02-23  

---

## 👁️ Quick Navigation

### For AI Coding Agents (Implementation)

📘 **[`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md)** ← **START HERE**

**This is the ONLY file you need for implementation.**

Contains:
- Phase 0-4 roadmap (RAG+SHINE → MVP → Jury → Iteration → Production)
- Code skeletons for every component
- Acceptance criteria per task
- Test commands
- Integration with cost optimization

---

### For Project Setup (Pre-Implementation)

🔧 **[`CLINE_SETUP_PROMPT.md`](CLINE_SETUP_PROMPT.md)**

**Use this ONLY for:**
- Resolving spec conflicts
- Organizing directory structure
- Creating validation scripts

**After setup, switch to:** [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md)

---

### For Understanding Context

📚 **[`README.md`](README.md)**

High-level overview:
- System architecture
- RAG + SHINE flow
- Performance benchmarks
- Installation instructions

---

## 📊 Supporting Documentation

### Cost Optimization

💰 **[`docs/COST_OPTIMIZATION_ROADMAP.md`](docs/COST_OPTIMIZATION_ROADMAP.md)**

Why optimizations matter:
- Baseline: $13.70/document
- Layer 1 (Week 4): $2.58 (-81%)
- Layer 2 (Week 6): $1.28 (-91%)
- Layer 3 (Week 8): $0.80 (-94%)

**Integration:** Already included in [`AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md) tasks.

---

### Technical Specifications

🔧 **[`docs/29_performance_optimizations.md`](docs/29_performance_optimizations.md)**

Detailed technical specs:
- §29.1 Prompt Caching (Anthropic)
- §29.5 State Optimization (bounded fields)
- §29.3 Model Tiering (cascading)
- §29.6 Parallelization (async)
- §29.7 Distillation (optional)

---

### RAG + SHINE Architecture

🔍 **[`docs/RAG_SHINE_INTEGRATION.md`](docs/RAG_SHINE_INTEGRATION.md)**

System integration:
- Memvid local knowledge base
- SHINE LoRA generation
- Fallback rules
- Benchmarks

---

## 🗂️ Complete Spec Files (docs/)

All 41 specification files are in [`docs/`](docs/) directory:

### Core Architecture
- [`01_vision.md`](docs/01_vision.md) — System vision & constraints
- [`04_architecture.md`](docs/04_architecture.md) — Phases A-D, LangGraph topology
- [`05_agents.md`](docs/05_agents.md) — 21 agent specifications (§5.1-5.21)

### Jury System
- [`08_jury_system.md`](docs/08_jury_system.md) — 3 mini-juries (R/F/S)
- [`09_css_aggregator.md`](docs/09_css_aggregator.md) — CSS formula & routing
- [`10_minority_veto.md`](docs/10_minority_veto.md) — Veto mechanism

### Advanced Features
- [`07_mixture_of_writers.md`](docs/07_mixture_of_writers.md) — MoW + Fusor
- [`11_panel_discussion.md`](docs/11_panel_discussion.md) — CSS<0.50 fallback
- [`12_reflector.md`](docs/12_reflector.md) — Feedback synthesis

### Infrastructure
- [`19_budget_controller.md`](docs/19_budget_controller.md) — Cost tracking
- [`28_llm_assignments.md`](docs/28_llm_assignments.md) — Model routing
- [`14_context_compressor.md`](docs/14_context_compressor.md) — Tiered compression

**Full list:** 41 files in [`docs/`](docs/)

---

## 🚨 Deprecated Files

### ❌ `CLAUDE_OPUS_4_PROMPT.md`

**Status:** Deprecated (now redirect to [`AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md))  
**Reason:** Contained outdated status ("75% complete"), missing RAG+SHINE

### ❌ `DEVELOPMENT_PLAN_2026-02-23.md`

**Status:** Deprecated (now redirect to [`AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md))  
**Reason:** Duplicate content with conflicting implementation status

### ❌ `CLAUDE_OPUS_INSTRUCTIONS.md`

**Status:** Deleted  
**Reason:** Duplicate of [`AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md) created by mistake

---

## 📋 File Status Summary

| File | Status | Purpose |
|------|--------|----------|
| **`docs/AI_CODING_PLAN.md`** | ✅ **CANONICAL** | Implementation roadmap |
| `docs/COST_OPTIMIZATION_ROADMAP.md` | ✅ Active | Cost reduction strategy |
| `docs/RAG_SHINE_INTEGRATION.md` | ✅ Active | RAG+SHINE architecture |
| `docs/29_performance_optimizations.md` | ✅ Active | Technical optimization specs |
| `CLINE_SETUP_PROMPT.md` | ✅ Active | Project setup (pre-implementation) |
| `README.md` | ✅ Active | High-level overview |
| `CLAUDE_OPUS_4_PROMPT.md` | ⚠️ Deprecated | Redirects to AI_CODING_PLAN.md |
| `DEVELOPMENT_PLAN_2026-02-23.md` | ⚠️ Deprecated | Redirects to AI_CODING_PLAN.md |
| `CLAUDE_OPUS_INSTRUCTIONS.md` | ❌ Deleted | Was duplicate |

---

## 🎯 Decision Flow

```
Are you setting up project structure?
└─ YES → Read CLINE_SETUP_PROMPT.md
   └─ After setup → Go to AI_CODING_PLAN.md
└─ NO  → Are you implementing DRS components?
   └─ YES → Read docs/AI_CODING_PLAN.md (START HERE)
      └─ Need cost context? → docs/COST_OPTIMIZATION_ROADMAP.md
      └─ Need tech details? → docs/29_performance_optimizations.md
      └─ Need RAG+SHINE? → docs/RAG_SHINE_INTEGRATION.md
   └─ NO  → Are you understanding the system?
      └─ YES → Read README.md
         └─ Need agent specs? → docs/05_agents.md
         └─ Need architecture? → docs/04_architecture.md
```

---

## 📞 Questions?

**"Which file should I read to start coding?"**  
→ [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md)

**"Where are the cost optimization details?"**  
→ [`docs/COST_OPTIMIZATION_ROADMAP.md`](docs/COST_OPTIMIZATION_ROADMAP.md) (also integrated in AI_CODING_PLAN.md)

**"How do I set up the project?"**  
→ [`CLINE_SETUP_PROMPT.md`](CLINE_SETUP_PROMPT.md) (setup only), then [`AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md) (implementation)

**"What's the system architecture?"**  
→ [`README.md`](README.md) (overview) + [`docs/04_architecture.md`](docs/04_architecture.md) (detailed)

**"Why are there so many instruction files?"**  
→ Historical reasons. **Use only [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md)** for implementation. Others are deprecated or setup-only.

---

## 🔄 Update History

**2026-02-23:**
- Created DOCUMENTATION_MAP.md
- Deprecated CLAUDE_OPUS_4_PROMPT.md → redirect to AI_CODING_PLAN.md
- Deprecated DEVELOPMENT_PLAN_2026-02-23.md → redirect to AI_CODING_PLAN.md
- Deleted duplicate CLAUDE_OPUS_INSTRUCTIONS.md
- Updated CLINE_SETUP_PROMPT.md with AI_CODING_PLAN.md reference
- Established [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md) as **single source of truth**

---

**Maintainer:** Luca Di Domenico (luca.di.domenico@dopehubs.com)  
**Repository:** [lucadidomenicodopehubs/deep-research-spec](https://github.com/lucadidomenicodopehubs/deep-research-spec)  
**Branch:** `struct`
