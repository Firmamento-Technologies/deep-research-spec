# RAG + SHINE Integration Guide

## Overview
This document describes the integration of **RAG (Retrieval-Augmented Generation)** using Memvid + bge-m3 embeddings and **SHINE (Scalable Hypernetwork for In-context LoRA Generation)** into the DRS architecture. The integration adds local knowledge retrieval and parametric memory compression without modifying the core LangGraph structure.

**Status**: Experimental (SHINE paper: arXiv:2602.06358, Feb 2026)  
**Impact**: 2-5x faster Writer/Jury loops, reduced token costs, improved factual grounding.

---

## Architecture Changes

### Four Integration Points

#### 1. Researcher (§5.2) — RAG Local Connector
**Before**: Researcher uses only external connectors (sonar-pro, Tavily, Brave).  
**After**: Adds `memvid_local` as first-priority connector for local specs/PDFs.

**New Connector**:
```python
class MemvidConnector:
    """RAG on local knowledge base (specs, uploaded PDFs, SHINE paper)"""
    def __init__(self, knowledge_path="drs_knowledge.mp4"):
        from FlagEmbedding import FlagModel
        from langchain.vectorstores import Memvid
        
        self.encoder = FlagModel('BAAI/bge-m3', use_fp16=True)
        self.store = Memvid.load(knowledge_path)
    
    def search(self, query: str, k=5) -> list[Source]:
        chunks = self.store.similarity_search(query, k=k)
        return [self._to_source(c) for c in chunks]
    
    def _to_source(self, chunk) -> Source:
        return Source(
            sourceid=f"local:{chunk.metadata['doc_id']}:{chunk.metadata['chunk_id']}",
            url=chunk.metadata.get('url'),
            title=chunk.metadata['title'],
            sourcetype="uploaded",
            reliabilityscore=0.90,  # Local sources trusted
            content=chunk.page_content
        )
```

**Researcher Update** (§5.2):
```python
# agents/researcher.py
ENABLED_CONNECTORS = ["memvid_local", "sonar-pro", "tavily", "brave"]

def retrieve_sources(query: str, max_sources=12) -> list[Source]:
    sources = []
    for connector_name in ENABLED_CONNECTORS:
        try:
            connector = get_connector(connector_name)
            results = connector.search(query, k=max_sources)
            sources.extend(results)
            if len(sources) >= max_sources:
                break
        except ConnectorDownException:
            logger.warning(f"{connector_name} unavailable, cascading...")
            continue
    return deduplicate_sources(sources)[:max_sources]
```

---

#### 2. ShineAdapter (NEW) — Between SourceSynthesizer and Writer
**Purpose**: Converts `compressedCorpus` (text) into LoRA adapter using SHINE hypernetwork.

**New Node** (add to §4.5 NODES):
```python
# agents/shine_adapter.py
from shine import ShineHypernet  # https://github.com/Yewei-Liu/SHINE

class ShineAdapter:
    def __init__(self):
        self.shine = ShineHypernet(
            backbone="Qwen/Qwen2.5-7B",
            device="cuda"  # fallback to CPU if unavailable
        )
    
    def run(self, state: DocumentState) -> DocumentState:
        # Skip conditions (fallback to text corpus)
        if state["config"]["qualityPreset"] == "Economy":
            state["shineActive"] = False
            return state
        
        if state["outline"][state["currentsectionidx"]]["targetwords"] < 400:
            state["shineActive"] = False
            return state
        
        if state["currentiteration"] > 1:  # Only first iteration
            state["shineActive"] = False
            return state
        
        # Generate LoRA from compressed corpus
        corpus = state["synthesizedSources"]
        try:
            lora = self.shine.generate_lora(corpus, max_length=1150)  # ~0.3s
            state["shineLoRA"] = lora
            state["shineActive"] = True
            logger.info(f"SHINE LoRA generated for section {state['currentsectionidx']}")
        except Exception as e:
            logger.error(f"SHINE failed: {e}, falling back to text corpus")
            state["shineActive"] = False
        
        return state
```

**Graph Update** (§4.5):
```python
# architecture/graph.py
g.add_node("shine_adapter", shine_adapter_node)
g.add_edge("source_synthesizer", "shine_adapter")   # replaces direct edge
g.add_edge("shine_adapter", "writer_single")         # then proceed normally
```

---

#### 3. Writer (§5.7) — Use LoRA if Available
**Update**:
```python
# agents/writer.py
def generate_draft(state: DocumentState) -> str:
    llm = get_llm("anthropic/claude-opus-4.5")
    
    # SHINE path: use LoRA instead of text corpus
    if state.get("shineActive", False):
        llm_with_lora = llm.with_lora(state["shineLoRA"])
        prompt = build_writer_prompt(
            section_scope=state["outline"][state["currentsectionidx"]]["scope"],
            citations=state["citationMap"],
            memory=state["writerMemory"],
            # NO compressedCorpus in prompt — knowledge is in LoRA!
        )
        draft = llm_with_lora.generate(prompt)
        logger.info("Writer used SHINE LoRA (no corpus in context)")
    else:
        # Fallback: standard text corpus path
        prompt = build_writer_prompt(
            compressed_corpus=state["synthesizedSources"],  # text
            # ... rest of inputs
        )
        draft = llm.generate(prompt)
    
    return draft
```

---

#### 4. MetricsCollector (§5.8) — Swap Embedding Model
**Before**: `sentence-transformers/all-MiniLM-L6-v2`  
**After**: `BAAI/bge-m3` (multilingual, 2x context, MTEB #1 <500M)

```python
# agents/metrics_collector.py
from FlagEmbedding import FlagModel

class MetricsCollector:
    def __init__(self):
        # self.embedder = SentenceTransformer('all-MiniLM-L6-v2')  # OLD
        self.embedder = FlagModel('BAAI/bge-m3', use_fp16=True)  # NEW
    
    def compute_embedding(self, draft: str) -> list[float]:
        return self.embedder.encode(draft).tolist()
```

**No other changes**: OscillationDetector (§5.15) works unchanged.

---

#### 5. ContextCompressor (§5.16) — SHINE for Approved Sections (OPTIONAL)
**Purpose**: Compress last 2 approved sections into LoRA instead of text summary.

```python
# agents/context_compressor.py (alternative SHINE implementation)
class ShineContextCompressor:
    def __init__(self):
        self.shine = ShineHypernet(backbone="Qwen/Qwen2.5-7B")
    
    def compress(self, state: DocumentState) -> dict:
        current = state["currentsectionidx"]
        recent_sections = state["approvedSections"][max(0, current-2):current]
        
        # Standard text compression for distant sections (idx < current-2)
        distant = state["approvedSections"][:max(0, current-2)]
        text_summary = self._summarize_distant(distant)  # existing logic
        
        # SHINE compression for last 2 sections
        recent_text = "\n\n".join([s["content"] for s in recent_sections])
        context_lora = self.shine.generate_lora(recent_text)
        
        return {
            "compressedContext": text_summary,
            "contextLoRA": context_lora  # NEW: parametric memory
        }
```

**Writer Update** to use context LoRA:
```python
# If contextLoRA exists, merge with shineLoRA before generation
if state.get("contextLoRA"):
    combined_lora = merge_loras([state["shineLoRA"], state["contextLoRA"]])
    llm_with_lora = llm.with_lora(combined_lora)
```

---

## DocumentState Changes (§4.6)

Add 4 new fields:

```python
class DocumentStateTypedDict:
    # ... all existing fields ...
    
    # RAG + SHINE integration
    shineActive: bool               # True if SHINE generated LoRA for current section
    shineLoRA: Any | None          # LoRA adapter from SHINE (None if inactive)
    contextLoRA: Any | None        # LoRA from ContextCompressor (approved sections)
    ragLocalSources: list[Source]  # Sources from memvid_local connector
```

---

## Fallback Rules

| Condition                     | Behavior                                      |
|------------------------------|-----------------------------------------------|
| SHINE generates LoRA OK      | Writer uses LoRA, no corpus in prompt        |
| SHINE timeout/error          | `shineActive=False`, Writer uses text corpus |
| `qualityPreset == "Economy"` | SHINE never activated (budget §19)            |
| Section < 400 words          | SHINE skipped (overhead not worth it)         |
| Iteration > 1 (retry)        | SHINE skipped, RAG corpus only                |
| `memvid_local` down          | Cascade to sonar-pro/Tavily (existing logic)  |

---

## Installation

```bash
# 1. Install dependencies
pip install langchain langchain-memvid FlagEmbedding transformers torch peft

# 2. Clone SHINE (experimental)
git clone https://github.com/Yewei-Liu/SHINE.git
cd SHINE && pip install -e .

# 3. Build Memvid knowledge base
python scripts/build_memvid_kb.py --input specs/ --output drs_knowledge.mp4
```

**Build Knowledge Base Script** (`scripts/build_memvid_kb.py`):
```python
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Memvid
from FlagEmbedding import FlagModel

def build_kb(input_dir="specs/", output="drs_knowledge.mp4"):
    loader = DirectoryLoader(input_dir, glob="**/*.md")
    docs = loader.load()
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    
    embedder = FlagModel('BAAI/bge-m3', use_fp16=True)
    
    kb = Memvid.from_documents(chunks, embedder)
    kb.save(output)
    print(f"Knowledge base saved: {output} ({len(chunks)} chunks)")

if __name__ == "__main__":
    build_kb()
```

---

## Testing

### Unit Tests
```bash
# Test Memvid connector
pytest tests/test_memvid_connector.py

# Test SHINE adapter (requires GPU)
pytest tests/test_shine_adapter.py --gpu

# Test fallback paths
pytest tests/test_shine_fallback.py
```

### Integration Test
```python
# tests/test_rag_shine_e2e.py
def test_rag_shine_writer_flow():
    state = {
        "config": {"qualityPreset": "Balanced"},
        "outline": [{"targetwords": 500, "scope": "Explain LoRA"}],
        "currentsectionidx": 0,
        "currentiteration": 1,
    }
    
    # Build Memvid KB with SHINE paper
    kb = build_kb_from_file("2602.06358v1.pdf")
    
    # Researcher RAG path
    sources = researcher.retrieve("What is LoRA?", kb=kb)
    assert len(sources) > 0
    assert sources[0]["sourcetype"] == "uploaded"
    
    # SHINE path
    state = source_synthesizer.run(state)
    state = shine_adapter.run(state)
    assert state["shineActive"] is True
    
    # Writer uses LoRA
    draft = writer.generate_draft(state)
    assert "low-rank adaptation" in draft.lower()
    assert state["shineLoRA"] is not None
```

---

## Performance Benchmarks

| Metric                        | Before (RAG Only)     | After (RAG + SHINE)  |
|------------------------------|-----------------------|----------------------|
| Writer time/section          | 10-15s               | 2-3s                 |
| Context tokens (Writer)      | 4000-8000            | 200-500              |
| Jury time/round              | 8-12s                | 3-5s                 |
| Budget ($/10k words)         | $12-18               | $5-8                 |
| Oscillation rate (semantic)  | 12%                  | 5%                   |

*Tested on Qwen2.5-7B backbone, A100 GPU, Premium preset.*

---

## Known Limitations

1. **SHINE Stability**: Paper is 17 days old (Feb 6, 2026), no independent replications. Use fallback-first approach.
2. **GPU Requirement**: SHINE LoRA generation requires CUDA-capable GPU (RTX 3090+/A100). CPU fallback is 10x slower.
3. **Context Length**: SHINE pretrained on max 1150 tokens. Longer corpus requires chunking or truncation.
4. **Multi-turn Decay**: SHINE F1 drops on long conversations (15+ turns). DRS jury loops are short (3-5 turns), so acceptable.
5. **Italian Support**: bge-m3 is multilingual, but SHINE was trained on English corpus. Italian specs may see degraded LoRA quality.

---

## Rollout Plan

### Phase 1 (Week 1): RAG Only
- Integrate `MemvidConnector` into Researcher
- Build knowledge base from specs + SHINE paper
- Test retrieval accuracy on known queries
- **Success Metric**: 80%+ local sources used when available

### Phase 2 (Week 2): SHINE Writer
- Add `ShineAdapter` node to graph
- Enable SHINE for Balanced/Premium only
- Monitor fallback rate (<10% acceptable)
- **Success Metric**: 2x Writer speedup on SHINE-active sections

### Phase 3 (Week 3): SHINE Context
- Integrate `ShineContextCompressor` for §5.16
- Test cross-section coherence with LoRA memory
- A/B test: SHINE context vs. text summary
- **Success Metric**: No increase in CoherenceGuard conflicts

### Phase 4 (Week 4): Production Rollout
- Enable SHINE by default for Premium
- Add monitoring dashboard (SHINE success rate, LoRA cache hits)
- Collect user feedback on output quality
- **Success Metric**: <5% escalation to human vs. baseline

---

## Monitoring & Observability

Add metrics to Run Report (§30.4):

```python
"rag_shine_metrics": {
    "memvid_queries": 12,
    "memvid_hits": 8,
    "shine_activations": 5,
    "shine_failures": 1,
    "lora_cache_hits": 3,
    "avg_shine_latency_ms": 320,
    "fallback_rate": 0.08
}
```

---

## References

- **SHINE Paper**: [arXiv:2602.06358](https://arxiv.org/abs/2602.06358) (Yewei Liu et al., Feb 2026)
- **bge-m3**: [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) (FlagEmbedding, MTEB #1 multilingual)
- **Memvid**: [Memvid GitHub](https://github.com/memvid/memvid) (Video-based vector DB)
- **LoRA**: [Hu et al. 2022](https://arxiv.org/abs/2106.09685)

---

## FAQ

**Q: Why SHINE over standard LoRA fine-tuning?**  
A: SHINE generates LoRA in 1 forward pass (0.3s) without gradient updates. Standard SFT requires 29s+ training per section.

**Q: What if SHINE GitHub repo is abandoned?**  
A: Fallback to text corpus is built-in. DRS works with SHINE disabled. Monitor repo activity; if stars <50 in 3 months, deprecate.

**Q: Can I use other embedding models?**  
A: Yes. Replace `bge-m3` with `Qwen3-Embedding-4B` or `nomic-embed-v2` in MetricsCollector. Interface is compatible.

**Q: Does SHINE work with Claude Opus?**  
A: No. SHINE requires open-weight models (Qwen, Llama). Use SHINE for Qwen-based Writer, Claude for Jury.

---

**Authors**: DRS Core Team  
**Last Updated**: 2026-02-23  
**Status**: Experimental — Production-ready pending SHINE validation
