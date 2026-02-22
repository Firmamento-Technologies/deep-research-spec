"""
Context Compressor Node — SHINE-enhanced implementation.

Replaces the pure LLM-based §14 ContextCompressor with a hybrid strategy:

  VERBATIM tier (distance 1–2, last 2 approved sections):
    → Full text encoded into SHINE LoRA adapter (~0.3s, zero token cost)
    → Adapter stored in AdapterRegistry (Redis + MinIO)
    → Only load-bearing claims [LBC:...] remain in text context
    → Writer receives adapter via DocumentState.active_lora_section_idxs
    → Token savings: ~70–80% reduction on Writer/Jury/Reflector input

  STRUCTURED_SUMMARY tier (distance 3–5):
    → LLM compression via qwen/qwen3-7b (§14.5)
    → Max 120 words, key claims + thesis preserved
    → Already small impact; LLM cost is negligible here

  THEMATIC_EXTRACT tier (distance ≥ 6):
    → Title + 40 words + load-bearing claims only
    → No LLM call (deterministic truncation)

Spec references:
    §14  — ContextCompressor base specification
    §30  — SHINE Integration (docs/30_shine_integration.md)
    §5.7 — Writer (consumes approved_sections_context + active_lora)

State fields produced:
    compressed_context          CompressedContext  — text-based context (tiers 2+3)
    active_lora_section_idxs   list[int]          — sections encoded as LoRA adapters
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# §14.6 — Writer context budget constants
CONTEXT_BUDGET_FRACTION   = 0.15
SAFETY_FACTOR             = 0.45
WRITER_CONTEXT_WINDOW     = 200_000   # Claude Opus 4.5


async def run(state: dict) -> dict:
    """
    SHINE-enhanced Context Compressor node.

    Entry point for LangGraph node registration::

        from src.graph.nodes import context_compressor
        g.add_node("context_compressor", context_compressor.run)

    Args:
        state: DocumentState (TypedDict)

    Returns:
        Partial DocumentState patch:
          - compressed_context:          CompressedContext dict
          - active_lora_section_idxs:    list[int]
    """
    from src.shine.hypernetwork import SHINEHypernetwork
    from src.shine.adapter_registry import AdapterRegistry
    from src.shine.chunker import TextChunker

    current_idx:       int  = state["current_section_idx"]
    approved_sections: list = state.get("approved_sections", [])
    outline:           list = state["outline"]
    doc_id:            str  = state["run_id"]
    shine_enabled:     bool = state.get("shine_enabled", True)

    # §14.4 — never invoke on section 0
    if current_idx == 0 or not approved_sections:
        logger.debug("[context_compressor] Section 0 or no prior sections — skipping")
        return {
            "compressed_context": None,
            "active_lora_section_idxs": [],
        }

    # Initialise SHINE stack (lazy — model loads on first actual call)
    shine    = SHINEHypernetwork() if shine_enabled else None
    registry = _build_registry(state) if shine_enabled else None
    chunker  = TextChunker(tokenizer=shine.tokenizer) if shine_enabled else None

    compressed_sections: list = []
    active_lora_idxs:    list = list(state.get("active_lora_section_idxs", []))

    for section in approved_sections:
        section_idx: int = section["idx"]
        distance:    int = current_idx - section_idx
        tier:        str = _resolve_tier(distance)

        if tier == "verbatim" and shine_enabled:
            entry = await _handle_verbatim_shine(
                section, section_idx, distance, outline, current_idx,
                doc_id, shine, registry, chunker, active_lora_idxs,
            )
        else:
            entry = await _handle_llm_compression(
                section, section_idx, distance, outline, current_idx, tier,
            )

        compressed_sections.append(entry)

    budget = _compute_budget()
    total_tokens = sum(
        len(s["compressed_text"].split()) * 1.3
        for s in compressed_sections
    )
    utilization = total_tokens / max(budget, 1)

    # §14.6 — if over budget, drop thematic sections to title-only
    if utilization > 1.0:
        logger.warning(
            "[context_compressor] Budget exceeded (%.2f) — tightening thematic_extract",
            utilization,
        )
        for s in compressed_sections:
            if s["tier"] == "thematic_extract":
                title = outline[s["section_idx"]]["title"]
                s["compressed_text"] = f"[{title}]"
        total_tokens = sum(len(s["compressed_text"].split()) * 1.3 for s in compressed_sections)
        utilization  = total_tokens / max(budget, 1)

    return {
        "compressed_context": {
            "sections": sorted(compressed_sections, key=lambda x: x["section_idx"]),
            "total_tokens_estimated": int(total_tokens),
            "budget_tokens": budget,
            "budget_utilization_ratio": utilization,
        },
        "active_lora_section_idxs": sorted(set(active_lora_idxs)),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _handle_verbatim_shine(
    section:         dict,
    section_idx:     int,
    distance:        int,
    outline:         list,
    current_idx:     int,
    doc_id:          str,
    shine,
    registry,
    chunker,
    active_lora_idxs: list,
) -> dict:
    """
    Encode a verbatim-tier section into a SHINE LoRA adapter.
    Checks registry cache first to avoid redundant encoding.
    """
    existing = registry.load(doc_id, section_idx)

    if existing is not None:
        logger.debug("[context_compressor] SHINE cache HIT for section %d", section_idx)
    else:
        logger.info(
            "[context_compressor] SHINE encoding section %d (distance=%d)...",
            section_idx, distance,
        )
        text   = section["content"]
        chunks = chunker.split(text)

        if len(chunks) == 1:
            adapter = shine.generate_adapter(chunks[0])
        else:
            logger.debug(
                "[context_compressor] Section %d split into %d SHINE chunks",
                section_idx, len(chunks),
            )
            adapters = [shine.generate_adapter(c) for c in chunks]
            adapter  = shine.merge_adapters(adapters)

        registry.store(doc_id, section_idx, adapter)

    if section_idx not in active_lora_idxs:
        active_lora_idxs.append(section_idx)

    lbc_text = _extract_lbc_text(section, outline, current_idx)

    return {
        "section_idx":          section_idx,
        "title":                outline[section_idx]["title"],
        "tier":                 "verbatim_shine",
        "distance":             distance,
        "compressed_text":      lbc_text,
        "load_bearing_claims":  section.get("load_bearing_claims", []),
        "original_word_count":  len(section["content"].split()),
        "compressed_word_count": len(lbc_text.split()),
        "adapter_available":    True,
    }


async def _handle_llm_compression(
    section:     dict,
    section_idx: int,
    distance:    int,
    outline:     list,
    current_idx: int,
    tier:        str,
) -> dict:
    """
    LLM-based compression for structured_summary (d=3–5) and
    thematic_extract (d≥6) tiers. These sections are already compressed;
    token cost here is negligible.

    TODO: Replace stub with qwen/qwen3-7b call via src/llm/client.py
    when LLM client is implemented (currently missing — see §28).
    """
    content = section.get("content", "")
    title   = outline[section_idx]["title"]

    if tier == "structured_summary":
        # §14.1 — max 120 words: take first 2 paragraphs
        paragraphs   = [p.strip() for p in content.split("\n\n") if p.strip()]
        summary_text = " ".join(paragraphs[:2])[:700]
    else:
        # thematic_extract — §14.1: title + 40 words + load-bearing claims
        words        = content.split()[:40]
        summary_text = f"[{title}] " + " ".join(words) + "..."

    return {
        "section_idx":          section_idx,
        "title":                title,
        "tier":                 tier,
        "distance":             distance,
        "compressed_text":      summary_text,
        "load_bearing_claims":  section.get("load_bearing_claims", []),
        "original_word_count":  len(content.split()),
        "compressed_word_count": len(summary_text.split()),
        "adapter_available":    False,
    }


def _resolve_tier(distance: int) -> str:
    """§14.1 tier resolution by distance."""
    if distance <= 2:
        return "verbatim"
    if distance <= 5:
        return "structured_summary"
    return "thematic_extract"


def _extract_lbc_text(section: dict, outline: list, current_idx: int) -> str:
    """
    Build the minimal text context for a SHINE-encoded section.
    Full content is in the LoRA adapter; only load-bearing claims [LBC:...]
    remain in the token budget to preserve logical dependencies across sections.
    """
    claims = section.get("load_bearing_claims", [])
    if not claims:
        # Fallback: first + last paragraph as minimal anchor
        content    = section.get("content", "")
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if len(paragraphs) <= 2:
            return content
        return (
            paragraphs[0]
            + "\n\n[...full content encoded in LoRA adapter...]\n\n"
            + paragraphs[-1]
        )

    lines = [
        f"[LBC:{c.get('claim_type', 'factual')}] {c['text']}"
        for c in claims
    ]
    return (
        "[Section fully encoded in LoRA adapter — load-bearing claims below]\n"
        + "\n".join(lines)
    )


def _build_registry(state: dict):
    """Instantiate AdapterRegistry with DRS storage clients."""
    from src.shine.adapter_registry import AdapterRegistry
    try:
        from src.storage.redis_cache import get_redis_client
        redis = get_redis_client()
    except Exception:
        redis = None

    try:
        from src.storage.minio import get_minio_client
        minio = get_minio_client()
    except Exception:
        minio = None

    return AdapterRegistry(
        redis_client=redis,
        minio_client=minio,
        enable_minio_persistence=True,
    )


def _compute_budget() -> int:
    """§14.6 — 15% of Writer context window reserved for prior sections."""
    mecw = int(WRITER_CONTEXT_WINDOW * SAFETY_FACTOR)
    return int(mecw * CONTEXT_BUDGET_FRACTION)
