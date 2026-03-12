"""SourceSanitizer node — §5.5, §22.4. 3-stage injection guard."""
from __future__ import annotations

import logging

from src.security.injection_guard import sanitize_source, SanitizeResult

logger = logging.getLogger(__name__)


class SourceSanitizerNode:
    """§5.5 — Sanitize source content through 3-stage injection guard.

    Stage 1: Regex pattern scan (pre-LLM)
    Stage 2: XML structural isolation
    Stage 3: Output monitoring (applied by downstream nodes)
    """

    async def run(self, state: dict) -> dict:
        """Sanitize all current_sources. Returns partial state update."""
        sources = state.get("current_sources", [])
        sanitized_sources: list[dict] = []
        injection_attempts: list[dict] = []

        for src in sources:
            sid = src.get("source_id", "")
            raw_content = src.get("abstract") or src.get("full_text_snippet") or ""

            if not raw_content:
                # No content to sanitize — pass through
                sanitized_sources.append(src)
                continue

            try:
                sanitized_xml, result = sanitize_source(raw_content, sid)

                # Update source with sanitized content
                src_copy = dict(src)
                src_copy["sanitized_xml"] = sanitized_xml
                src_copy["injection_detected"] = result.injection_detected

                if result.injection_attempts:
                    for attempt in result.injection_attempts:
                        injection_attempts.append(attempt.model_dump())
                    logger.warning(
                        "SECURITY_EVENT: injection detected in source %s", sid
                    )

                sanitized_sources.append(src_copy)

            except Exception as e:
                logger.error("Stage 1 regex error for source %s: %s — skipping", sid, e)
                # Skip source on regex error (§5.5 ERROR_HANDLING)
                continue

        return {
            "current_sources": sanitized_sources,
            "injection_attempts": injection_attempts,
        }


# ── Node function for graph registration ─────────────────────────────────────

_default_node = SourceSanitizerNode()


async def source_sanitizer_node(state: dict) -> dict:
    """Graph-compatible node function."""
    return await _default_node.run(state)
