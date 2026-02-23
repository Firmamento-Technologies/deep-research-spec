# DRS Implementation Plan — AI Coding Agent

> **Target audience:** AI coding assistants (Cline, Cursor, Aider, Continue, etc.)  
> **Repository:** [lucadidomenicodopehubs/deep-research-spec](https://github.com/lucadidomenicodopehubs/deep-research-spec/tree/struct)  
> **Branch:** `struct`  
> **Last updated:** 2026-02-23 (RAG + SHINE integration + Cost Optimization)  

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

**Phase 0 (NEW — RAG + SHINE):**
- `connectors/memvid_connector.py` — local RAG (§RAG_SHINE_INTEGRATION.md §1)
- `nodes/shine_adapter.py` — LoRA generation (§RAG_SHINE_INTEGRATION.md §2)
- Update `nodes/metrics_collector.py` — swap to bge-m3 embeddings
- `scripts/build_memvid_kb.py` — knowledge base builder ✅ CREATED

**Phase 1 agents:**
- `planner.py` — outline generation (§5.1)
- `budget_estimator.py` — pre-flight cost check (§19.1)

**Phase 2 core agents:**
- `writer.py` — draft generation (§5.7) — **CRITICAL**
- `jury.py` — 3 mini-juries R/F/S (§8) — **CRITICAL**
- `aggregator.py` — CSS + routing (§9) — **CRITICAL**
- `reflector.py` — feedback synthesis (§12) — **CRITICAL**
- `style_linter.py` — L1/L2 checks (§5.9)
- `style_fixer.py` — violation correction (§5.10)
- `metrics_collector.py` — draft metrics (§5.8)
- `post_draft_analyzer.py` — gap detection (§5.11)
- `oscillation_detector.py` — CSS/semantic oscillation (§5.15)

**Phase 3 advanced:**
- `mow_writers.py` — 3 parallel writers (§7)
- `jury_multidraft.py` — MoW jury (§7.5)
- `fusor.py` — draft fusion (§5.13)
- `span_editor.py` — surgical edits (§5.12)
- `panel_discussion.py` — CSS<0.50 fallback (§11)
- `coherence_guard.py` — cross-section conflicts (§5.17)
- `writer_memory.py` — error accumulator (§5.18)

**Phase 4 finalization:**
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

### 🔥 **Phase 0: RAG + SHINE Infrastructure (Week 1) — NEW PRIORITY**

**Goal:** Integrate local knowledge retrieval (Memvid) + parametric compression (SHINE) as foundation for all subsequent phases. Questo riduce i costi del 40% e accelera Writer 5x.

**Reference:** [`docs/RAG_SHINE_INTEGRATION.md`](https://github.com/lucadidomenicodopehubs/deep-research-spec/blob/struct/docs/RAG_SHINE_INTEGRATION.md)

---

#### Task 0.1: MemvidConnector — Local RAG Retrieval

**File:** `src/connectors/memvid_connector.py` (NEW)

**Context:** Prima di chiamare connettori esterni (sonar-pro/Tavily), Researcher deve cercare in knowledge base locale (specs, PDFs, SHINE paper). Questo migliora accuratezza e riduce costi API.

**Specs reference:** `docs/RAG_SHINE_INTEGRATION.md` §1

**Implementation:**
```python
"""MemvidConnector — RAG on local knowledge base (§RAG_SHINE_INTEGRATION §1)."""

from FlagEmbedding import FlagModel
from langchain.vectorstores import Memvid
from typing import TypedDict

class Source(TypedDict):
    sourceid: str
    url: str | None
    title: str
    sourcetype: str  # "uploaded" for local
    reliabilityscore: float
    content: str

class MemvidConnector:
    """RAG on local knowledge base (specs, uploaded PDFs, SHINE paper)."""
    
    def __init__(self, knowledge_path: str = "drs_knowledge.mp4"):
        self.encoder = FlagModel('BAAI/bge-m3', use_fp16=True)
        self.store = Memvid.load(knowledge_path)
    
    def search(self, query: str, k: int = 5) -> list[Source]:
        """Search local knowledge base.
        
        Args:
            query: Search query (section scope or targeted query)
            k: Max results to return
        
        Returns:
            List of Source dicts with sourcetype='uploaded'
        """
        try:
            chunks = self.store.similarity_search(query, k=k)
            return [self._to_source(c) for c in chunks]
        except FileNotFoundError:
            # KB not built yet — return empty (cascade to external connectors)
            return []
    
    def _to_source(self, chunk) -> Source:
        """Convert Memvid chunk to Source TypedDict."""
        return Source(
            sourceid=f"local:{chunk.metadata['doc_id']}:{chunk.metadata['chunk_id']}",
            url=chunk.metadata.get('url'),
            title=chunk.metadata.get('title', 'Local Document'),
            sourcetype="uploaded",
            reliabilityscore=0.90,  # Local sources trusted
            content=chunk.page_content
        )
```

**Instructions for AI agent:**
1. Create `src/connectors/memvid_connector.py` with code above
2. Install dependencies: `pip install FlagEmbedding langchain langchain-memvid`
3. Build test KB: `python scripts/build_memvid_kb.py --input docs/ --output test_kb.mp4`
4. Test:
   ```python
   from src.connectors.memvid_connector import MemvidConnector
   connector = MemvidConnector("test_kb.mp4")
   results = connector.search("What is LoRA?")
   assert len(results) > 0
   assert results[0]["sourcetype"] == "uploaded"
   ```

**Acceptance criteria:**
- [ ] `MemvidConnector.search()` returns list of Source dicts
- [ ] Graceful fallback if KB file missing (returns `[]`)
- [ ] Uses bge-m3 embeddings (multilingual support)
- [ ] Integration with Researcher: add to ENABLED_CONNECTORS list

---

#### Task 0.2: Update Researcher — Add memvid_local Priority

**File:** `src/graph/nodes/researcher.py` (UPDATE existing)

**Context:** Researcher attualmente usa solo connettori esterni. Aggiungi `memvid_local` come **prima priorità** nella cascade.

**Instructions:**
1. Open existing `src/graph/nodes/researcher.py`
2. Import `MemvidConnector`:
   ```python
   from src.connectors.memvid_connector import MemvidConnector
   ```
3. Update `ENABLED_CONNECTORS` list:
   ```python
   ENABLED_CONNECTORS = [
       "memvid_local",  # ← NEW: local knowledge base FIRST
       "sonar-pro",
       "tavily",
       "brave"
   ]
   ```
4. Update `get_connector()` function to handle `memvid_local`:
   ```python
   def get_connector(connector_name: str):
       if connector_name == "memvid_local":
           return MemvidConnector(knowledge_path="drs_knowledge.mp4")
       elif connector_name == "sonar-pro":
           # ... existing logic
   ```
5. Test: Run researcher with query "What is SHINE?", verify local results prioritized

**Acceptance criteria:**
- [ ] `memvid_local` checked first in cascade
- [ ] Falls back to `sonar-pro` if local returns 0 results
- [ ] Deduplication works across local + external sources

---

#### Task 0.3: ShineAdapter Node — LoRA Generation (Optional but High ROI)

**File:** `src/graph/nodes/shine_adapter.py` (NEW)

**Context:** SHINE converte il corpus compresso in LoRA adapter (parametric memory) invece di passarlo come testo nel prompt. Questo riduce i token da 4000-8000 a 200-500 (95%), accelerando Writer 5x e riducendo costi 40%.

**Specs reference:** `docs/RAG_SHINE_INTEGRATION.md` §2

**Implementation:**
```python
"""ShineAdapter — Convert compressedCorpus to LoRA adapter (§RAG_SHINE_INTEGRATION §2)."""

from src.graph.state import DocumentState
import logging

logger = logging.getLogger(__name__)

# Lazy import SHINE (fallback gracefully if not installed)
try:
    from shine import ShineHypernet
    SHINE_AVAILABLE = True
except ImportError:
    logger.warning("SHINE not installed — fallback to text corpus mode")
    SHINE_AVAILABLE = False

class ShineAdapter:
    """Generate LoRA from compressed corpus using SHINE hypernetwork."""
    
    def __init__(self):
        if SHINE_AVAILABLE:
            self.shine = ShineHypernet(
                backbone="Qwen/Qwen2.5-7B",
                device="cuda"  # fallback to CPU if unavailable
            )
        else:
            self.shine = None
    
    def run(self, state: DocumentState) -> dict:
        """Generate LoRA or fallback to text corpus.
        
        Fallback conditions (§RAG_SHINE_INTEGRATION fallback rules):
        - SHINE not installed
        - Quality preset = Economy
        - Section < 400 words
        - Iteration > 1 (retry)
        """
        
        # Skip conditions
        if not SHINE_AVAILABLE:
            logger.info("SHINE unavailable — using text corpus")
            return {"shine_active": False}
        
        if state["config"]["quality_preset"] == "Economy":
            logger.info("Economy preset — skipping SHINE")
            return {"shine_active": False}
        
        section = state["outline"][state["current_section_idx"]]
        if section["target_words"] < 400:
            logger.info("Section <400 words — skipping SHINE (overhead not worth it)")
            return {"shine_active": False}
        
        if state.get("current_iteration", 1) > 1:
            logger.info("Iteration >1 — skipping SHINE (use RAG corpus only)")
            return {"shine_active": False}
        
        # Generate LoRA
        corpus = state.get("compressed_corpus", "")
        if not corpus:
            logger.warning("Empty corpus — skipping SHINE")
            return {"shine_active": False}
        
        try:
            lora = self.shine.generate_lora(corpus, max_length=1150)  # ~0.3s on GPU
            logger.info(f"✅ SHINE LoRA generated for section {state['current_section_idx']}")
            return {
                "shine_lora": lora,
                "shine_active": True
            }
        except Exception as e:
            logger.error(f"SHINE failed: {e} — falling back to text corpus")
            return {"shine_active": False}

# Node function for LangGraph
def shine_adapter_node(state: DocumentState) -> dict:
    adapter = ShineAdapter()
    return adapter.run(state)
```

**Instructions for AI agent:**
1. Create `src/graph/nodes/shine_adapter.py`
2. Install SHINE (optional, GPU required): `git clone https://github.com/Yewei-Liu/SHINE.git && pip install -e SHINE/`
3. Test fallback mode (without SHINE installed):
   ```python
   from src.graph.nodes.shine_adapter import shine_adapter_node
   state = {"config": {"quality_preset": "Premium"}, "compressed_corpus": "test"}
   result = shine_adapter_node(state)
   assert result["shine_active"] is False  # Expected without SHINE
   ```
4. Test with SHINE (if available):
   ```python
   # Same test, but verify shine_active=True and shine_lora is not None
   ```

**Acceptance criteria:**
- [ ] Graceful fallback when SHINE not installed
- [ ] Skips on Economy preset
- [ ] Skips on sections <400 words
- [ ] Generates LoRA successfully on Premium preset (if SHINE installed)
- [ ] Returns `shine_active` boolean flag

---

#### Task 0.4: Update DocumentState — Add RAG + SHINE Fields

**File:** `src/graph/state.py` (UPDATE existing)

**Instructions:**
1. Open `src/graph/state.py`
2. Add new fields to `DocumentState` TypedDict:
   ```python
   class DocumentState(TypedDict):
       # ... existing fields ...
       
       # RAG + SHINE integration (§RAG_SHINE_INTEGRATION)
       shine_active: bool               # True if SHINE generated LoRA
       shine_lora: Any | None          # LoRA adapter from SHINE
       context_lora: Any | None        # LoRA from ContextCompressor (future)
       rag_local_sources: list[Source] # Sources from memvid_local
   ```

**Acceptance criteria:**
- [ ] New fields added without breaking existing code
- [ ] Default values: `shine_active=False`, `shine_lora=None`

---

#### Task 0.5: Update MetricsCollector — Swap to bge-m3 Embeddings

**File:** `src/graph/nodes/metrics_collector.py` (UPDATE existing)

**Context:** Current implementation uses `all-MiniLM-L6-v2` for draft embeddings. Swap to `bge-m3` (multilingual, 2x context, MTEB #1 <500M).

**Specs reference:** `docs/RAG_SHINE_INTEGRATION.md` §3

**Instructions:**
1. Open existing `src/graph/nodes/metrics_collector.py`
2. Replace SentenceTransformer import:
   ```python
   # BEFORE:
   # from sentence_transformers import SentenceTransformer
   # embedder = SentenceTransformer('all-MiniLM-L6-v2')
   
   # AFTER:
   from FlagEmbedding import FlagModel
   embedder = FlagModel('BAAI/bge-m3', use_fp16=True)
   ```
3. Update `compute_embedding()` method (interface unchanged):
   ```python
   def compute_embedding(self, draft: str) -> list[float]:
       return self.embedder.encode(draft).tolist()
   ```
4. Test: Verify OscillationDetector (§5.15) still works (uses cosine similarity on embeddings)

**Acceptance criteria:**
- [ ] Embedding model swapped to bge-m3
- [ ] Interface unchanged (returns `list[float]`)
- [ ] OscillationDetector works without modifications

---

#### Task 0.6: Update Graph — Add ShineAdapter Node

**File:** `src/graph/graph.py` (UPDATE existing)

**Instructions:**
1. Open `src/graph/graph.py`
2. Import ShineAdapter:
   ```python
   from src.graph.nodes.shine_adapter import shine_adapter_node
   ```
3. Add node to graph:
   ```python
   g.add_node("shine_adapter", shine_adapter_node)
   ```
4. **CRITICAL:** Update edge topology:
   ```python
   # BEFORE:
   # g.add_edge("source_synthesizer", "writer")
   
   # AFTER:
   g.add_edge("source_synthesizer", "shine_adapter")  # Synthesizer → SHINE
   g.add_edge("shine_adapter", "writer")               # SHINE → Writer
   ```
5. Test: Compile graph without errors

**Acceptance criteria:**
- [ ] Graph compiles with new node
- [ ] Edge topology: `source_synthesizer → shine_adapter → writer`
- [ ] Graph still works with `shine_active=False` (fallback path)

---

### Deliverable Phase 0

✅ **RAG + SHINE Infrastructure operativa:**
- Local knowledge base (Memvid) interrogabile
- Researcher prioritizza fonti locali
- ShineAdapter integrato con fallback graceful
- bge-m3 embeddings attivi in MetricsCollector

✅ **Performance baseline:**
- Measure: % local sources used (target: >80% quando KB populated)
- Measure: SHINE activation rate (target: 100% on Premium, 0% on Economy)
- Measure: Token reduction (target: 4000→500 quando SHINE active)

✅ **Documentazione:**
- `docs/RAG_SHINE_INTEGRATION.md` è la reference completa
- Tests in `tests/test_memvid_connector.py`, `tests/test_shine_adapter.py`

---

### 🔥 Phase 1: Minimum Viable Pipeline (Week 2-3)

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

#### Task 1.2: Writer Agent (§5.7) con §29.1 Caching + SHINE Support

**File:** `src/graph/nodes/writer.py` (NEW)

**Context:** Writer è il bottleneck costi. Deve:
1. Usare prompt caching per style rules + exemplar (§29.1)
2. Supportare SHINE LoRA quando `shine_active=True`
3. Fallback a `compressed_corpus` quando SHINE inactive

**Specs reference:** `docs/05_agents.md` §5.7 + `docs/RAG_SHINE_INTEGRATION.md` §2

**Implementation skeleton:**
```python
"""Writer agent (§5.7) with §29.1 prompt caching + SHINE support."""

from src.llm.client import llm_client
from src.graph.state import DocumentState
import logging

logger = logging.getLogger(__name__)

def writer_node(state: DocumentState) -> dict:
    """Generate section draft from compressed corpus or SHINE LoRA."""
    
    # Extract inputs from state
    section_scope = state["outline"][state["current_section_idx"]]["scope"]
    target_words = state["outline"][state["current_section_idx"]]["target_words"]
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
    
    # SHINE path check
    shine_active = state.get("shine_active", False)
    
    if shine_active:
        # §RAG_SHINE_INTEGRATION: use LoRA, no corpus in prompt
        logger.info("Writer using SHINE LoRA (no corpus in context)")
        user_prompt = f"""
Write a section for a {state['style_profile']} document.

Section: {section_scope}
Target word count: {target_words} (±15% acceptable)

Sources (use ONLY citations from this map):
{format_citation_map(citation_map)}

Constraints:
- Use ONLY facts from your knowledge (LoRA adapter active)
- Cite sources using [source_id] format
- Word count: {target_words} ± 15%
- No markdown formatting
"""
        # TODO: Apply LoRA to LLM call (requires SHINE integration in llm_client)
        # For now: proceed with normal call (LoRA application is SHINE-specific)
    else:
        # Fallback: standard text corpus path
        compressed_corpus = state.get("compressed_corpus", "")
        logger.info("Writer using text corpus (SHINE inactive)")
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
    
    logger.info(f"Draft generated: {word_count} words, {len(citations_used)} citations")
    
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
6. **CRITICAL:** Check `shine_active` flag to choose LoRA vs corpus path
7. TODO markers: `get_style_profile_rules()` needs actual implementation from §26 spec (for now return placeholder)

**Acceptance criteria:**
- [ ] `writer_node(mock_state)` returns draft with ~target_words ±20%
- [ ] System prompt uses cached blocks (verify in LLM API logs)
- [ ] Citations extracted correctly from draft
- [ ] Works with `shine_active=True` (no corpus in prompt)
- [ ] Works with `shine_active=False` (corpus in prompt)

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
   from src.graph.nodes.shine_adapter import shine_adapter_node
   ```
3. In `build_graph()` function, add MVP nodes:
   ```python
   g.add_node("planner", planner_node)
   g.add_node("researcher", researcher_node)  # Already exists
   g.add_node("citation_manager", citation_manager_node)  # Already exists
   g.add_node("citation_verifier", citation_verifier_node)  # Already exists
   g.add_node("source_sanitizer", source_sanitizer_node)  # Already exists
   g.add_node("source_synthesizer", source_synthesizer_node)  # Already exists
   g.add_node("shine_adapter", shine_adapter_node)  # NEW from Phase 0
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
   g.add_edge("source_synthesizer", "shine_adapter")  # NEW
   g.add_edge("shine_adapter", "writer")              # NEW
   g.add_edge("writer", "jury_mock")
   g.add_edge("jury_mock", "section_checkpoint")
   g.add_edge("section_checkpoint", END)  # For MVP: single section only
   ```

**Acceptance criteria:**
- [ ] Graph compiles without errors
- [ ] Can invoke `graph.invoke({"topic": "test", "target_words": 1000, ...})`
- [ ] Produces 1 approved section in `approved_sections`
- [ ] SHINE adapter runs (fallback OK if SHINE not installed)

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
→ Researcher (sources) ← memvid_local FIRST
→ Citation* (verified)
→ Sanitizer + Synthesizer (corpus)
→ ShineAdapter (LoRA gen or fallback) ← NEW
→ Writer (draft) ← §29.1 PROMPT CACHING + SHINE SUPPORT
→ Jury Mock (auto-approve)
→ SectionCheckpoint (PostgreSQL)
→ Output: 1 approved section
```

✅ **§29 + RAG + SHINE optimizations attive:**
- §29.1 Prompt Caching su Writer (system blocks cached)
- §29.5 State Optimization (bounded fields)
- RAG: memvid_local priority in Researcher
- SHINE: LoRA generation (if available) or graceful fallback

✅ **Cost baseline:**
- Track cache hit rate in logs
- Track SHINE activation rate
- Measure: costo single-section run con/senza caching + SHINE

---

## 🔥 Phase 2: Jury System + Aggregator (Week 4-5)

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

## 🔥 Phase 3: Reflector + StyleLinter + Iteration Loop (Week 6-7)

*(Implementation details truncated for brevity — follow same pattern as Phase 1-2)*

**Priority tasks:**
- Task 3.1: `reflector.py` (§5.14)
- Task 3.2: `style_linter.py` + `style_fixer.py` (§5.9-5.10)
- Task 3.3: `oscillation_detector.py` (§5.15)
- Task 3.4: Update graph con iteration loop (reflector → writer)

---

## 🔥 Phase 4: MoW + Panel + Advanced (Week 8+)

**Priority tasks:**
- Task 4.1: `mow_writers.py` + `jury_multidraft.py` + `fusor.py` (§7)
- Task 4.2: `panel_discussion.py` (§11)
- Task 4.3: `coherence_guard.py` (§5.17)
- Task 4.4: §29.3 Model Tiering implementation

---

## 🔗 INTEGRAZIONE CON COST OPTIMIZATION ROADMAP

Questo piano di sviluppo è **sincronizzato** con [`docs/COST_OPTIMIZATION_ROADMAP.md`](https://github.com/lucadidomenicodopehubs/deep-research-spec/blob/struct/docs/COST_OPTIMIZATION_ROADMAP.md).

### Ottimizzazioni per Phase

| Phase | Week | Ottimizzazioni Integrate | Riferimento | Risparmio Cumulativo |
|-------|------|-------------------------|-------------|---------------------|
| **Phase 0** | 1 | RAG (memvid_local) + SHINE | Task 0.1-0.6 | Baseline |
| **Phase 1** | 2-3 | NESSUNA (baseline measurements) | - | 0% |
| **Phase 2** | 4-5 | ✅ Prompt Caching (§29.1)<br>✅ State Optimization (§29.5) | Task 2.1, 1.6 | **-50%** |
| **Phase 3** | 6-7 | ✅ Model Tiering (§29.3)<br>✅ Parallel Verifier (§29.6) | Task 3.x | **-77%** |
| **Phase 4** | 8+ | 🔄 Distillation (§29.7) — Optional | Task 4.x | **-85%** |

### Task Modificati con Ottimizzazioni

#### ✅ Task 2.1: `jury_base.py` (Week 4) — Layer 1 Caching
**OTTIMIZZAZIONE ATTIVA:** Implementa con **Prompt Caching** fin dall'inizio (§29.1).

```python
class Judge(ABC):
    def _call_llm_with_cache(self, system_blocks: list[dict], user_prompt: str) -> dict:
        # §29.1 Prompt Caching: verdict schema + rubric cached (5min TTL)
        return llm_client.call(
            model=self.model,
            system=system_blocks,  # ← Cached blocks
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.1,
            max_tokens=2048
        )
```

**Expected Result:**
- Cache hit rate: 50%+ on second section
- Cost reduction: -50% vs naive implementation
- Verify in logs: `cache_read_tokens > 0`

---

#### ✅ Task 1.6: `state.py` (Week 2-3) — Layer 1 State Optimization
**OTTIMIZZAZIONE ATTIVA:** Usa **bounded fields** per evitare state bloat (§29.5).

```python
from langgraph.graph.state import Annotated, MaxLen

class DocumentState(TypedDict):
    # Bounded ring buffer (keeps only last 4)
    draft_embeddings: Annotated[list[list[float]], MaxLen(window=4)]
    all_verdicts_history: Annotated[list[list[dict]], MaxLen(window=2)]
```

**Expected Result:**
- State size: <200KB (vs 2.5MB unbounded)
- Checkpoint latency: <150ms
- Verify: `sys.getsizeof(state) < 200_000`

---

#### ✅ Task 2.5: `jury.py` (Week 4-5) — Layer 2 Model Tiering
**OTTIMIZZAZIONE ATTIVA (Week 6-7):** Implementa **Model Tiering con Cascading** (§29.3).

```python
async def call_mini_jury(self, dimension: str) -> list[Verdict]:
    # Step 1: tier1 unanimous check
    verdicts_t1 = await asyncio.gather(*[
        self.call_judge(slot=f"{dimension}{i+1}", tier=1)
        for i in range(3)
    ])
    
    if all_pass(verdicts_t1) or all_fail(verdicts_t1):
        return verdicts_t1  # Cost: $0.0003 (tier1 only)
    
    # Step 2: tier2 for minority only
    # Step 3: tier3 tiebreaker if needed
    # (full implementation in §29.3)
```

**Expected Result:**
- 60% runs stop at tier1 (unanimous)
- Average jury cost: $0.006 (vs $0.09 all-tier3)
- Verify: track `tier_used` metric per mini-jury

---

### Success Criteria Aggiornati

**Phase 0 (Week 1):**
- ✅ RAG + SHINE infrastructure operativa
- ✅ Local sources used: >80% quando KB populated
- ✅ SHINE activation: 100% Premium, 0% Economy

**Phase 1 (Week 2-3):**
- ✅ Single-section run completes end-to-end
- ✅ State size <500KB
- ✅ **Cost: $2-5/section (baseline measurement)**
- ⚠️ Cache hit rate: 0% (no caching yet)

**Phase 2 (Week 4-5):**
- ✅ Real jury with 3×3 judges works
- ✅ **Cache hit rate: 50%+** (§29.1 active)
- ✅ **Cost: $0.20-0.50/section (-81%)**
- ✅ State size: <200KB (§29.5 active)

**Phase 3 (Week 6-7):**
- ✅ Full reflector + oscillation detection
- ✅ **Cache hit rate: 80%+**
- ✅ **Cost: $0.10-0.20/section (-91%)**
- ✅ CitationVerifier: <5s for 12 sources (§29.6 parallel)

**Phase 4 (Week 8+):**
- ✅ Production-ready UI + observability
- ✅ **Cache hit rate: 90%+**
- ✅ **Cost: $0.05-0.15/section (Economy with distillation)**

---

### Measurement Commands

**Track cache hit rate:**
```bash
python -c "
from src.llm.client import llm_client
stats = llm_client.get_cache_stats()
print(f'Cache hit rate: {stats["cache_read_tokens"] / stats["total_input_tokens"]:.2%}')
"
```

**Measure state size:**
```bash
python -c "
import sys
from src.graph.state import DocumentState
state = {...}  # load from checkpoint
print(f'State size: {sys.getsizeof(state) / 1024:.2f} KB')
"
```

**Cost per section (PostgreSQL query):**
```sql
SELECT 
    section_idx,
    SUM(cost_usd) as total_cost,
    COUNT(DISTINCT iteration) as iterations
FROM costs
WHERE doc_id = 'doc_abc123'
GROUP BY section_idx;
```

**Cache metrics per agent:**
```bash
python -c "
from src.llm.client import llm_client
for agent in ['writer', 'jury_r', 'jury_f', 'jury_s']:
    stats = llm_client.get_cache_stats(agent)
    print(f'{agent}: {stats["cache_hit_rate"]:.1%}')
"
```

---

**IMPORTANTE:** Le ottimizzazioni sono **integrate nel codice nuovo**, non aggiunte dopo. Questo elimina refactoring costoso in seguito.

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
- Per RAG + SHINE: `docs/RAG_SHINE_INTEGRATION.md`
- Per cost optimization: `docs/COST_OPTIMIZATION_ROADMAP.md` ← NEW
- Per agent nodes: `docs/05_agents.md` (sezione specifica, es. §5.7 per Writer)
- Per jury: `docs/08_jury_system.md`, `docs/09_css_aggregator.md`
- Per state: `docs/04_architecture.md` (§4.6 DocumentState)
- Per ottimizzazioni: `docs/29_performance_optimizations.md`

**Workflow incrementale:**
1. Start with Phase 0 Task 0.1 (RAG foundation)
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

**Test RAG connector:**
```bash
python -c "from src.connectors.memvid_connector import MemvidConnector; c = MemvidConnector('test_kb.mp4'); print(c.search('test'))"
```

---

## 🏁 Success Metrics

**After Phase 0 (RAG + SHINE):**
- [ ] Knowledge base built from docs/ (>100 chunks)
- [ ] Researcher uses local sources first (>80% when populated)
- [ ] SHINE adapter runs without errors (fallback OK)
- [ ] bge-m3 embeddings active in MetricsCollector

**After Phase 1 (MVP):**
- [ ] Single-section run completes end-to-end
- [ ] **Baseline cost measured: $2-5/section** ← NEW
- [ ] §29.5 state size < 500KB after 1 section
- [ ] Cache hit rate: 0% (baseline, no caching yet)
- [ ] SHINE activation rate: 100% Premium, 0% Economy

**After Phase 2 (Jury + Layer 1):**
- [ ] Real jury approves/rejects correctly
- [ ] CSS formula matches §9 spec
- [ ] **§29.1 cache hit rate ≥50%** ← NEW
- [ ] **Cost: $0.20-0.50/section (-81%)** ← NEW
- [ ] **§29.5 state size <200KB** ← NEW

**After Phase 3 (Iteration + Layer 2):**
- [ ] Reflector → Writer loop works
- [ ] Max 4 iterations before force-approve
- [ ] Oscillation detector prevents infinite loops
- [ ] **§29.3 model tiering active: 60% runs tier1 only** ← NEW
- [ ] **§29.6 CitationVerifier <5s for 12 sources** ← NEW
- [ ] **Cost: $0.10-0.20/section (-91%)** ← NEW

**After Phase 4 (Advanced + Layer 3):**
- [ ] MoW generates 3 diverse drafts
- [ ] Panel Discussion activates on CSS < 0.50
- [ ] **§29.7 distillation active (Economy): 95% accuracy retention** ← NEW
- [ ] **Cost: $0.05-0.15/section Economy (-94%)** ← NEW

---

## 📝 Notes for AI Agent

1. **Always read specs first:** Don't guess implementation details. Reference `docs/*.md` files.

2. **Reuse existing patterns:** Many nodes already implemented in `src/graph/nodes/`. Copy structure.

3. **§29 optimizations are CRITICAL:** Prompt caching (§29.1) must be in every LLM call to Writer/Jury/Reflector.

4. **RAG + SHINE = Phase 0 priority:** Questo sblocca 40% cost reduction + 5x speedup. Implementa prima di MVP.

5. **Fallback-first:** SHINE e Memvid devono avere graceful fallback se non disponibili. DRS deve funzionare sempre.

6. **Test incrementally:** After each task, run `pytest tests/unit/test_[component].py`. Don't wait until end.

7. **State is immutable:** LangGraph state updates must return `dict` with changed keys only. Don't mutate `state` directly.

8. **Error handling:** All LLM calls must have try/except with fallback. See existing nodes for pattern.

9. **Cost tracking:** Every LLM call via `llm_client.call()` auto-tracks cost. Don't implement separately.

10. **Cache metrics:** Track `cache_read_tokens` / `total_input_tokens` ratio to verify §29.1 working.

11. **Cost optimization is progressive:** Layer 1 (Week 4) → Layer 2 (Week 6) → Layer 3 (Week 8). Don't skip baseline (Week 1-3). ← NEW

12. **Measure everything:** Cost, cache hit rate, state size. Use measurement commands dopo ogni Phase. ← NEW

---

**Last updated:** 2026-02-23 (RAG + SHINE integration + Cost Optimization Roadmap)  
**Maintainer:** Auto-generated by Perplexity AI  
**Specs version:** DRS v3.0 + §29 optimizations + RAG + SHINE + Cost Roadmap
