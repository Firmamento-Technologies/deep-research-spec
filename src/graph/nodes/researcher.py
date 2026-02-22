"""Researcher node — §5.2. Retrieve and rank sources for a section."""
from __future__ import annotations

import logging
from typing import Any

from src.connectors.base import SourceConnector, SourceRanker, DiversityAnalyzer

logger = logging.getLogger(__name__)

# Default max_sources (C06: from config, not hardcoded; 15 is fallback)
_DEFAULT_MAX_SOURCES = 15


class ResearcherNode:
    """§5.2 — Retrieve and rank sources for a single section.

    Connector cascade: academic → institutional → web → social (opt-in).
    Uses SourceRanker (§17.9) for scoring/dedup and DiversityAnalyzer (§17.8).
    """

    def __init__(
        self,
        connectors: list[SourceConnector] | None = None,
        ranker: SourceRanker | None = None,
        diversity_analyzer: DiversityAnalyzer | None = None,
    ):
        self.connectors = connectors or []
        self.ranker = ranker or SourceRanker()
        self.diversity = diversity_analyzer or DiversityAnalyzer()

    async def run(self, state: dict) -> dict:
        """Execute researcher node. Returns partial state update."""
        section_idx = state.get("current_section_idx", 0)
        outline = state.get("outline", [])
        section = outline[section_idx] if section_idx < len(outline) else {}
        scope = section.get("scope", state.get("config", {}).get("topic", ""))
        max_sources = state.get("config", {}).get(
            "sources", {}
        ).get("max_sources_per_section", _DEFAULT_MAX_SOURCES)

        logger.info("Researcher: section_idx=%d, scope='%s', max_sources=%d",
                     section_idx, scope[:60], max_sources)

        # Collect from all enabled connectors
        all_sources: list[dict] = []
        for connector in self.connectors:
            if not getattr(connector, "enabled", True):
                continue
            try:
                results = await connector.search(scope, max_sources)
                all_sources.extend(results)
                logger.info("Connector %s returned %d sources",
                           getattr(connector, "connector_id", "?"), len(results))
            except Exception as e:
                logger.warning("Connector %s failed: %s",
                             getattr(connector, "connector_id", "?"), e)

        # Deduplicate by URL+DOI before ranking (§5.2 CONSTRAINTS)
        deduped = self._dedup_by_url_doi(all_sources)

        # Filter out reliability < 0.20 (§5.2 CONSTRAINTS)
        deduped = [s for s in deduped if s.get("reliability_score", 0) >= 0.20]

        # Rank and truncate
        ranked = self.ranker.rank(deduped, scope)

        # Diversity analysis
        source_dicts = [r.model_dump() for r in ranked]
        diversity_report = self.diversity.analyze(source_dicts, scope)

        if diversity_report.diversification_required:
            logger.info("Diversity: %s — hint: %s",
                       diversity_report.violations, diversity_report.diversification_query_hint)

        return {
            "current_sources": source_dicts,
            "diversity_report": diversity_report.model_dump(),
        }

    @staticmethod
    def _dedup_by_url_doi(sources: list[dict]) -> list[dict]:
        """Deduplicate by URL+DOI before ranking. §5.2."""
        seen: set[str] = set()
        unique: list[dict] = []
        for s in sources:
            key = s.get("url") or s.get("doi") or s.get("title", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(s)
        return unique


# ── Node function for graph registration ─────────────────────────────────────

# Default instance (connectors injected at runtime)
_default_node = ResearcherNode()


async def researcher_node(state: dict) -> dict:
    """Graph-compatible node function."""
    return await _default_node.run(state)
