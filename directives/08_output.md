# Direttiva 08 — Output & QA

## Obiettivo

Implementare la pipeline di output post-loop: PostQA (coerenza globale + reference check), LengthAdjuster, Publisher (export DOCX/PDF/Markdown/LaTeX/JSON), e FeedbackCollector. Dopo questa fase il documento è esportabile.

## Pre-requisiti

- Fasi 5+6+7 completate (tutte le sezioni approvate, sources verificate)

## Spec da Leggere

| File | Sezione | Cosa estrarre |
|------|---------|--------------|
| `output/05_agents.md` | §5.19 (PostQA) | Cross-section check: reference consistency, numbering, orphan citations, bibliography completeness |
| `output/05_agents.md` | §5.20 (Publisher) | Deterministic, accepted formats: docx/pdf/markdown/latex/json, MinIO upload, pre-signed URL generation |
| `output/05_agents.md` | §5.22 (LengthAdjuster) | Total word count ±10% tolerance, trim/expand per section, proportional redistribution |
| `output/05_agents.md` | §5.24 (FeedbackCollector) | Emit RunReport JSON, run_metrics, section_metrics, cost breakdown |
| `output/30_output.md` | §30.1–§30.5 | Output format specs: Markdown structure, DOCX template, PDF via WeasyPrint, LaTeX template, JSON schema |
| `output/30_output.md` | §30.6 | TOC generation, figure/table numbering, cross-reference linking |
| `output/15_coherence_guard.md` | §15.4 | Post-document coherence scan (runs after all sections approved, before publish) |

## Conflitti da Applicare

- **C15**: LengthAdjuster model = `anthropic/claude-opus-4-5`, fallbacks `["anthropic/claude-sonnet-4", "google/gemini-2.5-pro"]`

## Output Atteso

### File da creare

```
src/graph/nodes/post_qa.py             # PostQA cross-document checks
src/graph/nodes/length_adjuster.py     # Word count adjustment ±10%
src/graph/nodes/publisher.py           # Multi-format export + MinIO upload
src/graph/nodes/feedback_collector.py  # RunReport generation
```

### `src/graph/nodes/post_qa.py` — Struttura richiesta

```python
async def post_qa_node(state: DocumentState) -> dict:
    # 1. Cross-reference check: all [src:id] tags map to existing sources
    # 2. Bibliography completeness: every cited source has full metadata
    # 3. Section numbering continuity
    # 4. Orphan citation detection (cited but not in sources)
    # 5. Length check: total_word_count within ±10% of target_words
    # 6. Final coherence scan across all approved sections
    # OUTPUT: {"post_qa_issues": [...], "total_word_count": int}
```

### `src/graph/nodes/publisher.py` — Struttura richiesta

```python
async def publisher_node(state: DocumentState) -> dict:
    formats = state["config"]["output_formats"]  # ["docx", "pdf", ...]
    export_urls = {}
    for fmt in formats:
        content = _assemble_document(state["approved_sections"], fmt)
        url = await _upload_to_minio(content, state["doc_id"], fmt)
        export_urls[fmt] = url
    return {"export_urls": export_urls, "status": "completed"}
```

### `src/graph/nodes/feedback_collector.py` — Struttura richiesta

```python
def feedback_collector_node(state: DocumentState) -> dict:
    report = {
        "doc_id": state["doc_id"],
        "total_cost_usd": state["budget"]["accumulated_cost"],
        "total_sections": len(state["approved_sections"]),
        "avg_css": ...,
        "avg_iterations": ...,
        "section_reports": [...],  # per-section css/iterations/cost
        "warnings": state.get("warnings", []),
    }
    return {"run_report": report}
```

## Script di Validazione

```bash
python -c "
from src.graph.nodes.post_qa import post_qa_node
from src.graph.nodes.publisher import publisher_node
from src.graph.nodes.feedback_collector import feedback_collector_node
print('OK: output pipeline nodes importable')
"
```
