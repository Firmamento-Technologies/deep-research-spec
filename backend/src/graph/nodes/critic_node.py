"""Critic node — evaluates section quality and decides approve/rewrite.

The Critic uses an LLM to perform a structured quality assessment of a
section's content against 7 evaluation criteria. Based on the score, it
either approves the section (allowing pipeline to continue) or requests
a rewrite (sending feedback back to the Writer).

Key responsibilities:
- Evaluate content against rubric (citations, coherence, depth, etc.)
- Parse structured JSON feedback from LLM
- Make approve/rewrite decision based on score threshold
- Track iteration count and enforce max rewrites limit
- Emit SSE events with detailed feedback
- Update section metadata (feedback, final_score, iterations)

The Critic implements the quality control feedback loop that ensures
all sections meet the minimum quality bar before proceeding.

Spec: §14 Critic node, §19 Budget tracking, §21 Quality presets
"""

from __future__ import annotations

import json
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
    os.path.dirname(__file__), "../../..", "prompts", "critic_system.txt"
)

# Approval thresholds by quality preset
APPROVAL_THRESHOLDS = {
    "Economy":  6.0,  # Lower bar, faster iteration
    "Balanced": 7.0,  # Standard quality
    "Premium":  8.0,  # High quality requirement
}

# Max rewrite iterations
MAX_ITERATIONS = {
    "Economy":  1,  # 1 rewrite max (2 total attempts)
    "Balanced": 2,  # 2 rewrites max (3 total attempts)
    "Premium":  3,  # 3 rewrites max (4 total attempts)
}


# ---------------------------------------------------------------------------
# Critic Node
# ---------------------------------------------------------------------------

async def critic_node(state: ResearchState) -> dict:
    """Evaluate section quality and decide approve/rewrite.

    Flow:
    1. Get current section from state
    2. Check iteration count (enforce max rewrites)
    3. Load critic system prompt
    4. Build evaluation prompt with content + rubric
    5. Call LLM (node_id='critic') for structured feedback JSON
    6. Parse feedback and extract score
    7. Make decision: score >= threshold → APPROVE, else → REWRITE
    8. If REWRITE: emit REWRITE_REQUIRED, increment iterations, return feedback
    9. If APPROVE: update final_score, mark section complete
    10. Emit SSE events with detailed feedback

    Args:
        state: ResearchState with current_section index.

    Returns:
        Partial state update with section feedback and status.
        If rewrite required, returns special flag for graph router.

    Raises:
        ValueError: If current_section is out of bounds.
        LLMError: If evaluation fails.
    """
    doc_id         = state["doc_id"]
    sections       = state.get("sections", [])
    current_idx    = state.get("current_section", 0)
    quality_preset = state.get("quality_preset", "Balanced")
    broker         = state.get("broker")

    if current_idx >= len(sections):
        raise ValueError(
            f"current_section={current_idx} out of bounds (sections={len(sections)})"
        )

    section = sections[current_idx]

    logger.info(
        "[%s] Critic started for section %d: '%s' (iteration=%d)",
        doc_id, current_idx, section.title, section.iterations,
    )

    t0 = time.monotonic()

    # Emit NODE_STARTED
    if broker:
        await broker.emit(doc_id, "NODE_STARTED", {
            "node": "critic",
            "section_idx": current_idx,
            "section_title": section.title,
            "iteration": section.iterations,
        })

    # --- 1. Check max iterations ---
    max_iter = MAX_ITERATIONS.get(quality_preset, 2)
    if section.iterations >= max_iter:
        logger.warning(
            "[%s] Section %d reached max iterations (%d), force-approving",
            doc_id, current_idx, max_iter,
        )
        # Force approve to avoid infinite loop
        section.status = "complete"
        section.final_score = section.final_score or 6.0  # Fallback score
        if broker:
            await broker.emit(doc_id, "CRITIC_FEEDBACK", {
                "section_idx": current_idx,
                "verdict": "FORCE_APPROVE",
                "reason": "max_iterations_reached",
            })
        return {"sections": sections, "status": "writing"}

    # --- 2. Load system prompt ---
    system_prompt = _load_prompt()

    # --- 3. Build evaluation prompt ---
    user_prompt = _build_evaluation_prompt(section, quality_preset)

    # --- 4. Get feedback from LLM ---
    feedback_json, llm_cost = await _evaluate_section(
        state=state,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    # --- 5. Parse feedback ---
    feedback = _parse_feedback(feedback_json)

    score = feedback["score"]
    verdict = feedback["verdict"]
    issues = feedback["issues"]
    suggestions = feedback["suggestions"]
    strengths = feedback.get("strengths", [])

    logger.info(
        "[%s] Critic evaluation: score=%.1f, verdict=%s",
        doc_id, score, verdict,
    )

    # Update section cost
    section.cost_usd += llm_cost

    # --- 6. Emit CRITIC_FEEDBACK ---
    if broker:
        await broker.emit(doc_id, "CRITIC_FEEDBACK", {
            "section_idx": current_idx,
            "score": score,
            "verdict": verdict,
            "issues": issues,
            "suggestions": suggestions,
            "strengths": strengths,
        })

    # --- 7. Make decision ---
    threshold = APPROVAL_THRESHOLDS.get(quality_preset, 7.0)

    if score >= threshold or verdict == "APPROVE":
        # APPROVE: Section is good enough
        section.feedback = feedback
        section.final_score = score
        section.status = "complete"

        logger.info(
            "[%s] Section %d APPROVED (score=%.1f >= threshold=%.1f)",
            doc_id, current_idx, score, threshold,
        )

        # Emit NODE_COMPLETED
        duration = time.monotonic() - t0
        if broker:
            await broker.emit(doc_id, "NODE_COMPLETED", {
                "node": "critic",
                "section_idx": current_idx,
                "duration_s": round(duration, 2),
                "verdict": "APPROVE",
                "score": score,
            })

        return {"sections": sections, "status": "writing"}

    else:
        # REWRITE: Section needs improvement
        section.feedback = feedback
        section.iterations += 1

        logger.info(
            "[%s] Section %d REWRITE REQUIRED (score=%.1f < threshold=%.1f, iteration=%d)",
            doc_id, current_idx, score, threshold, section.iterations,
        )

        # Emit REWRITE_REQUIRED
        if broker:
            await broker.emit(doc_id, "REWRITE_REQUIRED", {
                "section_idx": current_idx,
                "score": score,
                "issues": issues,
                "suggestions": suggestions,
                "iteration": section.iterations,
            })

        # Emit NODE_COMPLETED (with rewrite flag)
        duration = time.monotonic() - t0
        if broker:
            await broker.emit(doc_id, "NODE_COMPLETED", {
                "node": "critic",
                "section_idx": current_idx,
                "duration_s": round(duration, 2),
                "verdict": "REWRITE",
                "score": score,
            })

        # Return special flag for graph router to loop back to Writer
        return {
            "sections": sections,
            "status": "writing",
            "rewrite_required": True,  # ← Tells router to go back to Writer
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_prompt() -> str:
    """Load critic system prompt from prompts/critic_system.txt."""
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning("Critic prompt file not found: %s (using fallback)", PROMPT_PATH)
        return _FALLBACK_PROMPT


def _build_evaluation_prompt(section, quality_preset: str) -> str:
    """Build the evaluation prompt with section content and metadata.

    Returns:
        Formatted prompt string.
    """
    threshold = APPROVAL_THRESHOLDS.get(quality_preset, 7.0)

    prompt = f"""
Valuta la seguente sezione di documento di ricerca:

**TITOLO SEZIONE:** {section.title}

**SCOPE ORIGINALE:**
{section.scope}

**TARGET PAROLE:** {section.target_words}
**PAROLE EFFETTIVE:** {section.word_count}

**CONTENUTO DA VALUTARE:**
---
{section.content}
---

**PARAMETRI VALUTAZIONE:**
- Quality preset: {quality_preset}
- Soglia approvazione: {threshold}/10
- Iterazione corrente: {section.iterations}

**FONTI DISPONIBILI (per verifica citazioni):**
{_format_sources_for_review(section.search_results)}

---

Fornisci la valutazione strutturata in formato JSON come specificato nelle istruzioni.
"""
    return prompt.strip()


def _format_sources_for_review(search_results) -> str:
    """Format sources list for citation verification."""
    if not search_results:
        return "(Nessuna fonte)"

    lines = []
    for i, result in enumerate(search_results, start=1):
        lines.append(f"[{i}] {result.title[:60]} - {result.source_type}")

    return "\n".join(lines)


async def _evaluate_section(
    state: ResearchState,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, float]:
    """Call LLM to evaluate section and return structured feedback.

    Returns:
        Tuple of (feedback_json_str, cost_usd).

    Raises:
        LLMError: If evaluation fails.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]

    # Get LLM client
    client = await get_llm_client(db=None)  # TODO: inject db session

    # Call LLM (critic → o1-mini)
    response = await client.chat(
        messages=messages,
        node_id="critic",
        temperature=0.3,  # Low temp for consistent evaluation
        max_tokens=2048,
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


def _parse_feedback(json_str: str) -> dict:
    """Parse feedback JSON from LLM.

    Returns:
        Feedback dict with keys: score, verdict, issues, suggestions, strengths.

    Raises:
        ValueError: If JSON is invalid or missing required fields.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from Critic: {exc}\n{json_str[:200]}") from exc

    # Validate required fields
    required = ["score", "verdict", "issues", "suggestions"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValueError(f"Critic feedback missing fields: {missing}")

    # Validate score range
    score = data["score"]
    if not isinstance(score, (int, float)) or not (0 <= score <= 10):
        raise ValueError(f"Invalid score: {score} (must be 0-10)")

    # Validate verdict
    verdict = data["verdict"]
    if verdict not in ["APPROVE", "REWRITE"]:
        logger.warning(f"Unexpected verdict: {verdict}, defaulting to REWRITE")
        data["verdict"] = "REWRITE"

    return data


# ---------------------------------------------------------------------------
# Fallback prompt
# ---------------------------------------------------------------------------

_FALLBACK_PROMPT = """
You are a research document quality evaluator. Assess the provided section
against these 7 criteria (each 0-10): citations, coherence, depth, accuracy,
structure, completeness, originality.

Output a JSON object with:
- score: average of all criteria (0-10)
- scores_breakdown: dict with each criterion score
- issues: list of specific problems
- suggestions: list of actionable improvements
- strengths: list of positive aspects
- verdict: "APPROVE" if score >= 7, else "REWRITE"

Be specific and constructive. Output ONLY the JSON, no extra text.
"""
