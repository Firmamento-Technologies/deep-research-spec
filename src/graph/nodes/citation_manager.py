"""CitationManager node — §5.3, §18.1. Deterministic citation formatting."""
from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

CitationStyle = Literal["APA", "Harvard", "Chicago", "Vancouver"]


class CitationManagerNode:
    """§5.3 — Build citation map from source metadata (deterministic, no LLM)."""

    def __init__(self, default_style: CitationStyle = "APA"):
        self.default_style = default_style

    async def run(self, state: dict) -> dict:
        """Build citation_map and bibliography from current_sources."""
        sources = state.get("current_sources", [])
        style: CitationStyle = state.get("config", {}).get(
            "citation_style", self.default_style
        )

        citation_map: dict[str, str] = {}
        bibliography: list[str] = []

        for src in sources:
            sid = src.get("source_id", "")
            try:
                inline = self._format_inline(src, style)
                bib_entry = self._format_bibliography(src, style)
                citation_map[sid] = inline
                bibliography.append(bib_entry)
            except Exception as e:
                logger.warning("Citation format error for %s: %s", sid, e)
                citation_map[sid] = f"[INCOMPLETE_CITATION_{sid}]"
                bibliography.append(f"[INCOMPLETE_CITATION_{sid}]")

        return {
            "citation_map": citation_map,
            "bibliography": bibliography,
        }

    def _format_inline(self, src: dict, style: CitationStyle) -> str:
        """Format inline citation marker."""
        authors = src.get("authors", [])
        year = src.get("year")
        first_author = authors[0].split(",")[0] if authors else "Unknown"

        if style == "APA":
            return f"({first_author}, {year or 'n.d.'})"
        elif style == "Harvard":
            return f"({first_author}, {year or 'n.d.'})"
        elif style == "Chicago":
            return f"{first_author} ({year or 'n.d.'})"
        elif style == "Vancouver":
            # Vancouver uses numbered refs — position-based
            return f"[{src.get('source_id', '?')[:4]}]"
        return f"({first_author}, {year or 'n.d.'})"

    def _format_bibliography(self, src: dict, style: CitationStyle) -> str:
        """Format full bibliography entry. §18.1."""
        authors = src.get("authors", [])
        title = src.get("title", "Untitled")
        year = src.get("year")
        publisher = src.get("publisher", "")
        doi = src.get("doi")
        url = src.get("url")
        isbn = src.get("isbn")

        author_str = ", ".join(authors) if authors else "Unknown"

        if style == "APA":
            entry = f"{author_str} ({year or 'n.d.'}). *{title}*."
            if publisher:
                entry += f" {publisher}."
            if doi:
                entry += f" https://doi.org/{doi}"
            elif url:
                entry += f" {url}"
            elif isbn:
                entry += f" ISBN: {isbn}"
            return entry

        elif style == "Harvard":
            entry = f"{author_str} ({year or 'n.d.'}). *{title}*."
            if publisher:
                entry += f" {publisher}."
            if doi:
                entry += f" DOI: {doi}"
            elif url:
                entry += f" Available at: {url}"
            elif isbn:
                entry += f" ISBN: {isbn}"
            return entry

        elif style == "Chicago":
            entry = f"{author_str}. *{title}*."
            if publisher:
                entry += f" {publisher},"
            if year:
                entry += f" {year}."
            if doi:
                entry += f" https://doi.org/{doi}"
            elif isbn:
                entry += f" ISBN: {isbn}"
            return entry

        elif style == "Vancouver":
            # Abbreviated author format
            entry = f"{author_str}. {title}."
            if publisher:
                entry += f" {publisher}."
            if year:
                entry += f" {year}."
            if doi:
                entry += f" DOI: {doi}"
            return entry

        return f"{author_str}. {title}. {year or 'n.d.'}."


# ── Node function for graph registration ─────────────────────────────────────

_default_node = CitationManagerNode()


async def citation_manager_node(state: dict) -> dict:
    """Graph-compatible node function."""
    return await _default_node.run(state)
