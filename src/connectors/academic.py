"""AcademicConnector — CrossRef, Semantic Scholar, ArXiv — §17.2."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.connectors.base import SourceConnector, SourceType

logger = logging.getLogger(__name__)

# CrossRef polite pool: 50 req/s with CROSSREF_MAILTO header
_DEFAULT_CROSSREF_MAILTO = "drs@example.com"


class AcademicConnector(SourceConnector):
    """Search academic databases and return verified peer-reviewed sources. §17.2.

    Cascade: CrossRef → Semantic Scholar → ArXiv.
    """

    connector_id: str = "academic"
    source_type: SourceType = "academic"
    reliability_base: float = 0.80
    enabled: bool = True

    def __init__(
        self,
        crossref_mailto: str = _DEFAULT_CROSSREF_MAILTO,
        semantic_scholar_api_key: str | None = None,
        arxiv_enabled: bool = True,
        max_per_provider: int = 10,
    ):
        self.crossref_mailto = crossref_mailto
        self.semantic_scholar_api_key = semantic_scholar_api_key
        self.arxiv_enabled = arxiv_enabled
        self.max_per_provider = max_per_provider

    async def search(self, query: str, max_results: int) -> list[dict]:
        """Search CrossRef → Semantic Scholar → ArXiv. §17.2.

        Returns list of source dicts with source_type="academic".
        """
        results: list[dict] = []
        per_provider = min(self.max_per_provider, max_results)

        # ── CrossRef ─────────────────────────────────────────────────────
        try:
            cr_results = await self._search_crossref(query, per_provider)
            results.extend(cr_results)
        except Exception as e:
            logger.warning("CrossRef search failed: %s — falling back to Semantic Scholar", e)

        # ── Semantic Scholar ─────────────────────────────────────────────
        if len(results) < max_results:
            try:
                ss_results = await self._search_semantic_scholar(
                    query, min(per_provider, max_results - len(results))
                )
                results.extend(ss_results)
            except Exception as e:
                logger.warning("Semantic Scholar search failed: %s", e)

        # ── ArXiv ────────────────────────────────────────────────────────
        if self.arxiv_enabled and len(results) < max_results:
            try:
                ax_results = await self._search_arxiv(
                    query, min(per_provider, max_results - len(results))
                )
                results.extend(ax_results)
            except Exception as e:
                logger.warning("ArXiv search failed: %s", e)

        return results[:max_results]

    async def health_check(self) -> bool:
        """Check CrossRef API availability."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(
                    "https://api.crossref.org/works?rows=1",
                    headers={"User-Agent": f"DRS/1.0 (mailto:{self.crossref_mailto})"},
                )
                return r.status_code == 200
        except Exception:
            return False

    # ── Provider implementations ─────────────────────────────────────────

    async def _search_crossref(self, query: str, limit: int) -> list[dict]:
        """Search CrossRef Works API. Respects polite pool via mailto header."""
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.crossref.org/works",
                params={"query": query, "rows": limit, "sort": "relevance"},
                headers={"User-Agent": f"DRS/1.0 (mailto:{self.crossref_mailto})"},
            )
            r.raise_for_status()
            items = r.json().get("message", {}).get("items", [])

        sources = []
        for item in items:
            doi = item.get("DOI")
            title = (item.get("title") or [""])[0]
            authors = [
                f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
                for a in item.get("author", [])
            ]
            year = None
            dp = item.get("published-print") or item.get("published-online")
            if dp and dp.get("date-parts"):
                year = dp["date-parts"][0][0] if dp["date-parts"][0] else None

            sources.append({
                "source_id": self.make_source_id(doi or title),
                "url": f"https://doi.org/{doi}" if doi else None,
                "doi": doi,
                "isbn": None,
                "title": title,
                "authors": authors,
                "publisher": item.get("publisher"),
                "year": year,
                "abstract": item.get("abstract"),
                "source_type": "academic",
                "reliability_score": 0.85 if doi else 0.80,
                "http_verified": bool(doi),
                "language": item.get("language", "en"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
        return sources

    async def _search_semantic_scholar(self, query: str, limit: int) -> list[dict]:
        """Search Semantic Scholar Graph API."""
        import httpx

        headers = {}
        if self.semantic_scholar_api_key:
            headers["x-api-key"] = self.semantic_scholar_api_key

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": query,
                    "limit": limit,
                    "fields": "title,authors,year,abstract,externalIds,url",
                },
                headers=headers,
            )
            r.raise_for_status()
            papers = r.json().get("data", [])

        sources = []
        for p in papers:
            doi = (p.get("externalIds") or {}).get("DOI")
            sources.append({
                "source_id": self.make_source_id(doi or p.get("paperId", p.get("title", ""))),
                "url": p.get("url"),
                "doi": doi,
                "isbn": None,
                "title": p.get("title", ""),
                "authors": [a.get("name", "") for a in p.get("authors", [])],
                "publisher": None,
                "year": p.get("year"),
                "abstract": p.get("abstract"),
                "source_type": "academic",
                "reliability_score": 0.85 if doi else 0.80,
                "http_verified": False,
                "language": "en",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
        return sources

    async def _search_arxiv(self, query: str, limit: int) -> list[dict]:
        """Search ArXiv API (Atom feed)."""
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "http://export.arxiv.org/api/query",
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": limit,
                    "sortBy": "relevance",
                },
            )
            r.raise_for_status()

        # Simple XML parsing for ArXiv Atom feed
        import xml.etree.ElementTree as ET
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(r.text)
        entries = root.findall("atom:entry", ns)

        sources = []
        for entry in entries:
            title = (entry.findtext("atom:title", "", ns) or "").strip()
            abstract = (entry.findtext("atom:summary", "", ns) or "").strip()
            arxiv_id = (entry.findtext("atom:id", "", ns) or "").strip()
            published = entry.findtext("atom:published", "", ns) or ""
            year = int(published[:4]) if len(published) >= 4 else None
            authors = [
                a.findtext("atom:name", "", ns)
                for a in entry.findall("atom:author", ns)
            ]

            sources.append({
                "source_id": self.make_source_id(arxiv_id or title),
                "url": arxiv_id,
                "doi": None,
                "isbn": None,
                "title": title,
                "authors": authors,
                "publisher": "arXiv",
                "year": year,
                "abstract": abstract,
                "source_type": "academic",
                "reliability_score": 0.82,
                "http_verified": False,
                "language": "en",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
        return sources
