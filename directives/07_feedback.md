# Direttiva 07 — Feedback Loop

## Obiettivo

Implementare il ciclo di feedback post-jury: Reflector → OscillationDetector → SpanEditor/DiffMerger, CoherenceGuard, ContextCompressor, WriterMemory, e SectionCheckpoint. Questo è il cuore dell'iterazione di miglioramento.

## Pre-requisiti

- Fase 4 completata (routing functions per reflector/oscillation)
- Fase 6 completata (jury e aggregator producono verdicts che alimentano il reflector)

## Spec da Leggere

| File | Sezione | Cosa estrarre |
|------|---------|--------------|
| `output/12_reflector.md` | §12.1 | Reflector agent spec: INPUT/OUTPUT/CONSTRAINTS, scope derivation logic |
| `output/12_reflector.md` | §12.2 | Scope (SURGICAL/PARTIAL/FULL) derivation rules con soglie esplicite |
| `output/12_reflector.md` | §12.3 | ReflectorFeedback schema: {section_idx, feedbacks: list, scope, css_at_reflection} |
| `output/12_reflector.md` | §12.4 | Reflector prompt template |
| `output/12_reflector.md` | §12.5 | `route_after_reflector()` e `route_after_oscillation()` — canonical |
| `output/13_oscillation_detector.md` | §13.1–§13.4 | Cosine similarity window, trigger threshold ≥0.92, soft_limit/hard_limit |
| `output/05_agents.md` | §5.11 (SpanEditor) | Surgical edits, JSON diff format, max 5 spans per invocation |
| `output/05_agents.md` | §5.12 (DiffMerger) | Deterministic, apply SpanEditor patches to draft |
| `output/05_agents.md` | §5.15 (CoherenceGuard) | Cross-section contradiction detection, SOFT→auto-resolve, HARD→await_human |
| `output/05_agents.md` | §5.16 (ContextCompressor) | Distance-based compression: verbatim(1-2), summary(3-5), thematic(6+) |
| `output/05_agents.md` | §5.17 (WriterMemory) | Forbidden hits, glossary, citation_ratio, style_drift_idx update |
| `output/05_agents.md` | §5.21 (SectionCheckpoint) | Deterministic, save approved section to Store, emit SECTION_APPROVED SSE |
| `output/14_context_compressor.md` | §14.1–§14.3 | Compression algorithm, distance formula, priority preservation for load-bearing claims |
| `output/15_coherence_guard.md` | §15.1–§15.3 | Embedding comparison, SOFT/HARD thresholds, DeBERTa NLI for contradiction scoring |
| `output/16_writer_memory.md` | §16.1–§16.3 | Memory accumulation rules, style drift index, cross-section learning |

## Conflitti da Applicare

- **C13**: CoherenceConflict fields — mappare `claim_new→claim_a`, `existing_section_index→section_b_idx`
- §12.5 è CANONICAL per `route_after_reflector()` — scope `FULL` → `await_human`, `SURGICAL`/`PARTIAL` → `oscillation_check`
- Oscillation routing: `SURGICAL→span_editor`, `PARTIAL→writer`, `FULL→await_human` (§0.3 resolved values)

## Output Atteso

### File da creare

```
src/graph/nodes/reflector.py           # Reflector node (LLM)
src/graph/nodes/oscillation_detector.py # Cosine similarity oscillation check
src/graph/nodes/span_editor.py         # SURGICAL edits (LLM)
src/graph/nodes/diff_merger.py         # Apply patches (deterministic)
src/graph/nodes/coherence_guard.py     # Cross-section contradiction (LLM)
src/graph/nodes/context_compressor.py  # Distance-based compression (qwen/qwen3-7b)
src/graph/nodes/writer_memory.py       # Memory accumulation (deterministic)
src/graph/nodes/section_checkpoint.py  # Save to Store + emit SSE
```

### `src/graph/nodes/reflector.py` — Struttura richiesta

```python
async def reflector_node(state: DocumentState) -> dict:
    # INPUT: current_draft, jury_verdicts, css_content, css_style
    # Derive scope: SURGICAL if css >= threshold-0.05, PARTIAL if css >= threshold-0.15, else FULL
    # Generate structured feedbacks list
    # OUTPUT: {"reflector_output": {"scope": ..., "feedbacks": [...], "css_at_reflection": ...}}
```

### `src/graph/nodes/oscillation_detector.py` — Struttura richiesta

```python
def oscillation_detector_node(state: DocumentState) -> dict:
    # Compare current_draft embedding vs last 3 drafts (cosine similarity)
    # If similarity >= 0.92 → oscillation_detected = True
    # Track soft_limit (3 hits) and hard_limit (5 hits)
    # OUTPUT: {"oscillation_detected": bool, "oscillation_count": int}
```

### `src/graph/nodes/context_compressor.py` — Struttura richiesta

```python
async def context_compressor_node(state: DocumentState) -> dict:
    # For each approved section, compute distance = current_section_idx - section_idx
    # distance 1-2: verbatim
    # distance 3-5: structured summary (80-120 words)
    # distance ≥ 6: thematic extract (claims + citations only)
    # Preserve load-bearing claims regardless of distance
    # OUTPUT: {"context_window": compressed_text}
```

## Script di Validazione

```bash
python -c "
from src.graph.nodes.reflector import reflector_node
from src.graph.nodes.oscillation_detector import oscillation_detector_node
from src.graph.nodes.coherence_guard import coherence_guard_node
from src.graph.nodes.context_compressor import context_compressor_node
print('OK: feedback loop nodes importable')
"
```
