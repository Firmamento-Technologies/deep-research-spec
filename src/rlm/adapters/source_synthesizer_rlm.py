"""RLM adapter for SourceSynthesizer §5.6.

Replaces the single-prompt Sonnet compression with a goal-directed
RLM navigation pass that compresses the corpus toward the specific
section_scope, prioritising DeBERTa-verified claims (nli_entailment > 0.80).

DocumentState contract:
  CONSUMES: current_sources, outline, current_section_idx, config
  PRODUCES: compressed_corpus (str), compression_ratio_achieved (float),
            skipped_source_ids (list[str])

Feature flag: config.features.rlm_source_synthesizer
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from src.rlm.runtime import get_rlm_runtime
from src.rlm.budget_bridge import emit_cost_entries

logger = logging.getLogger(__name__)


async def source_synthesizer_rlm_node(state: dict) -> dict:
    """Goal-directed corpus compression using RLM.

    Falls back to original source_synthesizer_node when:
    - Feature flag is off
    - len(current_sources) < 2  (§5.6 constraint)
    """
    features = state.get("config", {}).get("features", {})
    if not features.get("rlm_source_synthesizer", False):
        return await _fallback(state)

    sources = state.get("current_sources", [])
    if len(sources) < 2:
        # §5.6: NEVER run if len(sanitized_sources) < 2
        return await _fallback(state)

    section_idx = state.get("current_section_idx", 0)
    outline = state.get("outline", [])
    if section_idx >= len(outline):
        return await _fallback(state)

    section = outline[section_idx]
    section_scope = section.get("scope", "")
    target_ratio = state.get("config", {}).get("target_compression_ratio", 0.40)

    context = {
        "sources": [
            {
                "id": i,
                "title": s.get("title", ""),
                "source_type": s.get("source_type", ""),
                "reliability_score": s.get("reliability_score", 0.0),
                "nli_entailment": s.get("nli_entailment"),
                "snippet": s.get("abstract", "")[:400],
            }
            for i, s in enumerate(sources)
        ],
        "source_texts": {
            str(i): s.get("full_text", s.get("abstract", ""))[:6000]
            for i, s in enumerate(sources)
        },
        "section_scope": section_scope,
        "target_compression_ratio": target_ratio,
        "section_idx": section_idx,
        "n_sources": len(sources),
    }

    task = (
        f'Compress this source corpus for writing a section on: "{section_scope}"\n\n'
        f"Goal: produce a compressed_corpus string with:\n"
        f"  - All claims tagged inline: claim text [src:N]\n"
        f"  - Semantically deduplicated claims (merge confirmed_by fields)\n"
        f"  - Target compression ratio: {target_ratio:.0%} of original token count\n"
        f"  - Prioritise sources with nli_entailment > 0.80 (DeBERTa-verified)\n"
        f"  - Prioritise sources with reliability_score > 0.70\n\n"
        f"Strategy:\n"
        f"  1. Scan sources metadata to identify thematically relevant sources\n"
        f"  2. Use llm_query() to read full text of top relevant sources\n"
        f"  3. Extract and deduplicate key claims per source\n"
        f"  4. Assemble compressed_corpus with source tags\n\n"
        f"Set final_answer = {{\"compressed_corpus\": \"...\", "
        f'"compression_ratio_achieved": 0.0, "skipped_source_ids": []}}'
    )

    rlm = get_rlm_runtime(
        root_model=state.get("config", {}).get("rlm_root_model", "claude-sonnet-4-5"),
        sub_model=state.get("config", {}).get("rlm_sub_model", "claude-haiku-3-5"),
        max_subcalls=20,
        cost_hard_limit=0.25,
        timeout_seconds=90,
    )

    result = await rlm.run(context=context, task_instruction=task)
    await emit_cost_entries(state=state, agent="source_synthesizer_rlm", rlm_result=result)

    output = result.output
    if not isinstance(output, dict):
        logger.warning(
            "SourceSynthesizerRLM: output is not a dict (method=%s), falling back.",
            result.method,
        )
        return await _fallback(state)

    compressed = output.get("compressed_corpus", "")
    if not compressed:
        logger.warning("SourceSynthesizerRLM: empty compressed_corpus, falling back.")
        return await _fallback(state)

    return {
        "compressed_corpus": compressed,
        "compression_ratio_achieved": float(output.get("compression_ratio_achieved", 0.0)),
        "skipped_source_ids": output.get("skipped_source_ids", []),
    }


async def _fallback(state: dict) -> dict:
    try:
        from src.nodes.source_synthesizer import source_synthesizer_node
        return await source_synthesizer_node(state)
    except ImportError:
        logger.error("src.nodes.source_synthesizer not found — returning empty corpus.")
        return {
            "compressed_corpus": "",
            "compression_ratio_achieved": 0.0,
            "skipped_source_ids": [],
        }
