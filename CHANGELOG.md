# Changelog

All notable changes to the Deep Research Spec (DRS) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
