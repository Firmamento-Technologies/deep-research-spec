"""InstitutionalConnector — Tavily with domain filter — §17.3."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.connectors.base import SourceConnector, SourceType

logger = logging.getLogger(__name__)

INSTITUTIONAL_DOMAIN_ALLOWLIST: list[str] = [
    ".gov", ".eu", ".un.org", ".who.int", ".oecd.org",
    ".worldbank.org", ".imf.org", ".nato.int",
]


class InstitutionalConnector(SourceConnector):
    """Retrieve sources from institutional/government domains. §17.3.

    Uses Tavily API with domain filtering against allowlist.
    """

    connector_id: str = "institutional"
    source_type: SourceType = "institutional"
    reliability_base: float = 0.85
    enabled: bool = True

    def __init__(
        self,
        tavily_api_key: str | None = None,
        extra_domains: list[str] | None = None,
    ):
        self.tavily_api_key = tavily_api_key
        self.domain_allowlist = INSTITUTIONAL_DOMAIN_ALLOWLIST + (extra_domains or [])

    def _is_allowed_domain(self, url: str) -> bool:
        """Check if URL matches any domain in the allowlist."""
        if not url:
            return False
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.domain_allowlist)

    async def search(self, query: str, max_results: int) -> list[dict]:
        """Search Tavily filtered to institutional domains. §17.3."""
        if not self.tavily_api_key:
            logger.warning("InstitutionalConnector: no Tavily API key configured")
            return []

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "max_results": max_results * 3,  # overfetch for filtering
                        "search_depth": "advanced",
                        "include_domains": [d.lstrip(".") for d in self.domain_allowlist],
                    },
                )
                r.raise_for_status()
                results = r.json().get("results", [])
        except Exception as e:
            logger.warning("Tavily institutional search failed: %s", e)
            return []

        sources = []
        for item in results:
            url = item.get("url", "")
            if not self._is_allowed_domain(url):
                continue
            sources.append({
                "source_id": self.make_source_id(url),
                "url": url,
                "doi": None,
                "isbn": None,
                "title": item.get("title", ""),
                "authors": [],
                "publisher": item.get("url", "").split("/")[2] if "/" in item.get("url", "") else None,
                "year": None,
                "abstract": item.get("content", "")[:500],
                "source_type": "institutional",
                "reliability_score": 0.88,
                "http_verified": True,
                "language": "en",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
            if len(sources) >= max_results:
                break

        return sources

    async def health_check(self) -> bool:
        """Check Tavily API availability."""
        if not self.tavily_api_key:
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": self.tavily_api_key, "query": "test", "max_results": 1},
                )
                return r.status_code == 200
        except Exception:
            return False
