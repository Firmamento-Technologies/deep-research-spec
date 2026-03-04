"""Planner node — generates the document outline from the research topic.

The Planner is the first node in the research pipeline after the budget
estimator. It uses an LLM to generate a structured outline consisting of
4-12 sections, each with a title, scope, and target word count.

The outline is then presented to the user for approval (HITL). Once approved,
the pipeline proceeds to the Researcher node for each section.

Spec: §11 Planner node, §19 Budget tracking, §20 HITL
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.state import ResearchState

from src.models.state import Section
from src.llm.client import get_llm_client, LLMError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "../../..", "prompts", "planner_system.txt"
)

# Validation thresholds
MIN_SECTIONS = 4
MAX_SECTIONS = 12
WORD_COUNT_TOLERANCE = 0.15  # ±15% of target_words


# ---------------------------------------------------------------------------
# Planner Node
# ---------------------------------------------------------------------------

async def planner_node(state: ResearchState) -> dict:
    """Generate document outline and wait for user approval.

    Flow:
    1. Load planner system prompt
    2. Call LLM (node_id='planner') to generate outline JSON
    3. Parse and validate JSON structure
    4. Emit SSE: HUMAN_REQUIRED with outline payload
    5. Wait for OUTLINE_APPROVED event from broker
    6. Update state with approved outline

    Args:
        state: ResearchState with topic, target_words, quality_preset.

    Returns:
        Partial state update with outline, sections, total_sections, status.

    Raises:
        LLMError: If outline generation fails after retries.
        ValueError: If outline validation fails.
    """
    doc_id         = state["doc_id"]
    topic          = state["topic"]
    target_words   = state.get("target_words", 5000)
    quality_preset = state.get("quality_preset", "Balanced")
    broker         = state.get("broker")

    logger.info("[%s] Planner started: topic='%s', target=%d, preset=%s", 
                doc_id, topic, target_words, quality_preset)

    t0 = time.monotonic()

    # Emit NODE_STARTED
    if broker:
        await broker.emit(doc_id, "NODE_STARTED", {"node": "planner"})

    # --- 1. Load system prompt ---
    system_prompt = _load_prompt()

    # --- 2. Generate outline via LLM ---
    outline_json = await _generate_outline(
        state=state,
        topic=topic,
        target_words=target_words,
        quality_preset=quality_preset,
        system_prompt=system_prompt,
    )

    # --- 3. Parse and validate ---
    sections = _parse_and_validate(
        outline_json, target_words, quality_preset
    )

    logger.info(
        "[%s] Planner generated %d sections, total_words=%d",
        doc_id, len(sections), sum(s.target_words for s in sections),
    )

    # --- 4. Emit HUMAN_REQUIRED (outline approval) ---
    if broker:
        await broker.emit(doc_id, "HUMAN_REQUIRED", {
            "type": "outline_approval",
            "payload": {
                "sections": [s.to_dict() for s in sections]
            },
        })

    # --- 5. Wait for approval ---
    approved_sections = await _wait_for_approval(broker, doc_id, sections)

    # --- 6. Emit NODE_COMPLETED ---
    duration = time.monotonic() - t0
    if broker:
        await broker.emit(doc_id, "NODE_COMPLETED", {
            "node": "planner",
            "duration_s": round(duration, 2),
            "sections_count": len(approved_sections),
        })

    logger.info("[%s] Planner completed in %.2fs", doc_id, duration)

    # Return state updates
    return {
        "outline": approved_sections,
        "sections": approved_sections.copy(),  # Writer will fill content
        "total_sections": len(approved_sections),
        "status": "planning",
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_prompt() -> str:
    """Load planner system prompt from prompts/planner_system.txt."""
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning("Planner prompt file not found: %s (using fallback)", PROMPT_PATH)
        return _FALLBACK_PROMPT


async def _generate_outline(
    state: ResearchState,
    topic: str,
    target_words: int,
    quality_preset: str,
    system_prompt: str,
) -> str:
    """Call LLM to generate outline JSON.

    Returns:
        Raw JSON string from LLM response.

    Raises:
        LLMError: If LLM call fails.
    """
    # Build user prompt
    user_prompt = (
        f"Genera la struttura di un documento di ricerca per il seguente topic:\n\n"
        f"TOPIC: {topic}\n\n"
        f"PARAMETRI:\n"
        f"- Target parole totali: {target_words}\n"
        f"- Quality preset: {quality_preset}\n\n"
        f"Rispondi con il JSON come da istruzioni."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]

    # Get LLM client (loads from DB settings cache)
    from database.connection import get_db
    db = None  # For simplicity, use env-var fallback (TODO: inject db session)
    client = await get_llm_client(db)

    # Call LLM
    response = await client.chat(
        messages=messages,
        node_id="planner",
        temperature=0.3,  # Low temp for structured output
        max_tokens=4096,
        state=state,  # Budget tracking
    )

    # Extract JSON from response (may have markdown fences)
    content = response.content.strip()
    if content.startswith("```"):
        # Strip markdown code fences
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    return content


def _parse_and_validate(
    json_str: str,
    target_words: int,
    quality_preset: str,
) -> list[Section]:
    """Parse outline JSON and validate structure.

    Args:
        json_str:       Raw JSON string from LLM.
        target_words:   Expected total word count.
        quality_preset: "Economy" | "Balanced" | "Premium".

    Returns:
        List of Section objects.

    Raises:
        ValueError: If JSON is invalid or fails validation.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from Planner: {exc}\n{json_str[:200]}") from exc

    if "sections" not in data or not isinstance(data["sections"], list):
        raise ValueError(f"Missing or invalid 'sections' array in outline: {data}")

    raw_sections = data["sections"]

    # Validate section count
    if not (MIN_SECTIONS <= len(raw_sections) <= MAX_SECTIONS):
        raise ValueError(
            f"Outline has {len(raw_sections)} sections (expected {MIN_SECTIONS}-{MAX_SECTIONS})"
        )

    # Parse sections
    sections = []
    for i, s in enumerate(raw_sections):
        if not isinstance(s, dict):
            raise ValueError(f"Section {i} is not a dict: {s}")
        if "title" not in s or "scope" not in s or "target_words" not in s:
            raise ValueError(f"Section {i} missing required keys: {s}")

        sections.append(
            Section(
                title=s["title"],
                scope=s["scope"],
                target_words=int(s["target_words"]),
            )
        )

    # Validate total word count
    total = sum(s.target_words for s in sections)
    diff_pct = abs(total - target_words) / target_words
    if diff_pct > WORD_COUNT_TOLERANCE:
        logger.warning(
            "Outline word count off by %.1f%% (got %d, expected %d)",
            diff_pct * 100, total, target_words,
        )
        # Auto-adjust: scale all sections proportionally
        scale = target_words / total
        for s in sections:
            s.target_words = int(s.target_words * scale)
        logger.info("Auto-adjusted section word counts to match target=%d", target_words)

    return sections


async def _wait_for_approval(
    broker,
    doc_id: str,
    sections: list[Section],
) -> list[Section]:
    """Wait for OUTLINE_APPROVED event from the frontend.

    The user may edit the outline before approving. We listen for the
    approval event and return the (potentially modified) section list.

    Args:
        broker:   SSEBroker instance.
        doc_id:   Run document ID.
        sections: Planner-generated sections (default if user doesn't edit).

    Returns:
        List of approved Section objects (may be user-edited).
    """
    if not broker:
        logger.warning("No broker available, auto-approving outline")
        return sections

    # Subscribe to approval event
    # (In a real LangGraph interrupt, we'd use graph checkpointer + user input)
    # For now, simulate with a simple wait loop polling Redis pub/sub

    logger.info("[%s] Waiting for outline approval...", doc_id)

    # TODO: Replace with proper LangGraph interrupt + user input handling
    # For MVP, we auto-approve after 1 second (stub)
    await asyncio.sleep(1.0)

    logger.info("[%s] Outline auto-approved (HITL stub)", doc_id)
    return sections


# ---------------------------------------------------------------------------
# Fallback prompt (if file not found)
# ---------------------------------------------------------------------------

_FALLBACK_PROMPT = """
You are a research document structure expert. Generate a detailed outline
for a research document on the given topic.

Output a JSON object with a "sections" array. Each section must have:
- "title": concise section title (max 5 words)
- "scope": detailed description of what to cover (1-2 sentences)
- "target_words": target word count for this section

Rules:
1. 4-12 sections total
2. Total word count should match the requested target (±15%)
3. Logical narrative flow
4. Output ONLY the JSON, no extra text

Example:
{
  "sections": [
    {"title": "Introduction", "scope": "Context and objectives.", "target_words": 800},
    {"title": "Background", "scope": "State of the art.", "target_words": 1500}
  ]
}
"""
