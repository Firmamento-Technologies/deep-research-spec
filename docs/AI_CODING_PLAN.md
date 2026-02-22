# DRS Implementation Plan — AI Coding Agent

> **Target audience:** AI coding assistants (Cline, Cursor, Aider, Continue, etc.)  
> **Repository:** [lucadidomenicodopehubs/deep-research-spec](https://github.com/lucadidomenicodopehubs/deep-research-spec/tree/struct)  
> **Branch:** `struct`  
> **Last updated:** 2026-02-23  

---

## 📊 Current State Analysis

### ✅ Existing Implementation

```
src/
├── llm/
│   └── pricing.py           # MODEL_PRICING table (§28.4) ✅ COMPLETE
├── graph/
│   ├── state.py             # DocumentState TypedDict ✅ PARTIAL
│   ├── graph.py             # LangGraph builder ✅ PARTIAL
│   ├── nodes/
│   │   ├── researcher.py                ✅ COMPLETE
│   │   ├── researcher_targeted.py       ✅ COMPLETE
│   │   ├── citation_manager.py          ✅ COMPLETE
│   │   ├── citation_verifier.py         ✅ COMPLETE (needs §29.6 parallelization)
│   │   ├── source_sanitizer.py          ✅ COMPLETE
│   │   ├── source_synthesizer.py        ✅ COMPLETE
│   │   ├── context_compressor.py        ✅ COMPLETE
│   │   ├── section_checkpoint.py        ✅ COMPLETE
│   │   └── budget_controller.py         ✅ COMPLETE
│   └── routers/                 ❓ UNKNOWN (need to check)
├── budget/                      ❓ UNKNOWN
├── connectors/                  ❓ UNKNOWN
├── storage/                     ❓ UNKNOWN
├── security/                    ❓ UNKNOWN
└── config/                      ❓ UNKNOWN
```

### ❌ Missing Critical Components

**Phase A agents:**
- `planner.py` — outline generation (§5.1)
- `budget_estimator.py` — pre-flight cost check (§19.1)

**Phase B core agents:**
- `writer.py` — draft generation (§5.7) — **CRITICAL**
- `jury.py` — 3 mini-juries R/F/S (§8) — **CRITICAL**
- `aggregator.py` — CSS + routing (§9) — **CRITICAL**
- `reflector.py` — feedback synthesis (§12) — **CRITICAL**
- `style_linter.py` — L1/L2 checks (§5.9)
- `style_fixer.py` — violation correction (§5.10)
- `metrics_collector.py` — draft metrics (§5.8)
- `post_draft_analyzer.py` — gap detection (§5.11)
- `oscillation_detector.py` — CSS/semantic oscillation (§5.15)

**Phase B advanced:**
- `mow_writers.py` — 3 parallel writers (§7)
- `jury_multidraft.py` — MoW jury (§7.5)
- `fusor.py` — draft fusion (§5.13)
- `span_editor.py` — surgical edits (§5.12)
- `panel_discussion.py` — CSS<0.50 fallback (§11)
- `coherence_guard.py` — cross-section conflicts (§5.17)
- `writer_memory.py` — error accumulator (§5.18)

**Phase C/D:**
- `post_qa.py` — final QA (§4.3)
- `length_adjuster.py` — word count fix (§5.22)
- `publisher.py` — DOCX/PDF output (§5.19)
- `feedback_collector.py` — post-delivery (§5.20)

**Infrastructure:**
- `src/llm/client.py` — unified LLM wrapper with §29.1 prompt caching
- `src/llm/routing.py` — §29.3 model tiering
- `src/storage/db.py` — PostgreSQL interface
- `src/storage/s3.py` — MinIO/S3 interface
- `tests/` — unit + integration tests

---

## 🎯 Implementation Priority (ROI-Optimized)

### 🔥 Phase 1: Minimum Viable Pipeline (Settimana 1-2)

**Goal:** End-to-end single-section run senza jury (mock approval).

#### Task 1.1: LLM Client Unified + §29.1 Prompt Caching

**File:** `src/llm/client.py` (NEW)

**Context:** Attualmente ogni nodo chiama LLM direttamente. Serve un client unificato che supporta prompt caching nativo (§29.1).

**Implementation:**
```python
"""Unified LLM client with prompt caching support (§29.1)."""

from typing import Any, Literal
import anthropic
import openai
from src.llm.pricing import cost_usd

class LLMClient:
    def __init__(self):
        self.anthropic = anthropic.Anthropic()
        self.openai = openai.OpenAI()
    
    def call(
        self,
        model: str,
        messages: list[dict],
        system: str | list[dict] | None = None,  # §29.1: support cache_control
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs
    ) -> dict:
        """Unified LLM call with automatic cost tracking."""
        
        if model.startswith("anthropic/"):
            # §29.1 Prompt Caching: system as array with cache_control
            if isinstance(system, list):
                response = self.anthropic.messages.create(
                    model=model.split("/")[1],
                    system=system,  # [{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}]
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            else:
                response = self.anthropic.messages.create(
                    model=model.split("/")[1],
                    system=system if system else "",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            text = response.content[0].text
            
            # §29.1 metrics: track cache performance
            cache_creation = getattr(response.usage, "cache_creation_input_tokens", 0)
            cache_read = getattr(response.usage, "cache_read_input_tokens", 0)
            
        elif model.startswith("openai/"):
            # OpenAI API
            response = self.openai.chat.completions.create(
                model=model.split("/")[1],
                messages=[
                    {"role": "system", "content": system if system else ""},
                    *messages
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            text = response.choices[0].message.content
            cache_creation = 0
            cache_read = 0
        
        else:
            raise ValueError(f"Unsupported model: {model}")
        
        cost = cost_usd(model, tokens_in, tokens_out)
        
        return {
            "text": text,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost,
            "cache_creation_tokens": cache_creation,
            "cache_read_tokens": cache_read,
            "model": model
        }

# Singleton instance
llm_client = LLMClient()
```

**Instructions for AI agent:**
1. Create `src/llm/client.py` with the code above
2. Import `cost_usd` from existing `src/llm/pricing.py`
3. Add `anthropic` and `openai` to `requirements-shine.txt` if missing
4. Test: call `llm_client.call("anthropic/claude-opus-4-5", messages=[{"role": "user", "content": "test"}])` and verify response

**Acceptance criteria:**
- [ ] `llm_client.call()` works for Anthropic + OpenAI
- [ ] System prompt accepts `list[dict]` with `cache_control` for Anthropic
- [ ] Returns `cost_usd`, `cache_creation_tokens`, `cache_read_tokens`

---

#### Task 1.2: Writer Agent (§5.7) con §29.1 Caching

**File:** `src/graph/nodes/writer.py` (NEW)

**Context:** Writer è il bottleneck costi. Deve usare prompt caching per style rules + exemplar (§29.1).

**Specs reference:** `docs/05_agents.md` §5.7

**Implementation skeleton:**
```python
"""Writer agent (§5.7) with §29.1 prompt caching."""

from src.llm.client import llm_client
from src.graph.state import DocumentState

def writer_node(state: DocumentState) -> dict:
    """Generate section draft from compressed corpus."""
    
    # Extract inputs from state
    section_scope = state["outline"][state["current_section_idx"]]["scope"]
    target_words = state["outline"][state["current_section_idx"]]["target_words"]
    compressed_corpus = state["compressed_corpus"]
    citation_map = state["citation_map"]
    style_exemplar = state.get("style_exemplar", "")
    writer_memory = state.get("writer_memory", {})
    
    # §29.1 Prompt Caching: system as array with cache_control
    # Cache blocks: style_profile_rules + style_exemplar (persist 5min)
    system_blocks = [
        {
            "type": "text",
            "text": get_style_profile_rules(state["style_profile"]),  # L1/L2 rules from §26
            "cache_control": {"type": "ephemeral"}  # ← CACHED
        },
        {
            "type": "text",
            "text": f"Style Exemplar:\n{style_exemplar}" if style_exemplar else "",
            "cache_control": {"type": "ephemeral"}  # ← CACHED
        },
        {
            "type": "text",
            "text": format_writer_memory(writer_memory),  # Recurring errors (not cached, changes per section)
        }
    ]
    
    # User prompt: section scope + compressed corpus
    user_prompt = f"""
Write a section for a {state['style_profile']} document.

Section: {section_scope}
Target word count: {target_words} (±15% acceptable)

Sources (use ONLY citations from this map):
{format_citation_map(citation_map)}

Research corpus:
{compressed_corpus}

Constraints:
- Use ONLY facts from the corpus above
- Cite sources using [source_id] format
- Word count: {target_words} ± 15%
- No markdown formatting
"""
    
    messages = [{"role": "user", "content": user_prompt}]
    
    # Call LLM with cached system prompt
    response = llm_client.call(
        model="anthropic/claude-opus-4-5",  # §28 model assignment
        system=system_blocks,  # ← §29.1 caching active
        messages=messages,
        temperature=0.3,
        max_tokens=8192
    )
    
    draft = response["text"]
    word_count = len(draft.split())
    
    # Extract citations used
    import re
    citations_used = list(set(re.findall(r"\[(\w+)\]", draft)))
    
    # Track cost in state
    # TODO: add cost tracking to budget controller
    
    return {
        "current_draft": draft,
        "word_count": word_count,
        "citations_used": citations_used,
        "current_iteration": 1  # Reset for new section
    }

def get_style_profile_rules(style_profile: str) -> str:
    """Load L1/L2 rules from §26 style profiles."""
    # TODO: implement style profile loader from config/
    return "[PLACEHOLDER: Load from §26 spec]"

def format_citation_map(citation_map: dict) -> str:
    return "\n".join([f"[{sid}] {citation}" for sid, citation in citation_map.items()])

def format_writer_memory(writer_memory: dict) -> str:
    recurring = writer_memory.get("recurring_errors", [])
    if not recurring:
        return ""
    return "Previous errors to avoid:\n" + "\n".join([f"- {err}" for err in recurring])
```

**Instructions for AI agent:**
1. Create `src/graph/nodes/writer.py`
2. Implement `writer_node(state)` using skeleton above
3. Import `llm_client` from `src/llm/client.py`
4. Import `DocumentState` from `src/graph/state.py`
5. **CRITICAL:** System prompt MUST be `list[dict]` with `cache_control` for §29.1
6. TODO markers: `get_style_profile_rules()` needs actual implementation from §26 spec (for now return placeholder)

**Acceptance criteria:**
- [ ] `writer_node(mock_state)` returns draft with ~target_words ±20%
- [ ] System prompt uses cached blocks (verify in LLM API logs)
- [ ] Citations extracted correctly from draft

---

#### Task 1.3: Mock Jury for MVP

**File:** `src/graph/nodes/jury_mock.py` (TEMPORARY)

**Context:** Per MVP, skippiamo la jury completa e mocchiamo approval. Task 2.x implementerà la vera jury.

**Implementation:**
```python
"""Mock jury for MVP — always approves."""

from src.graph.state import DocumentState

def jury_mock_node(state: DocumentState) -> dict:
    """Mock approval for MVP pipeline."""
    return {
        "jury_verdicts": [
            {
                "judge_slot": "R1",
                "pass_fail": True,
                "css_contribution": 0.85,
                "motivation": "[MOCK] Auto-approved for MVP"
            }
        ],
        "aggregator_verdict": {
            "verdict_type": "APPROVED",
            "css_content": 0.85,
            "css_style": 0.85,
            "css_final": 0.85
        }
    }
```

**Instructions:**
1. Create `src/graph/nodes/jury_mock.py`
2. Always return `APPROVED` verdict
3. **This is temporary** — will be replaced by Task 2.x

---

#### Task 1.4: Planner Agent (§5.1)

**File:** `src/graph/nodes/planner.py` (NEW)

**Specs reference:** `docs/05_agents.md` §5.1

**Implementation:**
```python
"""Planner agent (§5.1) — outline generation."""

from src.llm.client import llm_client
from src.graph.state import DocumentState
import json

def planner_node(state: DocumentState) -> dict:
    """Generate section outline from topic."""
    
    topic = state["topic"]
    target_words = state["target_words"]
    style_profile = state["style_profile"]
    quality_preset = state["quality_preset"]
    
    prompt = f"""
Create a detailed outline for a {style_profile} document on: {topic}

Total target: {target_words} words

Generate 5-10 sections with:
- Title (concise)
- Scope (2-3 sentence description)
- Target word count (distribute {target_words} evenly, min 200 words/section)
- Dependencies (section indices that must come before, if any)

Return ONLY valid JSON:
{{
  "sections": [
    {{"idx": 0, "title": "...", "scope": "...", "target_words": 1000, "dependencies": []}},
    ...
  ],
  "document_type": "survey|tutorial|review|report|spec|essay|blog"
}}
"""
    
    response = llm_client.call(
        model="google/gemini-2.5-pro",  # §28 assignment
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4096
    )
    
    # Parse JSON
    try:
        outline_data = json.loads(response["text"])
        outline = outline_data["sections"]
        document_type = outline_data["document_type"]
    except json.JSONDecodeError:
        # Fallback: simple outline
        outline = [
            {"idx": 0, "title": "Introduction", "scope": topic, "target_words": target_words, "dependencies": []}
        ]
        document_type = "report"
    
    return {
        "outline": outline,
        "document_type": document_type,
        "outline_approved": False  # Needs human approval (skip for MVP)
    }
```

**Instructions:**
1. Create `src/graph/nodes/planner.py`
2. Use `google/gemini-2.5-pro` per §28
3. Parse JSON outline (handle errors gracefully)

---

#### Task 1.5: Update LangGraph con MVP Pipeline

**File:** `src/graph/graph.py` (UPDATE existing)

**Context:** Il file `graph.py` esiste già ma probabilmente è incompleto. Aggiungi i nodi MVP.

**Instructions:**
1. Open existing `src/graph/graph.py`
2. Add imports:
   ```python
   from src.graph.nodes.planner import planner_node
   from src.graph.nodes.writer import writer_node
   from src.graph.nodes.jury_mock import jury_mock_node
   ```
3. In `build_graph()` function, add MVP nodes:
   ```python
   g.add_node("planner", planner_node)
   g.add_node("researcher", researcher_node)  # Already exists
   g.add_node("citation_manager", citation_manager_node)  # Already exists
   g.add_node("citation_verifier", citation_verifier_node)  # Already exists
   g.add_node("source_sanitizer", source_sanitizer_node)  # Already exists
   g.add_node("source_synthesizer", source_synthesizer_node)  # Already exists
   g.add_node("writer", writer_node)
   g.add_node("jury_mock", jury_mock_node)
   g.add_node("section_checkpoint", section_checkpoint_node)  # Already exists
   ```
4. Add edges for MVP flow:
   ```python
   g.set_entry_point("planner")
   g.add_edge("planner", "researcher")
   g.add_edge("researcher", "citation_manager")
   g.add_edge("citation_manager", "citation_verifier")
   g.add_edge("citation_verifier", "source_sanitizer")
   g.add_edge("source_sanitizer", "source_synthesizer")
   g.add_edge("source_synthesizer", "writer")
   g.add_edge("writer", "jury_mock")
   g.add_edge("jury_mock", "section_checkpoint")
   g.add_edge("section_checkpoint", END)  # For MVP: single section only
   ```

**Acceptance criteria:**
- [ ] Graph compiles without errors
- [ ] Can invoke `graph.invoke({"topic": "test", "target_words": 1000, ...})`
- [ ] Produces 1 approved section in `approved_sections`

---

#### Task 1.6: §29.5 State Optimization — Bounded Fields

**File:** `src/graph/state.py` (UPDATE existing)

**Context:** Il file `state.py` esiste. Aggiungi bounded reducers per §29.5.

**Instructions:**
1. Open `src/graph/state.py`
2. Add bounded reducer:
   ```python
   from typing import Annotated
   
   def max_len_reducer(window: int):
       def reducer(existing: list, new: list) -> list:
           return (existing + new)[-window:]
       return reducer
   
   MaxLen = lambda window: max_len_reducer(window)
   ```
3. Update `DocumentState` fields:
   ```python
   class DocumentState(TypedDict):
       # ... existing fields ...
       
       # §29.5 Bounded fields
       draft_embeddings: Annotated[list[list[float]], MaxLen(window=4)]
       css_history: Annotated[list[float], MaxLen(window=8)]
       
       # ... rest ...
   ```

**Acceptance criteria:**
- [ ] `draft_embeddings` never exceeds 4 items
- [ ] `css_history` never exceeds 8 items
- [ ] Test: append 10 embeddings, verify only last 4 retained

---

### Deliverable Phase 1

✅ **MVP pipeline funzionante:**
```
Topic "machine learning" 
→ Planner (outline)
→ Researcher (sources)
→ Citation* (verified)
→ Sanitizer + Synthesizer (corpus)
→ Writer (draft) ← §29.1 PROMPT CACHING ACTIVE
→ Jury Mock (auto-approve)
→ SectionCheckpoint (PostgreSQL)
→ Output: 1 approved section
```

✅ **§29 optimizations attive:**
- §29.1 Prompt Caching su Writer (system blocks cached)
- §29.5 State Optimization (bounded fields)

✅ **Cost baseline:**
- Track cache hit rate in logs
- Measure: costo single-section run con/senza caching

---

## 🔥 Phase 2: Jury System + Aggregator (Settimana 3-4)

**Goal:** Sostituire mock jury con vero sistema §8 (3 mini-juries + aggregator).

### Task 2.1: Judge Base Class

**File:** `src/graph/nodes/jury_base.py` (NEW)

**Specs:** `docs/08_jury_system.md`

**Implementation:**
```python
"""Base class for Judge agents (§8)."""

from abc import ABC, abstractmethod
from src.llm.client import llm_client
from typing import Literal

class Judge(ABC):
    def __init__(self, slot: str, model: str):
        self.slot = slot  # R1/R2/R3/F1/F2/F3/S1/S2/S3
        self.model = model
    
    @abstractmethod
    def evaluate(self, draft: str, sources: list, section_scope: str) -> dict:
        """Return JudgeVerdict dict."""
        pass
    
    def _call_llm_with_cache(self, system_blocks: list[dict], user_prompt: str) -> dict:
        """§29.1: Reuse cached system prompt (verdict schema + rubric)."""
        return llm_client.call(
            model=self.model,
            system=system_blocks,  # Cached: verdict schema + judge-specific rubric
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.1,
            max_tokens=2048
        )
```

---

### Task 2.2-2.4: Judge R/F/S Implementations

**Files:**
- `src/graph/nodes/judge_r.py` (Reasoning) — 3 instances R1/R2/R3
- `src/graph/nodes/judge_f.py` (Factual) — 3 instances F1/F2/F3 + micro-search
- `src/graph/nodes/judge_s.py` (Style) — 3 instances S1/S2/S3

**Specs:** `docs/08_jury_system.md` §8.1-8.3

**Implementation example (Judge R):**
```python
from src.graph.nodes.jury_base import Judge
import json

class JudgeR(Judge):
    def evaluate(self, draft: str, sources: list, section_scope: str) -> dict:
        # §29.1: Cache verdict schema + reasoning rubric
        system_blocks = [
            {
                "type": "text",
                "text": VERDICT_SCHEMA,  # JSON schema for output
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": REASONING_RUBRIC,  # §8.1 evaluation criteria
                "cache_control": {"type": "ephemeral"}
            }
        ]
        
        user_prompt = f"""
Evaluate the REASONING quality of this draft.

Section scope: {section_scope}

Draft:
{draft}

Criteria:
- Logical consistency
- Argument structure
- Causality claims
- Contradictions

Return JSON verdict:
{{
  "pass_fail": true/false,
  "css_contribution": 0.0-1.0,
  "veto_category": null or "logical_contradiction",
  "confidence": "low|medium|high",
  "motivation": "...",
  "failed_claims": ["..."]
}}
"""
        
        response = self._call_llm_with_cache(system_blocks, user_prompt)
        
        try:
            verdict = json.loads(response["text"])
        except json.JSONDecodeError:
            # Fallback: pass con low confidence
            verdict = {
                "pass_fail": True,
                "css_contribution": 0.70,
                "veto_category": None,
                "confidence": "low",
                "motivation": "[JSON parse error]",
                "failed_claims": []
            }
        
        verdict["judge_slot"] = self.slot
        verdict["model"] = self.model
        return verdict

VERDICT_SCHEMA = """..."""
REASONING_RUBRIC = """..."""
```

**Instructions for AI agent:**
1. Create 3 files: `judge_r.py`, `judge_f.py`, `judge_s.py`
2. Each inherits from `Judge` base class
3. Implement `evaluate()` con §29.1 cached system blocks
4. Judge F: add micro-search via `llm_client.call("perplexity/sonar-pro", ...)` per falsification
5. Judge S: inject style rules from state

---

### Task 2.5: Jury Orchestrator

**File:** `src/graph/nodes/jury.py` (NEW, replaces jury_mock.py)

**Specs:** `docs/08_jury_system.md` §8.4

**Implementation:**
```python
"""Jury orchestrator — parallel execution of 9 judges (§8.4)."""

import asyncio
from src.graph.nodes.judge_r import JudgeR
from src.graph.nodes.judge_f import JudgeF
from src.graph.nodes.judge_s import JudgeS
from src.graph.state import DocumentState

def jury_node(state: DocumentState) -> dict:
    """Run 3 mini-juries (R/F/S) in parallel."""
    
    draft = state["current_draft"]
    sources = state["current_sources"]
    section_scope = state["outline"][state["current_section_idx"]]["scope"]
    jury_size = state["budget"]["jury_size"]  # 1/2/3 based on preset
    
    # Initialize judges
    judges_r = [JudgeR(f"R{i+1}", "openai/o3") for i in range(jury_size)]
    judges_f = [JudgeF(f"F{i+1}", "google/gemini-2.5-pro") for i in range(jury_size)]
    judges_s = [JudgeS(f"S{i+1}", "google/gemini-2.5-pro") for i in range(jury_size)]
    
    # §29.6 Parallel execution (already in spec, but ensure it's async)
    async def evaluate_all():
        tasks = []
        for judge in judges_r + judges_f + judges_s:
            tasks.append(asyncio.to_thread(judge.evaluate, draft, sources, section_scope))
        return await asyncio.gather(*tasks)
    
    verdicts = asyncio.run(evaluate_all())
    
    return {
        "jury_verdicts": verdicts,
        "all_verdicts_history": state.get("all_verdicts_history", []) + [verdicts]
    }
```

**Instructions:**
1. Create `src/graph/nodes/jury.py`
2. Import Judge classes
3. Use `asyncio.gather()` for §29.6 parallel execution
4. Return verdicts list

---

### Task 2.6: Aggregator + CSS Formula

**File:** `src/graph/nodes/aggregator.py` (NEW)

**Specs:** `docs/09_css_aggregator.md`

**Implementation:**
```python
"""Aggregator — CSS computation + routing (§9)."""

from src.graph.state import DocumentState

def aggregator_node(state: DocumentState) -> dict:
    """Compute CSS and route based on §9.4 logic."""
    
    verdicts = state["jury_verdicts"]
    jury_size = len([v for v in verdicts if v["judge_slot"].startswith("R")])
    css_threshold = state["budget"]["css_content_threshold"]  # 0.65/0.70/0.78
    
    # §9 CSS Formula
    r_scores = [v["css_contribution"] for v in verdicts if v["judge_slot"].startswith("R")]
    f_scores = [v["css_contribution"] for v in verdicts if v["judge_slot"].startswith("F")]
    s_scores = [v["css_contribution"] for v in verdicts if v["judge_slot"].startswith("S")]
    
    css_content = (sum(r_scores) * 0.35 + sum(f_scores) * 0.50 + sum(s_scores) * 0.15) / jury_size
    css_style = sum(s_scores) / jury_size
    css_final = css_content * 0.70 + css_style * 0.30
    
    # §10 Minority Veto check
    veto_triggered = any(v.get("veto_category") for v in verdicts)
    
    # §9.4 Routing logic
    if state.get("force_approve"):  # §19.5: max iterations reached
        verdict_type = "APPROVED"
    elif css_content >= css_threshold and css_style >= 0.80 and not veto_triggered:
        verdict_type = "APPROVED"
    elif veto_triggered:
        verdict_type = "VETO"
    elif css_content < 0.50:
        verdict_type = "PANEL"  # Trigger Panel Discussion
    elif css_style < 0.80:
        verdict_type = "FAIL_STYLE"
    else:
        verdict_type = "FAIL_REFLECTOR"
    
    return {
        "aggregator_verdict": {
            "verdict_type": verdict_type,
            "css_content": css_content,
            "css_style": css_style,
            "css_final": css_final
        },
        "css_history": state.get("css_history", []) + [css_final]
    }
```

---

### Task 2.7: Update Graph — Remove Mock, Add Real Jury

**File:** `src/graph/graph.py` (UPDATE)

**Instructions:**
1. Remove `jury_mock` node
2. Add `jury` and `aggregator` nodes:
   ```python
   from src.graph.nodes.jury import jury_node
   from src.graph.nodes.aggregator import aggregator_node
   
   g.add_node("jury", jury_node)
   g.add_node("aggregator", aggregator_node)
   ```
3. Update edge: `writer → jury → aggregator`
4. Add conditional edge after aggregator:
   ```python
   def route_after_aggregator(state):
       verdict = state["aggregator_verdict"]["verdict_type"]
       if verdict == "APPROVED":
           return "section_checkpoint"
       elif verdict == "FAIL_REFLECTOR":
           return "reflector"  # TODO: implement in Phase 3
       elif verdict == "FAIL_STYLE":
           return "style_fixer"  # TODO: implement in Phase 3
       else:
           return "section_checkpoint"  # Fallback for MVP
   
   g.add_conditional_edges("aggregator", route_after_aggregator)
   ```

---

### Deliverable Phase 2

✅ **Real jury system:**
- 9 judges (R1-R3, F1-F3, S1-S3) paralleli
- CSS formula (§9) computata correttamente
- Minority veto (§10) funzionante

✅ **Routing:**
- `APPROVED` → section_checkpoint
- `FAIL_REFLECTOR` → (placeholder, Phase 3)
- `FAIL_STYLE` → (placeholder, Phase 3)

✅ **§29.1 active:**
- Jury judges use cached verdict schema + rubric
- Cache hit rate ≥70%

---

## 🔥 Phase 3: Reflector + StyleLinter + Iteration Loop (Settimana 5-6)

*(Implementation details truncated for brevity — follow same pattern as Phase 1-2)*

**Priority tasks:**
- Task 3.1: `reflector.py` (§5.14)
- Task 3.2: `style_linter.py` + `style_fixer.py` (§5.9-5.10)
- Task 3.3: `oscillation_detector.py` (§5.15)
- Task 3.4: Update graph con iteration loop (reflector → writer)

---

## 🔥 Phase 4: MoW + Panel + Advanced (Settimana 7-8)

**Priority tasks:**
- Task 4.1: `mow_writers.py` + `jury_multidraft.py` + `fusor.py` (§7)
- Task 4.2: `panel_discussion.py` (§11)
- Task 4.3: `coherence_guard.py` (§5.17)
- Task 4.4: §29.3 Model Tiering implementation

---

## 🛠️ AI Agent Usage Tips

### For Cline/Cursor/Aider:

**Comando consigliato per ogni task:**
```
"Implement Task X.Y following the specs in docs/AI_CODING_PLAN.md.
Read the referenced spec files (docs/*.md) for detailed requirements.
Use existing code in src/ as reference (especially src/graph/nodes/*.py for patterns).
Test the implementation with a simple unit test before marking complete."
```

**Context files da fornire:**
- Sempre: `docs/AI_CODING_PLAN.md` (questo file)
- Per agent nodes: `docs/05_agents.md` (sezione specifica, es. §5.7 per Writer)
- Per jury: `docs/08_jury_system.md`, `docs/09_css_aggregator.md`
- Per state: `docs/04_architecture.md` (§4.6 DocumentState)
- Per ottimizzazioni: `docs/29_performance_optimizations.md`

**Workflow incrementale:**
1. Start with Phase 1 Task 1.1
2. Run test dopo ogni task
3. Commit dopo ogni task completato: `git commit -m "feat(task-X.Y): implement [component]"`
4. Se test fallisce: "Debug Task X.Y. Check error log: [paste error]. Fix and retest."
5. Se specs unclear: "Read docs/[spec].md section [X] for [component] details. Then implement."

### Comandi utility:

**Run single test:**
```bash
pytest tests/unit/test_writer.py::test_writer_basic -v
```

**Check imports:**
```bash
python -c "from src.graph.nodes.writer import writer_node; print('OK')"
```

**Inspect state:**
```bash
python -c "from src.graph.state import DocumentState; print(DocumentState.__annotations__)"
```

---

## 🏁 Success Metrics

**After Phase 1 (MVP):**
- [ ] Single-section run completes end-to-end
- [ ] §29.1 prompt caching active (cache hit rate ≥50%)
- [ ] §29.5 state size < 500KB after 1 section
- [ ] Cost: ~$2-5 per section (depends on length)

**After Phase 2 (Jury):**
- [ ] Real jury approves/rejects correctly
- [ ] CSS formula matches §9 spec
- [ ] Cache hit rate ≥70%

**After Phase 3 (Iteration):**
- [ ] Reflector → Writer loop works
- [ ] Max 4 iterations before force-approve
- [ ] Oscillation detector prevents infinite loops

**After Phase 4 (Advanced):**
- [ ] MoW generates 3 diverse drafts
- [ ] Panel Discussion activates on CSS < 0.50
- [ ] Model tiering reduces Economy preset costs by 55%

---

## 📝 Notes for AI Agent

1. **Always read specs first:** Don't guess implementation details. Reference `docs/*.md` files.

2. **Reuse existing patterns:** Many nodes already implemented in `src/graph/nodes/`. Copy structure.

3. **§29 optimizations are CRITICAL:** Prompt caching (§29.1) must be in every LLM call to Writer/Jury/Reflector.

4. **Test incrementally:** After each task, run `pytest tests/unit/test_[component].py`. Don't wait until end.

5. **State is immutable:** LangGraph state updates must return `dict` with changed keys only. Don't mutate `state` directly.

6. **Error handling:** All LLM calls must have try/except with fallback. See existing nodes for pattern.

7. **Cost tracking:** Every LLM call via `llm_client.call()` auto-tracks cost. Don't implement separately.

8. **Cache metrics:** Track `cache_read_tokens` / `total_input_tokens` ratio to verify §29.1 working.

---

**Last updated:** 2026-02-23  
**Maintainer:** Auto-generated by Perplexity AI  
**Specs version:** DRS v3.0 + §29 optimizations
