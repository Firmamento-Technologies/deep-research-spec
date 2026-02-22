# 30_shine_integration.md
# SHINE Agent Integration Patches

**Cross-references:** SHINE Infrastructure (§17), Agent specs (§5), Architecture (§4), Config (§29)

---

This document contains **inline modifications** to existing agent specifications to integrate SHINE parametric memory.

## Modification Strategy

- **Decorator-based:** All integrations use the `@with_shine_memory` decorator (§17.10)
- **Non-invasive:** Agent core logic remains unchanged
- **Conditional:** SHINE features activate only when `state.shineavailable == True`
- **Transparent:** Agents behave identically from caller's perspective

---

## § 5.2.1 SHINE Integration: Researcher

**INSERT AFTER:** §5.2 Researcher specification

### ADDED INPUT
```python
+ corpus_id: Optional[str] = None  # From state.corpusid
```

### ADDED CONSTRAINTS

**MUST** query uploaded sources via `@with_shine_memory` decorator if `corpus_id` is not None — see §17.11 for implementation

**MUST** append uploaded sources with `sourcetype="uploaded"` to `currentsources` list

**MUST** cap uploaded sources at 5 per section

**NEVER** skip external search when uploaded sources available

### NEW METHOD
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

### MODIFIED OUTPUT
```python
sources: List[Source]  # Now includes sourcetype="uploaded" entries
```

---

## § 5.7.1 SHINE Integration: Writer

**INSERT AFTER:** §5.7 Writer specification

### ADDED CONSTRAINTS

**MUST** apply `@with_shine_memory(corpus_id=state.corpusid, top_k=3)` decorator when `state.corpusid` is not None — see §17.12

**MUST** prioritize parametric knowledge (adapter) over contextual knowledge (compressedcorpus) for conflict resolution

**MUST** inject system prompt instruction about uploaded memory when adapter active:
```
You have been augmented with parametric memory of uploaded documents.
You can reference these documents implicitly without quoting them in the
compressed corpus. Cite them as [uploaded:X] where X is the source identifier.
```

**NEVER** expose adapter injection mechanism in generated draft

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

## § 5.4.1 SHINE Integration: CitationVerifier

**INSERT AFTER:** §5.4 CitationVerifier specification

### ADDED CONSTRAINTS

**MUST** use `@with_shine_memory` decorator **only when verifying uploaded sources** (source_id starts with `"uploaded_"`) — see §17.13

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

## § 5.11.1 SHINE Integration: PostDraftAnalyzer

**INSERT AFTER:** §5.11 PostDraftAnalyzer specification

### ADDED CONSTRAINTS

**MUST** apply `@with_shine_memory(corpus_id, top_k=5)` decorator — see §17.14

**MUST** check if gaps are resolvable via uploaded documents before flagging for external research:
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

## § 4.1.1 SHINE Integration: Phase A Architecture

**INSERT AFTER:** §4.1 Phase A Pre-Flight and Setup

### MODIFIED FLOW

**Before:**
```
preflight → budgetestimator → planner → awaitoutline
```

**After:**
```
preflight → budgetestimator → shine_indexer → planner → awaitoutline
```

### NEW NODE: `shine_indexer`

- Runs if `config.user.uploadedsources` is non-empty
- Indexes uploaded documents into LoRA adapters (§17.9)
- Sets `state.shineavailable` flag
- Emits indexing progress via SSE
- Timeout: 10 minutes for 1K docs
- On failure: proceed without SHINE (degraded mode)

---

## § 4.5 SHINE Integration: LangGraph Topology

**INSERT IN:** §4.5 NODES list

### NODES (MODIFIED)
```python
NODES: List[str] = [
    "preflight",
    "budgetestimator",
    "shine_indexer",  # ADDED
    "planner",
    ...
]
```

### EDGES (MODIFIED)
```python
# Phase A Setup (MODIFIED)
g.add_edge("preflight", "budgetestimator")
g.add_edge("budgetestimator", "shine_indexer")  # ADDED
g.add_edge("shine_indexer", "planner")          # MODIFIED (was budgetestimator→planner)
g.add_edge("planner", "awaitoutline")
```

---

## § 4.6 SHINE Integration: DocumentState

**INSERT IN:** §4.6 DocumentState schema

### ADDED FIELDS
```python
class DocumentState(TypedDict):
    ...
    
    # SHINE state (ADDED)
    corpusid: Optional[str]              # "run_{runid}" or None
    shineavailable: bool                 # True if indexing succeeded
    shinemeta: Optional[Dict[str, Any]]  # {adapter_hashes, total_adapters, indexing_time_seconds, storage_mb}
```

---

## § 29.6 SHINE Integration: UserConfig

**INSERT IN:** §29.6 UserConfig class definition

### ADDED FIELDS
```python
class UserConfig(BaseModel):
    """User-specified configuration parameters."""
    
    topic: str = Field(..., min_length=10, max_length=500)
    targetwords: int = Field(..., ge=500, le=50000)
    maxbudgetdollars: float = Field(..., ge=1.0, le=500.0)
    
    # Existing fields...
    citationstyle: Literal["APA", "Harvard", "Chicago", "Vancouver"] = "APA"
    styleprofile: StyleProfile = "scientific_report"
    
    # SHINE configuration (ADDED)
    uploadedsources: List[UploadedFile] = Field(
        default_factory=list,
        description="User-uploaded documents for parametric memory injection via SHINE"
    )
    shineenabled: bool = Field(
        default=True,
        description="Enable SHINE parametric memory. Disable to use standard RAG only."
    )
    shineadapterrank: int = Field(
        default=16,
        ge=8,
        le=32,
        description="LoRA adapter rank (8/16/32). Higher = better quality, larger storage."
    )
```

### NEW SCHEMA: UploadedFile
```python
class UploadedFile(BaseModel):
    """Schema for user-uploaded source documents."""
    
    filepath: str = Field(..., description="Absolute path to uploaded file (server-side)")
    filename: str = Field(..., min_length=1, max_length=255, description="Original filename")
    mimetype: str = Field(..., description="MIME type")
    filesize_mb: float = Field(..., ge=0.001, le=50.0, description="File size in MB (max 50MB)")
    upload_timestamp: str = Field(..., description="ISO 8601 timestamp of upload")
    
    @field_validator("mimetype")
    @classmethod
    def validate_mimetype(cls, v: str) -> str:
        allowed = [
            "application/pdf",
            "text/plain",
            "text/markdown",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"  # .docx
        ]
        if v not in allowed:
            raise ValueError(f"Unsupported MIME type: {v}. Allowed: {allowed}")
        return v
```

---

## § 30.5 SHINE Integration: Run Report

**INSERT AS NEW SECTION IN:** Run Report specification

### SHINE Memory Metrics

**ADDED TO RUN REPORT:**

```python
"shine_metrics": {
    "enabled": bool,                        # True if SHINE was active for this run
    "docs_uploaded": int,                   # Count of uploaded documents
    "adapters_created": int,                # Count after deduplication
    "deduplication_count": int,             # Docs skipped (already indexed)
    "indexing_time_seconds": float,
    "storage_mb": float,                    # Total adapter storage consumed
    "injection_count": int,                 # How many times @with_shine_memory injected adapter
    "avg_injection_time_ms": float,
    "injection_breakdown": {
        "researcher": int,                  # Injection count per agent
        "writer": int,
        "citation_verifier": int,
        "postdraft_analyzer": int
    },
    "top_retrieved_adapters": [             # Most frequently used adapters
        {
            "doc_hash": str,
            "retrieval_count": int,
            "avg_similarity_score": float
        }
    ],
    "fallback_events": int                  # Times injection failed → standard RAG
}
```

**NULL VALUES:** If `shineenabled=False` or no uploaded sources, entire `shine_metrics` dict is `null`.

---

## Implementation Checklist

For developers implementing these patches:

### Infrastructure (Priority: HIGH)
- [ ] Install SHINE hypernetwork pre-trained (Qwen3-8B backbone)
- [ ] Create PostgreSQL table `lora_adapters` with `ivfflat` index (§17.15)
- [ ] Implement `SHINEIndexer` class (§17.9)
- [ ] Implement `@with_shine_memory` decorator (§17.10)
- [ ] Implement `LoRARegistry` for storage/retrieval

### Agent Modifications (Priority: MEDIUM)
- [ ] Modify `Researcher.__init__` to accept `corpus_id`
- [ ] Add `Researcher.query_uploaded_sources()` method
- [ ] Apply decorator to `Writer.generate_draft()`
- [ ] Apply decorator to `CitationVerifier.verify_claim()` (conditional)
- [ ] Apply decorator to `PostDraftAnalyzer.identify_gaps()`

### Graph & State (Priority: HIGH)
- [ ] Add `shine_indexer` node to LangGraph
- [ ] Modify edge `budgetestimator → shine_indexer → planner`
- [ ] Extend `DocumentState` with SHINE fields

### Config & Validation (Priority: MEDIUM)
- [ ] Extend Pydantic `UserConfig` with SHINE fields
- [ ] Implement validator for `UploadedFile.mimetype`
- [ ] Add file parsing (PDF/DOCX/TXT/MD) in preflight

### Monitoring & Reporting (Priority: LOW)
- [ ] Add SSE event `SHINE_INDEXING` with progress bar
- [ ] Extend Run Report with `shine_metrics` section
- [ ] Log injection metadata for debugging

---

## Migration Notes

### Backward Compatibility

- **Existing runs:** All SHINE features are **opt-in** via `config.user.shineenabled`
- **Default behavior:** If `uploadedsources` is empty, SHINE is automatically disabled (no performance impact)
- **Graceful degradation:** If indexing fails, system falls back to standard RAG

### Performance Impact

- **Phase A overhead:** ~0.6s per uploaded document (indexing)
- **Runtime overhead:** ~0.35s per agent call with injection
- **Storage overhead:** ~80KB per document (rank=16 LoRA)

### Security Considerations

- **Multi-tenancy:** `corpus_id` and `user_id` enforce isolation
- **Data retention:** Adapters auto-delete after 90 days (configurable)
- **File validation:** Strict MIME type whitelist + size limits (50MB max)

---

<!-- SPECCOMPLETE -->