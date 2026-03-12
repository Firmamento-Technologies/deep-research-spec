# Direttiva 06 — Writer & Jury System

## Obiettivo

Implementare il nodo Writer (con MoW/Fusor interni), PostDraftAnalyzer, il sistema Jury a 3 mini-giurie (Reasoning/Factual/Style), l'Aggregator CSS, la Panel Discussion, il MetricsCollector, e StyleLinter/StyleFixer.

## Pre-requisiti

- Fase 4 completata (grafo compilabile)
- Fase 3 completata (budget thresholds per regime selection)

## Spec da Leggere

| File | Sezione | Cosa estrarre |
|------|---------|--------------|
| `output/05_agents.md` | §5.7 (Writer) | INPUT/OUTPUT/CONSTRAINTS, forbidden words, word count tolerance ±10%, structured prompt |
| `output/05_agents.md` | §5.8 (Fusor) | Best-element extraction, merge logic |
| `output/05_agents.md` | §5.13 (PostDraftAnalyzer) | Gap detection, if gap → targeted researcher |
| `output/07_mixture_of_writers.md` | §7.1 | MoW activation: `quality_preset != economy AND mow_enabled AND target_words >= 1500` |
| `output/07_mixture_of_writers.md` | §7.2–§7.3 | 3 writers (A/B/C), asyncio.gather, temperature variance |
| `output/07_mixture_of_writers.md` | §7.4–§7.5 | MicroJury per draft, Fusor best_elements extraction |
| `output/07_mixture_of_writers.md` | §7.6 | **AUTHORITATIVE**: MoW è INTERAMENTE INTERNO al nodo `writer`. Nessun nodo graph extra. |
| `output/08_jury_system.md` | §8.0–§8.1 | 3 mini-juries: Reasoning (R1-R3), Factual (F1-F3), Style (S1-S3), parallel via asyncio.gather |
| `output/08_jury_system.md` | §8.2–§8.4 | Per-jury prompt templates, model assignments, DimensionScores |
| `output/08_jury_system.md` | §8.5 | Cascading tiers: tier1 first → tier2/3 only if split. Disabled when `jury_size < 3` |
| `output/08_jury_system.md` | §8.6 | VerdictJSON schema, structured_output enforcement |
| `output/09_css_aggregator.md` | §9.1 | CSS formula: `CSS_dim = Σ(pass_i × confidence_weight_i) / Σ(confidence_weight_i)` |
| `output/09_css_aggregator.md` | §9.2 | `JURY_WEIGHTS = {"reasoning": 0.35, "factual": 0.45, "style": 0.20}` |
| `output/09_css_aggregator.md` | §9.4 | `route_after_aggregator()` — canonical implementation |
| `output/09_css_aggregator.md` | §9.5 | Panel Discussion self-loop, `route_after_panel_internal()` |
| `output/11_panel_discussion.md` | §11.1–§11.3 | Panel flow: structured_debate → jury_revote → check CSS → loop or escalate |
| `output/05_agents.md` | §5.9 (StyleLinter) | DeBERTa + textstat, deterministic, 7 checks, violation schema |
| `output/05_agents.md` | §5.10 (StyleFixer) | LLM fix of lint violations, max 2 fixes per violation |
| `output/05_agents.md` | §5.14 (MetricsCollector) | Deterministic, section_metrics dict, word_count/readability/lexical_diversity |
| `output/28_llm_assignments.md` | §28.2 | All model assignments for writer, fusor, judges R/F/S |
| `output/26_style_profiles.md` | §26.1–§26.6 | Style preset YAML: L1/L2/L3 rules per profile |
| `output/03b_style_calibration.md` | §3b | Forbidden words, readability targets, citation density per profile |

## Conflitti da Applicare

- **C04**: judge_f3 = `openai/gpt-4o-search-preview` (non `perplexity/sonar-pro`)
- **C05**: Style jury tier cascade: tier1=llama-70b, tier2=mistral-large, tier3=gpt-4.5
- **C07**: Writer fallback[2] = `google/gemini-2.5-pro`
- **C14**: Quality preset lowercase in config, capitalized in DocumentState

## Output Atteso

### File da creare

```
src/graph/nodes/writer.py              # Writer node (MoW/Fusor internal)
src/graph/nodes/post_draft_analyzer.py # Gap detection → targeted research
src/graph/nodes/jury.py                # 3 mini-juries, cascading tiers
src/graph/nodes/aggregator.py          # CSS computation + SectionCSSReport
src/graph/nodes/panel_discussion.py    # Panel self-loop
src/graph/nodes/style_linter.py        # Deterministic lint (DeBERTa + textstat)
src/graph/nodes/style_fixer.py         # LLM style fix
src/graph/nodes/metrics_collector.py   # Section metrics
src/graph/nodes/fusor.py               # NOT a graph node — used internally by writer.py
```

### `src/graph/nodes/writer.py` — Struttura interna

```python
async def writer_node(state: DocumentState) -> dict:
    if _should_activate_mow(state):
        drafts = await asyncio.gather(
            _write_variant(state, "A", temp=0.4),
            _write_variant(state, "B", temp=0.7),
            _write_variant(state, "C", temp=1.0),
        )
        verdicts = await _micro_jury(drafts, state)
        draft = await _fuse(drafts, verdicts, state)
    else:
        draft = await _write_single(state)
    return {"current_draft": draft, "current_iteration": state["current_iteration"] + 1}
```

### `src/graph/nodes/jury.py` — Struttura richiesta

```python
async def jury_node(state: DocumentState) -> dict:
    jury_size = state["budget"]["jury_size"]
    # asyncio.gather across all active mini-juries
    r_verdicts, f_verdicts, s_verdicts = await asyncio.gather(
        _run_mini_jury("reasoning", state, jury_size),
        _run_mini_jury("factual", state, jury_size),
        _run_mini_jury("style", state, jury_size),
    )
    return {"jury_verdicts": r_verdicts + f_verdicts + s_verdicts}
```

## Script di Validazione

```bash
python -c "
from src.graph.nodes.writer import writer_node
from src.graph.nodes.jury import jury_node
from src.graph.nodes.aggregator import aggregator_node
print('OK: writer/jury/aggregator nodes importable')
"
```
