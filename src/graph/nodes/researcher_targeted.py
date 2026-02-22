"""ResearcherTargeted node — §5.23. Targeted re-research for specific gaps."""
from __future__ import annotations

import logging

from src.connectors.base import SourceConnector

logger = logging.getLogger(__name__)


class ResearcherTargetedNode:
    """§5.23 — Execute targeted re-research for gaps from PostDraftAnalyzer
    or missing evidence flagged by JuryFactual.

    Sets targeted_research_active=True so downstream agents can distinguish
    this path from initial research.
    """

    def __init__(self, connectors: list[SourceConnector] | None = None):
        self.connectors = connectors or []

    async def run(self, state: dict) -> dict:
        """Execute targeted research. Returns partial state update."""
        gaps = state.get("post_draft_gaps", [])
        existing_sources = state.get("current_sources", [])
        existing_urls = {s.get("url") for s in existing_sources if s.get("url")}
        existing_dois = {s.get("doi") for s in existing_sources if s.get("doi")}

        section_idx = state.get("current_section_idx", 0)
        outline = state.get("outline", [])
        section = outline[section_idx] if section_idx < len(outline) else {}
        scope = section.get("scope", "")

        # Build queries from gaps
        queries: list[str] = []
        for gap in gaps:
            suggested = gap.get("suggested_queries", [])
            if suggested:
                queries.extend(suggested[:2])  # max 2 per gap
            else:
                queries.append(gap.get("description", scope))
        queries = queries[:6]  # max 6 total queries

        logger.info("ResearcherTargeted: section_idx=%d, queries=%d", section_idx, len(queries))

        # Search across connectors
        additional: list[dict] = []
        for query in queries:
            for connector in self.connectors:
                if not getattr(connector, "enabled", True):
                    continue
                try:
                    results = await connector.search(query, max_results=5)
                    for r in results:
                        # Dedup vs existing (§5.23 CONSTRAINTS)
                        r_url = r.get("url")
                        r_doi = r.get("doi")
                        if r_url and r_url in existing_urls:
                            continue
                        if r_doi and r_doi in existing_dois:
                            continue
                        additional.append(r)
                        existing_urls.add(r_url)
                        if r_doi:
                            existing_dois.add(r_doi)
                except Exception as e:
                    logger.warning("Targeted connector %s failed: %s",
                                 getattr(connector, "connector_id", "?"), e)

        # Merge additional into current_sources
        merged = list(existing_sources) + additional

        logger.info("ResearcherTargeted: added %d new sources (total %d)",
                    len(additional), len(merged))

        return {
            "current_sources": merged,
            "targeted_research_active": True,  # MUST set (§5.23)
        }


# ── Node function for graph registration ─────────────────────────────────────

_default_node = ResearcherTargetedNode()


async def researcher_targeted_node(state: dict) -> dict:
    """Graph-compatible node function."""
    return await _default_node.run(state)
