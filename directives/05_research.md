# Direttiva 05 — Research Pipeline

## Obiettivo

Implementare la pipeline di ricerca: Researcher → CitationManager → CitationVerifier → SourceSanitizer → SourceSynthesizer. Anche ResearcherTargeted per re-research mirata post-draft.

## Pre-requisiti

- Fase 4 completata (grafo compilabile, nodi registrati come stub)

## Spec da Leggere

| File | Sezione | Cosa estrarre |
|------|---------|--------------|
| `output/05_agents.md` | §5.2 (Researcher) | INPUT/OUTPUT/CONSTRAINTS, connector cascade, dedup, diversity_score |
| `output/05_agents.md` | §5.3 (CitationManager) | Deterministic, citation_map, bibliography, handle ISBN |
| `output/05_agents.md` | §5.4 (CitationVerifier) | HTTP HEAD check, DOI resolution, DeBERTa NLI entailment ≥0.80, ghost_citations |
| `output/05_agents.md` | §5.5 (SourceSanitizer) | 3-stage injection guard: regex→XML wrap→jailbreak scan |
| `output/05_agents.md` | §5.6 (SourceSynthesizer) | Compress to 40%, clear `targeted_research_active`, claim tagging `[src:id]` |
| `output/05_agents.md` | §5.23 (ResearcherTargeted) | Sets `targeted_research_active=True`, dedup vs existing sources |
| `output/17_research_layer.md` | §17.1–§17.8 | Connectors: academic/institutional/web/social/upload, SourceRanker, diversity formula |
| `output/18_citations.md` | §18.1–§18.4 | Citation formats: APA/Harvard/Chicago/Vancouver, NLI entailment, ISBN handling |
| `output/22_security.md` | §22.3 | PII detection before external calls (presidio + spaCy) |

## Conflitti da Applicare

- **C01**: `source_type` enum → `"web"`, `"upload"` (non `"general"`, `"uploaded"`)
- **C06**: `max_sources` default → 15 (da config, non hardcoded)
- **C08**: Output di SourceSynthesizer → scrivere nel campo `synthesized_sources` di DocumentState

## Output Atteso

### File da creare

```
src/graph/nodes/researcher.py          # Researcher node
src/graph/nodes/citation_manager.py    # CitationManager node (deterministic)
src/graph/nodes/citation_verifier.py   # CitationVerifier node (DeBERTa NLI)
src/graph/nodes/source_sanitizer.py    # SourceSanitizer node (3-stage)
src/graph/nodes/source_synthesizer.py  # SourceSynthesizer node
src/connectors/base.py                 # SourceConnector ABC
src/connectors/tavily.py               # Tavily search
src/connectors/brave.py                # Brave search
src/connectors/crossref.py             # CrossRef DOI
src/connectors/semantic_scholar.py     # Semantic Scholar
src/connectors/arxiv.py                # ArXiv
src/connectors/scraper.py              # BS4 + Playwright fallback
src/security/injection_guard.py        # Regex patterns for source sanitization
```

### Pattern di Dependency Injection (§2.11)

```python
class ResearcherNode:
    def __init__(self, llm: LLMClient, connectors: list[SourceConnector]): ...
    async def run(self, state: DocumentState) -> dict: ...
```

## Script di Validazione

```bash
python -c "
from src.graph.nodes.researcher import researcher_node
from src.graph.nodes.source_sanitizer import source_sanitizer_node
print('OK: research pipeline nodes importable')
"
```
