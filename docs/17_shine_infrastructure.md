# 17_shine_infrastructure.md
# SHINE Parametric Memory Infrastructure

**Cross-references:** Agent specs (§5), DocumentState (§4.6), Source connectors (§17.1–17.8), Config (§29)

---

## § 17.9 SHINE Indexer

**RESPONSIBILITY:** Index uploaded documents into LoRA adapters for parametric memory injection  
**TRIGGER:** Phase A setup, if `config.user.uploadedsources` is non-empty  
**MODEL:** SHINE hypernetwork (Qwen3-8B backbone pre-trained)  
**TEMP:** n/a (deterministic single forward pass per document)  
**MAXTOKENS:** n/a

### INPUT
```python
uploaded_docs: List[str]  # Raw document text, pre-parsed by file handler
corpus_id: str            # Unique identifier: f"run_{runid}"
user_id: str              # For multi-tenant isolation
```

### OUTPUT
```python
indexing_result: Dict[str, Any] = {
    "adapter_hashes": List[str],        # SHA256 of each adapter
    "total_adapters": int,              # Count after deduplication
    "indexing_time_seconds": float,
    "deduplication_count": int,         # Docs skipped (already indexed)
    "storage_mb": float                 # Total storage consumed
}
```

### CONSTRAINTS

**MUST** complete within **10 minutes** for 1,000 documents (0.6s/doc budget including I/O)

**MUST** deduplicate by content hash before indexing — if `sha256(doc)` exists in registry with same user_id, skip indexing and reuse existing adapter

**MUST** store topic embeddings alongside adapter weights for semantic search at runtime — use `sentence-transformers/all-MiniLM-L6-v2` (same as MetricsCollector §5.8 for consistency)

**MUST** generate rank=16 LoRA adapters targeting `["q_proj", "v_proj"]` modules only — this balances quality (sufficient for knowledge injection) with storage efficiency (~80KB per adapter)

**MUST** validate adapter generation success — if SHINE hypernetwork raises error for a document, log warning, skip that document, continue with remaining documents

**NEVER** block run start if indexing fails partially — if ≥50% of documents indexed successfully, proceed with partial corpus; if <50%, log error and proceed without SHINE (fallback to standard RAG via Researcher §5.2)

**ALWAYS** emit indexing progress via SSE stream: `{"event": "SHINE_INDEXING", "progress": 0.0-1.0, "docs_processed": int, "docs_total": int}`

### ERRORHANDLING

| Error | Action |
|---|---|
| `hypernetwork_load_error` | Fallback to standard RAG — set `state.shineavailable = False`, skip injection hooks |
| `storage_quota_exceeded` | Fail preflight — raise to user before Phase A completes |
| `doc_parsing_error` | Skip document, log warning, continue with remaining |
| `registry_db_timeout` | Retry 3× with exponential backoff (1s→2s→4s); if all fail, fallback to in-memory registry (ephemeral, lost after run) |

### CONSUMES (from DocumentState)
- `config.user.uploadedsources: List[UploadedFile]` — file metadata (path, name, mimetype)
- `userid: str`
- `runid: str`

### PRODUCES (to DocumentState)
- `shinemeta: Dict[str, Any]` — indexing result dict above
- `corpusid: str` — computed as `f"run_{runid}"`
- `shineavailable: bool` — `True` if indexing succeeded, gates injection hooks

---

## § 17.10 SHINE Injection Hook

**RESPONSIBILITY:** Decorator that injects LoRA adapters into agent model at runtime  
**TRIGGER:** Applied to Researcher (§5.2), Writer (§5.7), CitationVerifier (§5.4), PostDraftAnalyzer (§5.11)  
**MODEL:** PEFT library adapter injection API  
**OVERHEAD:** 0.35s per decorated agent call (search 0.2s + load/merge 0.15s)

### Decorator Signature
```python
@with_shine_memory(
    corpus_id: str,           # From state.corpusid
    top_k: int = 3,           # Researcher=5, Writer=3, Verifier=10, Analyzer=5
    enable_condition: Callable[[DocumentState], bool] = lambda s: s.shineavailable
)
def agent_method(self, *args, **kwargs) -> Any:
    ...
```

### Mechanism (5-step injection pipeline)

**STEP 1: Query Extraction**  
Extract semantic query from agent input — implementation varies per agent:
- Researcher: `section_scope` string
- Writer: `section_scope + reflector_feedback.summary` (if present)
- CitationVerifier: `claim` string when `source_id.startswith("uploaded_")`
- PostDraftAnalyzer: `gap.description` for each detected gap

**STEP 2: Semantic Search**  
Query LoRA Registry for top-k relevant adapters:
```python
registry = LoRARegistry.get_instance()
query_embedding = embed_model.encode(query)  # all-MiniLM-L6-v2
relevant_doc_hashes = registry.search(
    corpus_id=corpus_id,
    query_embedding=query_embedding,
    top_k=top_k,
    similarity_threshold=0.60  # Cosine similarity cutoff
)
```

**STEP 3: Adapter Loading & Merging**  
Load adapter weights from registry and merge using TIES algorithm:
```python
adapters = [registry.load_adapter(h) for h in relevant_doc_hashes]
merged_lora = ties_merge(
    adapters,
    density=0.10,  # Keep top 10% of weights — pruning for efficiency
    resolve_method="magnitude"  # Magnitude-based sign consensus
)
```

**STEP 4: Model Injection**  
Inject merged adapter into agent's model via PEFT:
```python
from peft import inject_adapter_in_model, set_peft_model_state_dict

inject_adapter_in_model(
    model=agent.model,
    peft_config=LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"]),
    adapter_name="shine_dynamic"
)
set_peft_model_state_dict(agent.model, merged_lora, adapter_name="shine_dynamic")
agent.model.enable_adapters()
```

**STEP 5: Cleanup**  
After agent method executes, remove adapter:
```python
try:
    result = agent_method(self, *args, **kwargs)
finally:
    agent.model.disable_adapters()
    # Adapter weights remain in registry — only model reference is cleared
```

### CONSTRAINTS

**MUST** complete steps 1-4 within **0.35s total** — if search exceeds 0.3s timeout, skip injection and execute agent without adapter (log warning to Run Report)

**MUST** filter search results by `similarity_threshold=0.60` — if all retrieved adapters score <0.60 cosine similarity, skip injection (irrelevant documents)

**MUST** use TIES-Merging algorithm when `top_k > 1` — simple averaging causes weight interference, TIES resolves sign conflicts (see [Yadav et al., 2023](https://arxiv.org/abs/2306.01708))

**MUST** isolate adapter injection per agent call — if two agents run in parallel (e.g., Writer A/B/C in MoW §7), each gets independent adapter injection (no shared state)

**NEVER** inject adapter if `state.shineavailable == False` — decorator becomes no-op passthrough

**NEVER** modify agent method signature or return type — decorator is fully transparent to agent implementation

**ALWAYS** log injection metadata to Run Report:
```python
{
    "agent": "Writer",
    "section_idx": 3,
    "query": "section_scope...",
    "adapters_retrieved": ["hash1", "hash2"],
    "similarity_scores": [0.82, 0.74],
    "injection_time_ms": 285
}
```

### ERRORHANDLING

| Error | Action |
|---|---|
| `registry_search_timeout` | Skip injection, execute agent without adapter, log warning |
| `adapter_load_error` | Skip that adapter, try next in top-k; if all fail, skip injection |
| `ties_merge_failure` | Fallback to simple averaging (degraded mode), log warning |
| `peft_injection_error` | Skip injection, execute agent without adapter, set `state.shineavailable = False` for remainder of run |

### APPLIES TO (agent modifications)

See §17.11–17.14 for agent-specific integration details.

---

## § 17.11 SHINE Integration: Researcher (§5.2 Modification)

**MODIFICATION TYPE:** Input expansion + constraint addition

### INPUT (ADDED)
```python
+ corpus_id: Optional[str] = None  # From state.corpusid, None if no uploads
```

### CONSTRAINTS (ADDED)

**MUST** query SHINE memory if `corpus_id` is not None — invoke decorated method `query_uploaded_sources(section_scope, top_k=5)` which uses `@with_shine_memory` hook

**MUST** tag uploaded sources with `sourcetype="uploaded"` in Source dict — this signals CitationVerifier (§5.4) and SourceSanitizer (§5.5) to handle them specially

**MUST** append uploaded sources to `currentsources` list **after** web/academic sources — preserve existing source ranking, treat uploaded as supplementary

**MUST** cap uploaded sources at **5 per section** regardless of relevance — prevents over-reliance on user-uploaded content vs. external verification

**NEVER** skip external search (Tavily/Brave/CrossRef) when uploaded sources are available — uploaded content supplements, not replaces, external sources

### NEW METHOD (added to Researcher class)
```python
@with_shine_memory(corpus_id=lambda self: self.corpus_id, top_k=5)
def query_uploaded_sources(self, section_scope: str, max_sources: int = 5) -> List[Source]:
    """
    With SHINE adapter injected, query the model for relevant excerpts
    from uploaded documents. The adapter contains parametric knowledge —
    the model can "recall" document content without seeing raw text.
    """
    prompt = f"""
You have been trained on a corpus of uploaded documents.

Section scope: {section_scope}

List up to {max_sources} relevant excerpts from the uploaded documents.
For each excerpt:
1. Quote the relevant passage (max 200 words)
2. State the document title/filename if known
3. Assess relevance (HIGH/MEDIUM/LOW)

Format:
[EXCERPT 1]
Content: <quoted text>
Source: <document identifier>
Relevance: <HIGH|MEDIUM|LOW>
"""
    
    response = self.model.generate(prompt, max_tokens=2048)
    sources = self._parse_shine_response(response)
    
    # Assign sourcetype and reliabilityscore
    for source in sources:
        source["sourcetype"] = "uploaded"
        source["reliabilityscore"] = 1.0  # User-provided = trusted by default
        source["sourceid"] = f"uploaded_{hash(source['content'])[:8]}"
    
    return sources[:max_sources]
```

### PRODUCES (MODIFIED)
```python
sources: List[Source]  # Now includes sourcetype="uploaded" entries
```

---

## § 17.12 SHINE Integration: Writer (§5.7 Modification)

**MODIFICATION TYPE:** Decorator application + constraint addition

### CONSTRAINTS (ADDED)

**MUST** use `@with_shine_memory(corpus_id, top_k=3)` decorator when `state.corpusid` is not None

**MUST** prioritize parametric knowledge over contextual knowledge for conflict resolution — if a fact appears in both `compressedcorpus` (contextual) and the injected adapter (parametric), trust the adapter (user-uploaded source) unless explicitly contradicted by high-reliability external source (reliabilityscore ≥ 0.90)

**MUST** include proactive instruction in system prompt when adapter is active:
```
You have been augmented with parametric memory of uploaded documents.
You can reference these documents implicitly without quoting them in the
compressed corpus. Cite them as [uploaded:X] where X is the source identifier.
```

**NEVER** expose adapter injection mechanism in generated draft — the draft must read naturally, as if the Writer simply "knows" the uploaded content

### EXAMPLE WORKFLOW

**Without SHINE:**
```
compressedcorpus = "Policy X states Y. Report Z found Q."
→ Writer generates: "According to Policy X, Y is true [cite:1]."
```

**With SHINE (adapter injected for Policy X):**
```
compressedcorpus = "Report Z found Q."
→ Writer generates: "Internal policy mandates Y [uploaded:3a2f], which aligns 
   with external findings that Q [cite:1]."
```

The Writer "remembers" Policy X via adapter, doesn't need it in prompt.

---

## § 17.13 SHINE Integration: CitationVerifier (§5.4 Modification)

**MODIFICATION TYPE:** Conditional decorator + method addition

### CONSTRAINTS (ADDED)

**MUST** use `@with_shine_memory(corpus_id, top_k=10)` decorator **only when verifying uploaded sources** (source_id starts with `"uploaded_"`)

**MUST** extract source passage from parametric memory before running DeBERTa NLI:
```python
if source.sourcetype == "uploaded":
    # Adapter injection hook active
    passage = self._extract_passage_from_shine(claim, source.sourceid)
    entailment_score = self.deberta_nli(claim, passage)
else:
    # Standard HTTP fetch for external sources
    passage = self.fetch_source_content(source.url)
    entailment_score = self.deberta_nli(claim, passage)
```

**MUST** set `httpverified=True` for uploaded sources automatically — no HTTP check needed, file was validated at upload time

**NEVER** mark uploaded source as `ghostcitation` — uploaded sources are immutable within run scope

### NEW METHOD
```python
@with_shine_memory(corpus_id=lambda self: self.corpus_id, top_k=10)
def _extract_passage_from_shine(self, claim: str, source_id: str) -> str:
    """
    Use injected adapter to retrieve the specific passage that supports
    the claim. This avoids loading full document from storage.
    """
    prompt = f"""
From uploaded source {source_id}, extract the passage that supports:
Claim: {claim}

Return only the relevant passage (max 300 words).
"""
    passage = self.model.generate(prompt, max_tokens=512)
    return passage.strip()
```

---

## § 17.14 SHINE Integration: PostDraftAnalyzer (§5.11 Modification)

**MODIFICATION TYPE:** Decorator application + gap resolution logic

### CONSTRAINTS (ADDED)

**MUST** use `@with_shine_memory(corpus_id, top_k=5)` decorator when analyzing gaps

**MUST** check if detected gaps are addressable via uploaded documents before flagging for external research:
```python
for gap in detected_gaps:
    if self.corpus_id:
        coverage = self._check_uploaded_coverage(gap.description)
        if coverage.score >= 0.70:
            gap.suggested_queries.append(f"uploaded:{gap.topic}")
            gap.category = "resolvable_internal"
        else:
            gap.category = "missing_evidence"  # Trigger Researcher
```

**MUST** reduce false-positive gap detection — if adapter indicates uploaded docs contain relevant info, don't flag as "missing evidence" (avoids unnecessary Researcher call)

### NEW METHOD
```python
@with_shine_memory(corpus_id=lambda self: self.corpus_id, top_k=5)
def _check_uploaded_coverage(self, gap_description: str) -> Dict[str, Any]:
    """
    Query injected adapter to assess if uploaded docs cover the gap.
    """
    prompt = f"""
Do the uploaded documents contain information addressing this gap?
Gap: {gap_description}

Respond: YES (with confidence 0-1) or NO
"""
    response = self.model.generate(prompt, max_tokens=100)
    return self._parse_coverage_response(response)
```

---

## § 17.15 LoRA Registry Storage Schema

**DATABASE:** PostgreSQL (same instance as sections table §21)  
**TABLE:** `lora_adapters`

```sql
CREATE TABLE lora_adapters (
    doc_hash VARCHAR(64) PRIMARY KEY,           -- SHA256 of document content
    corpus_id VARCHAR(64) NOT NULL,             -- "run_{runid}" for multi-run isolation
    user_id VARCHAR(64) NOT NULL,               -- Multi-tenant isolation
    adapter_weights BYTEA NOT NULL,             -- PEFT state_dict serialized (pickle)
    topic_embedding VECTOR(384) NOT NULL,       -- all-MiniLM-L6-v2 embedding
    metadata JSONB DEFAULT '{}',                -- {"title": "...", "length": 5000, ...}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_corpus_user (corpus_id, user_id),
    INDEX idx_topic_embedding USING ivfflat (topic_embedding vector_cosine_ops)
);

-- Retention policy: DELETE adapters WHERE created_at < NOW() - INTERVAL '90 days'
-- User-uploaded sources are ephemeral per run; cleanup after 90 days
```

### Storage Efficiency

| Corpus Size | Adapter Weights | Topic Embeddings | Total Storage |
|---|---|---|---|
| 100 docs | 8 MB | 150 KB | **8.15 MB** |
| 1,000 docs | 80 MB | 1.5 MB | **81.5 MB** |
| 10,000 docs | 800 MB | 15 MB | **815 MB** |

**Rank=16 LoRA:** ~80 KB per adapter (q_proj + v_proj for Qwen3-8B = 2 × 4096 × 16 × 2 bytes)

---

## § 17.16 Configuration Schema Extension

**FILE:** `03_input_config.md` (§29 modification)

### UserConfig (ADDED fields)
```python
class UserConfig(BaseModel):
    ...
    
    # SHINE configuration
    uploadedsources: List[UploadedFile] = Field(
        default_factory=list,
        description="User-uploaded documents for parametric memory injection"
    )
    shineenabled: bool = Field(
        default=True,
        description="Enable SHINE parametric memory. Set False to use standard RAG only."
    )
    shineadapterrank: int = Field(
        default=16,
        ge=8,
        le=32,
        description="LoRA adapter rank. Higher = better quality, larger storage. 16 is recommended."
    )
```

### UploadedFile Schema
```python
class UploadedFile(BaseModel):
    filepath: str = Field(..., description="Absolute path to uploaded file")
    filename: str = Field(..., description="Original filename")
    mimetype: str = Field(..., description="MIME type (e.g., application/pdf)")
    filesize_mb: float = Field(..., description="File size in MB")
    upload_timestamp: str = Field(..., description="ISO 8601 timestamp")
    
    @validator("mimetype")
    def validate_mimetype(cls, v):
        allowed = ["application/pdf", "text/plain", "text/markdown", 
                   "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        if v not in allowed:
            raise ValueError(f"Unsupported mimetype: {v}")
        return v
```

---

## § 17.17 Pre-Flight Validation (§4.1 Modification)

**PHASE A ADDITION:** After `budgetestimator` node, before `planner` node

### New Node: `shine_indexer`

```python
def shine_indexer_node(state: DocumentState) -> DocumentState:
    """
    Index uploaded documents into LoRA adapters if present.
    Runs during Phase A setup, blocks outline approval until complete.
    """
    if not state.config["user"]["uploadedsources"]:
        state.shineavailable = False
        return state
    
    if not state.config["user"]["shineenabled"]:
        state.shineavailable = False
        return state
    
    indexer = SHINEIndexer(
        hypernetwork_path=SHINE_MODEL_PATH,
        registry_db=POSTGRES_CONNECTION_STRING
    )
    
    uploaded_docs = [
        parse_file(f.filepath, f.mimetype) 
        for f in state.config["user"]["uploadedsources"]
    ]
    
    corpus_id = f"run_{state.runid}"
    
    result = indexer.index_documents(
        uploaded_docs=uploaded_docs,
        corpus_id=corpus_id,
        user_id=state.userid
    )
    
    state.shinemeta = result
    state.corpusid = corpus_id
    state.shineavailable = result["total_adapters"] >= len(uploaded_docs) * 0.50
    
    return state
```

### Graph Edges (MODIFIED)
```python
g.add_edge("budgetestimator", "shine_indexer")
g.add_edge("shine_indexer", "planner")
```

---

## § 17.18 DocumentState Extensions (§4.6 Modification)

```python
class DocumentState(TypedDict):
    ...
    
    # SHINE state (added)
    corpusid: Optional[str]              # "run_{runid}" or None
    shineavailable: bool                 # True if indexing succeeded
    shinemeta: Optional[Dict[str, Any]]  # Indexing result from §17.9
```

---

## § 17.19 Run Report Extension (§30 Modification)

**SECTION ADDED:** SHINE Memory Metrics

```python
"shine_metrics": {
    "enabled": bool,
    "docs_uploaded": int,
    "adapters_created": int,
    "indexing_time_seconds": float,
    "storage_mb": float,
    "injection_count": int,  # How many times decorator injected adapter
    "avg_injection_time_ms": float,
    "top_retrieved_docs": List[str]  # Most frequently retrieved adapter hashes
}
```

---

<!-- SPECCOMPLETE -->