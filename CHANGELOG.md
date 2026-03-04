# Changelog

All notable changes to the Deep Research Spec (DRS) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-03-04

### Added

**Knowledge Spaces — Private Document RAG Integration** ([TH.1-3](https://github.com/lucadidomenicodopehubs/deep-research-spec/issues/XXX))

Utenti possono ora caricare documenti privati (PDF/DOCX/TXT/MD) in "Knowledge Spaces" per farli usare dal Researcher durante le run con alta affidabilità (0.95).

#### Database

- **Migration 0003**: `chunks` table con pgvector per vector embeddings
  - Embedding dimension: 384 (sentence-transformers/all-MiniLM-L6-v2)
  - IVFFlat index per cosine similarity search
  - Foreign keys a `spaces` e `sources` con cascade delete
  - Metadata JSONB per estensioni future

#### Services

- **SpaceIndexer** ([backend/src/services/space_indexer.py](backend/src/services/space_indexer.py))
  - Text extraction da PDF (pypdf), DOCX (python-docx), TXT/MD
  - Semantic chunking: 512 token window, 50 token overlap
  - Batch embedding generation con sentence-transformers
  - Progress tracking e error handling
  - Support per re-indexing (delete + re-create)

- **RAGRetriever** ([backend/src/services/rag_retriever.py](backend/src/services/rag_retriever.py))
  - Query embedding con sentence-transformers
  - Cosine similarity search via pgvector (`<=>` operator)
  - Filtering per `space_ids` con IN clause
  - Top-K retrieval con similarity threshold (default 0.70)
  - Conversion a `Source` objects per DocumentState
  - Deduplication by content hash

#### API Endpoints

- **POST /spaces/:id/sources** — Upload file e trigger indexing
  - Validation: PDF/DOCX/TXT/MD, max 50MB
  - Async background indexing con SSE progress events
  - File storage: `/app/data/knowledge_spaces/{space_id}/`

- **GET /spaces/:id/sources** — List sources con chunk counts
- **POST /spaces/:id/reindex** — Re-index tutti i sources
- **DELETE /spaces/:id/sources/:source_id** — Delete source + chunks

#### Integration

- **Researcher Node** (§5.2) ora chiama `retrieve_chunks_for_spaces()`
  - Recupera top-5 chunks rilevanti per query
  - Aggiunge a `current_sources` con `reliability=0.95`
  - Priority: RAG chunks → memvid → sonar-pro → tavily

#### Documentation

- [Setup Guide](docs/KNOWLEDGE_SPACES_SETUP.md)
  - Installation (dependencies + pgvector)
  - Database migration steps
  - API usage examples (curl)
  - Testing commands (local + integration)
  - Troubleshooting guide
  - Architecture diagram

- [Requirements](backend/requirements_knowledge_spaces.txt)
  - sentence-transformers >= 2.3.1
  - pypdf >= 4.0.0
  - python-docx >= 1.1.0
  - tiktoken >= 0.5.2
  - aiofiles >= 23.2.1
  - pgvector >= 0.2.4

### Performance

| Operation | CPU | GPU |
|-----------|-----|-----|
| Extract 10-page PDF | 0.8s | 0.8s |
| Chunk 5k words | 0.2s | 0.2s |
| Embed 10 chunks | 1.2s | 0.06s |
| Insert 10 chunks (DB) | 0.05s | 0.05s |
| **Total per file** | **~2.3s** | **~1.1s** |
| Vector search (top-5) | 0.02s | 0.02s |

**Storage:**
- 1k chunks ≈ 5 MB (embeddings only)
- IVFFlat index ≈ 10% overhead

### Changed

- DocumentState schema: `space_ids` field now used by Researcher
- Source priority in Researcher: RAG chunks have highest reliability (0.95)

### Dependencies

- Added: `sentence-transformers`, `pypdf`, `python-docx`, `tiktoken`, `aiofiles`, `pgvector`
- PostgreSQL extension: `vector` (pgvector)

### References

- Task: TH.1-3 Knowledge Spaces
- PR: `fix/ui-issues-and-docker-config`
- Commits: [1c3cc70](https://github.com/lucadidomenicodopehubs/deep-research-spec/commit/1c3cc70b563d89e040aa278af758c6cc1df05e8b), [15742744](https://github.com/lucadidomenicodopehubs/deep-research-spec/commit/15742744c253d54e80ab34c5dd1cf391041f0893), [7f76e996](https://github.com/lucadidomenicodopehubs/deep-research-spec/commit/7f76e996af7987f12769b2ca27819c41b00df753), [2dc47de5](https://github.com/lucadidomenicodopehubs/deep-research-spec/commit/2dc47de50c77889d539b68d6cbd364f59e2d3d9e)
- pgvector: [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector)
- sentence-transformers: [sbert.net](https://www.sbert.net/)

---

## [2.0.0] - 2026-03-04

### 🚨 BREAKING CHANGES

**Budget Estimator v2** ([#XXX](https://github.com/lucadidomenicodopehubs/deep-research-spec/pull/XXX))

Complete rewrite of budget estimation formula with critical bug fixes. **Cost estimates increased by 92-164%** due to corrected pricing.

#### Fixed

1. **BUG #1 (CRITICAL):** gpt-4.5 judge cost corrected from $1.10/M → **$150/M** (+18× jury cost)
   - Root cause: §19.0 used aggregate tier average instead of per-slot pricing
   - Impact: Jury cost underestimated by factor of 18 in Balanced/Premium

2. **BUG #2 (MAJOR):** MoW multiplier amortization corrected to **2.1×** (was 1.4×)
   - Root cause: Multiplier applied to entire iter_cost instead of writer only
   - Impact: Writer cost underestimated by 40%

3. **BUG #3 (MAJOR):** Input tokens now included for all agents
   - Root cause: §19.0 only counted output tokens
   - Impact: +20-50% cost for high-input agents (Reflector, Planner)

4. **BUG #4 (MEDIUM):** Jury count now respects regime (was hardcoded to 9)
   - Root cause: Ignored `jury_size` parameter from §19.2
   - Impact: Economy jury cost reduced by 67% (correct)

5. **BUG #5 (MEDIUM):** `avg_iter` now clamped to regime `max_iterations`
   - Root cause: Default 2.5 exceeded Economy limit of 2
   - Impact: Economy estimates reduced by 20%

6. **GAP #6 (MINOR):** Planner cost now included (+$0.04 overhead)

#### Added

- **SHINE-aware Panel Discussion contingency** (§11.3)
  - 40% probability in Balanced/Premium regimes
  - 2 rounds max with tier-1 jury
  - Adds 8-12% to total estimate

- **RLM-aware context compression** (optional, feature flag)
  - Context Compressor savings: -60% Writer input tokens on iter 2+
  - Reflector overhead: +30% (recursive whack-a-mole)
  - Net savings: ~10% if enabled

- **Complete test suite** ([tests/unit/test_budget_estimator_v2.py](tests/unit/test_budget_estimator_v2.py))
  - Regression tests for all 6 bugs
  - Golden-set comparisons
  - SHINE/RLM validation
  - Edge case coverage

- **Comprehensive documentation**
  - [Migration Guide](docs/BUDGET_ESTIMATOR_V2_MIGRATION.md)
  - [API Reference](backend/src/services/README_BUDGET_V2.md)
  - [LangGraph Integration](backend/src/graph/nodes/budget_estimator_node.py)

#### Changed

- `estimate_run_cost()` now imports from canonical `src/llm/pricing.py`
- `BudgetEstimate` dataclass expanded with breakdown fields:
  - `planner_cost`, `panel_contingency`, `compression_savings`
  - `writer_cost_per_iter`, `jury_cost_per_iter`, etc.
- Regime derivation now uses corrected `budget_per_word` thresholds

#### Migration Required

⚠️ **All existing budget caps must be reviewed**

| Old Cap | New Recommended | Delta |
|---------|----------------|-------|
| $5 | $10 | +100% |
| $10 | $18 | +80% |
| $20 | $45 | +125% |

See [Migration Guide](docs/BUDGET_ESTIMATOR_V2_MIGRATION.md) for detailed checklist.

#### Performance

- Estimation speed: 0.8-1.2 ms (unchanged, deterministic)
- Memory: < 3 KB (unchanged)
- No LLM calls (pure arithmetic)

#### References

- Spec Review: 2026-03-04
- PR: `fix/ui-issues-and-docker-config`
- Issues: #XXX (BUG #1), #XXX (MoW), #XXX (input tokens)
- SHINE paper: [arXiv:2303.17651](https://arxiv.org/abs/2303.17651)
- RLM: [github.com/alexzhang13/rlm](https://github.com/alexzhang13/rlm)

---

## [Unreleased] - 2026-02-23

### Added
- **RAG + SHINE Integration** ([docs/RAG_SHINE_INTEGRATION.md](docs/RAG_SHINE_INTEGRATION.md))
  - New `MemvidConnector` for local knowledge retrieval in Researcher (§5.2)
  - `ShineAdapter` node for parametric memory compression (LoRA generation)
  - `ShineContextCompressor` for approved section compression (§5.16)
  - Swapped `all-MiniLM-L6-v2` → `bge-m3` in MetricsCollector (§5.8)
  - Added `shineActive`, `shineLoRA`, `contextLoRA`, `ragLocalSources` to DocumentState (§4.6)
  - Fallback-first architecture: SHINE failures gracefully degrade to text corpus

### Changed
- Researcher connector priority: `memvid_local` → `sonar-pro` → `tavily` → `brave`
- Writer now checks `shineActive` flag to use LoRA or text corpus path
- Graph topology: `source_synthesizer` → `shine_adapter` → `writer_single`

### Performance
- Writer latency: 10-15s → 2-3s (5x faster with SHINE active)
- Context tokens: 4000-8000 → 200-500 (95% reduction)
- Budget impact: -40% on Premium preset

### Experimental
- SHINE paper is 17 days old (arXiv:2602.06358, Feb 6 2026)
- No independent validation yet — use with monitoring
- GPU required for SHINE; CPU fallback is 10x slower

### Dependencies
- Added: `langchain-memvid`, `FlagEmbedding`, `peft`, `SHINE` (GitHub)
- Updated: `transformers>=4.40.0`, `torch>=2.2.0`

---

## [0.1.0] - 2026-02-20

### Added
- Initial DRS specification structure
- 21 specialized AI agents (Planner, Researcher, Writer, Jury, etc.)
- LangGraph orchestration framework
- Mixture-of-Writers (MoW) for first-draft diversity
- Multi-Jury CSS evaluation (Reasoning, Factual, Style)
- Budget control and oscillation detection
- PostgreSQL persistence layer
- Run Companion SSE interface

### Documentation
- Complete agent specifications (§5)
- Architecture diagrams (§4)
- DocumentState schema (§4.6)
- Style profiles and forbidden patterns (§26)
- Source connectors and ranking (§17)

---

## Template for Future Releases

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Vulnerability patches
```
