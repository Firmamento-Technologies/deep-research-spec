"""Writer node — generates section content from gathered sources.

The Writer receives a section with populated search_results and uses an LLM
to generate a well-structured, properly cited Markdown draft. The draft is
then presented to the user for approval (HITL).

Key responsibilities:
- Format sources as numbered citations
- Build context-rich prompt with section scope + sources
- Call LLM (writer model) to generate Markdown content
- Validate word count against target
- Track cost and update budget
- Emit SSE events for progress and HITL approval

The Writer does NOT critique its own output — that's the Critic's job.
It simply generates a draft and waits for approval before proceeding.

Spec: §13 Writer node, §19 Budget tracking, §20 HITL
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.state import ResearchState, Section

from src.llm.client import get_llm_client, LLMError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "../../..", "prompts", "writer_system.txt"
)

WORD_COUNT_TOLERANCE = 0.15  # ±15% of target_words
MIN_WORD_COUNT = 100          # Absolute minimum


# ---------------------------------------------------------------------------
# Writer Node
# ---------------------------------------------------------------------------

async def writer_node(state: ResearchState) -> dict:
    """Generate section content and wait for user approval.

    Flow:
    1. Get current section from state
    2. Load writer system prompt
    3. Build user prompt with section scope + formatted sources
    4. Call LLM (node_id='writer_single') to generate Markdown
    5. Validate word count
    6. Update section.content, section.word_count, section.cost_usd
    7. Emit SSE: SECTION_DRAFTED, HUMAN_REQUIRED (section_approval)
    8. Wait for SECTION_APPROVED event
    9. Update section.status = 'approved'

    Args:
        state: ResearchState with current_section index.

    Returns:
        Partial state update with sections[i] content populated.

    Raises:
        ValueError: If current_section is out of bounds.
        LLMError: If content generation fails.
    """
    doc_id         = state["doc_id"]
    sections       = state.get("sections", [])
    current_idx    = state.get("current_section", 0)
    target_words   = state.get("target_words", 5000)
    style_profile  = state.get("style_profile", "academic")
    broker         = state.get("broker")

    if current_idx >= len(sections):
        raise ValueError(
            f"current_section={current_idx} out of bounds (sections={len(sections)})"
        )

    section = sections[current_idx]

    logger.info(
        "[%s] Writer started for section %d: '%s' (target=%d words)",
        doc_id, current_idx, section.title, section.target_words,
    )

    t0 = time.monotonic()

    # Emit NODE_STARTED
    if broker:
        await broker.emit(doc_id, "NODE_STARTED", {
            "node": "writer",
            "section_idx": current_idx,
            "section_title": section.title,
        })

    # --- 1. Load system prompt ---
    system_prompt = _load_prompt()

    # --- 2. Build user prompt ---
    user_prompt = _build_user_prompt(section, style_profile)

    # --- 3. Generate content via LLM ---
    content, llm_cost = await _generate_content(
        state=state,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        section=section,
    )

    # --- 4. Validate word count ---
    word_count = _count_words(content)
    _validate_word_count(word_count, section.target_words, section.title)

    # --- 5. Update section ---
    section.content = content
    section.word_count = word_count
    section.cost_usd = llm_cost
    section.status = "drafting"

    logger.info(
        "[%s] Writer generated %d words (target=%d, cost=$%.4f)",
        doc_id, word_count, section.target_words, llm_cost,
    )

    # --- 6. Emit SECTION_DRAFTED + HUMAN_REQUIRED ---
    if broker:
        await broker.emit(doc_id, "SECTION_DRAFTED", {
            "section_idx": current_idx,
            "word_count": word_count,
            "target_words": section.target_words,
            "content_preview": content[:200] + "...",
        })

        await broker.emit(doc_id, "HUMAN_REQUIRED", {
            "type": "section_approval",
            "payload": {
                "section_idx": current_idx,
                "title": section.title,
                "content": content,
                "word_count": word_count,
            },
        })

    # --- 7. Wait for approval ---
    approved_content = await _wait_for_approval(
        broker, doc_id, current_idx, content
    )

    section.content = approved_content
    section.status = "approved"

    # --- 8. Emit NODE_COMPLETED ---
    duration = time.monotonic() - t0
    if broker:
        await broker.emit(doc_id, "NODE_COMPLETED", {
            "node": "writer",
            "section_idx": current_idx,
            "duration_s": round(duration, 2),
            "word_count": word_count,
            "cost_usd": llm_cost,
        })

    logger.info(
        "[%s] Writer completed in %.2fs (section %d approved)",
        doc_id, duration, current_idx,
    )

    # Return state updates
    return {
        "sections": sections,  # Updated in-place
        "status": "writing",
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_prompt() -> str:
    """Load writer system prompt from prompts/writer_system.txt."""
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning("Writer prompt file not found: %s (using fallback)", PROMPT_PATH)
        return _FALLBACK_PROMPT


def _build_user_prompt(section, style_profile: str) -> str:
    """Build the user prompt with section scope and formatted sources.

    Returns:
        Formatted prompt string.
    """
    # Format sources as numbered list
    sources_text = _format_sources(section.search_results)

    # Build prompt
    prompt = f"""
Scrivi la sezione del documento con le seguenti specifiche:

**TITOLO SEZIONE:** {section.title}

**SCOPE:**
{section.scope}

**TARGET PAROLE:** {section.target_words} (±10%)

**STILE:** {style_profile}

**FONTI DISPONIBILI:**
{sources_text}

---

Genera il contenuto Markdown seguendo tutte le regole nel prompt di sistema.
Ricorda:
- Cita ogni fatto con [N]
- Rispetta il target parole
- Scrivi in Markdown pulito
- Usa le fonti in modo bilanciato
"""
    return prompt.strip()


def _format_sources(search_results) -> str:
    """Format search results as a numbered citation list.

    Returns:
        Formatted string like:
        [1] [WEB] Title - snippet... (url)
        [2] [RAG] RAG: content... (chunk://id)
    """
    if not search_results:
        return "(Nessuna fonte disponibile — genera contenuto basandoti su conoscenza generale)"

    lines = []
    for i, result in enumerate(search_results, start=1):
        source_type = result.source_type.upper()  # "WEB" or "RAG"
        title = result.title[:60]
        snippet = result.snippet[:150].replace("\n", " ")
        url = result.url

        # Add similarity for RAG sources
        extra = ""
        if result.source_type == "rag" and result.similarity:
            extra = f" [sim={result.similarity:.2f}]"

        lines.append(
            f"[{i}] [{source_type}] {title} - {snippet}... ({url}){extra}"
        )

    return "\n".join(lines)


async def _generate_content(
    state: ResearchState,
    system_prompt: str,
    user_prompt: str,
    section,
) -> tuple[str, float]:
    """Call LLM to generate section content.

    Returns:
        Tuple of (content_markdown, cost_usd).

    Raises:
        LLMError: If generation fails.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]

    # Get LLM client
    client = await get_llm_client(db=None)  # TODO: inject db session

    # Call LLM (writer_single → claude-opus-4-5)
    response = await client.chat(
        messages=messages,
        node_id="writer_single",
        temperature=0.7,  # Moderate creativity
        max_tokens=section.target_words * 2,  # Approx 2 tokens per word
        state=state,  # Budget tracking
    )

    # Clean up response (remove markdown fences if present)
    content = response.content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    return content, response.cost_usd


def _count_words(text: str) -> int:
    """Count words in text (simple whitespace split)."""
    return len(text.split())


def _validate_word_count(actual: int, target: int, section_title: str) -> None:
    """Validate word count against target.

    Logs a warning if off by more than WORD_COUNT_TOLERANCE.
    Raises ValueError if below MIN_WORD_COUNT.
    """
    if actual < MIN_WORD_COUNT:
        raise ValueError(
            f"Section '{section_title}' word count too low: {actual} < {MIN_WORD_COUNT}"
        )

    diff_pct = abs(actual - target) / target
    if diff_pct > WORD_COUNT_TOLERANCE:
        logger.warning(
            "Section '%s' word count off by %.1f%% (got %d, target %d)",
            section_title, diff_pct * 100, actual, target,
        )
    else:
        logger.info(
            "Section '%s' word count OK: %d words (target %d)",
            section_title, actual, target,
        )


async def _wait_for_approval(
    broker,
    doc_id: str,
    section_idx: int,
    content: str,
) -> str:
    """Wait for SECTION_APPROVED event from the frontend.

    The user may edit the content before approving. We return the
    (potentially edited) content.

    Args:
        broker:      SSEBroker instance.
        doc_id:      Run document ID.
        section_idx: Section index.
        content:     Draft content (default if user doesn't edit).

    Returns:
        Approved content string (may be user-edited).
    """
    if not broker:
        logger.warning("No broker available, auto-approving section %d", section_idx)
        return content

    logger.info("[%s] Waiting for section %d approval...", doc_id, section_idx)

    approved_content = await broker.wait_for_section_approval(
        doc_id=doc_id,
        section_idx=section_idx,
        default_content=content,
        timeout_s=600.0,
    )

    logger.info("[%s] Section %d approved (len=%d)", doc_id, section_idx, len(approved_content))
    return approved_content


# ---------------------------------------------------------------------------
# Fallback prompt
# ---------------------------------------------------------------------------

_FALLBACK_PROMPT = """
You are an expert research writer. Generate a well-structured section of a
research document based on the provided title, scope, and sources.

Rules:
1. Cite every fact using [N] format where N is the source number
2. Write in Markdown with proper headings (## only, no #)
3. Target the specified word count (±10%)
4. Use professional but accessible tone
5. Integrate information from multiple sources
6. Output ONLY the Markdown content, no extra text

Example citation: "Quantum computers use qubits [1][2]."
"""
