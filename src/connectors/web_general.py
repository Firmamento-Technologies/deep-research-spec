"""WebGeneralConnector — Tavily primary, Brave fallback — §17.4."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.connectors.base import SourceConnector, SourceType

logger = logging.getLogger(__name__)

# Reliability heuristics — §17.4
_HTTPS_BONUS = 0.10
_NEWS_DOMAIN_BONUS = 0.05
_WIKI_PENALTY = -0.05
_NO_AUTHOR_PENALTY = -0.15
_MAX_WEB_RELIABILITY = 0.70
_BASE_WEB_RELIABILITY = 0.50


class WebGeneralConnector(SourceConnector):
    """Retrieve general web sources. Tavily → Brave fallback. §17.4."""

    connector_id: str = "web_general"
    source_type: SourceType = "web"
    reliability_base: float = 0.50
    enabled: bool = True

    def __init__(
        self,
        tavily_api_key: str | None = None,
        brave_api_key: str | None = None,
    ):
        self.tavily_api_key = tavily_api_key
        self.brave_api_key = brave_api_key

    def _score_reliability(self, url: str, has_author: bool) -> float:
        """Heuristic reliability scoring for web sources. §17.4."""
        score = _BASE_WEB_RELIABILITY
        if url.startswith("https://"):
            score += _HTTPS_BONUS
        if any(d in url.lower() for d in ["reuters.", "bbc.", "nytimes.", "apnews."]):
            score += _NEWS_DOMAIN_BONUS
        if "wikipedia." in url.lower():
            score += _WIKI_PENALTY
        if not has_author:
            score += _NO_AUTHOR_PENALTY
        return min(max(score, 0.0), _MAX_WEB_RELIABILITY)

    async def search(self, query: str, max_results: int) -> list[dict]:
        """Search Tavily, fall back to Brave if unavailable. §17.4."""
        results = await self._search_tavily(query, max_results)
        if not results:
            results = await self._search_brave(query, max_results)
        return results

    async def _search_tavily(self, query: str, max_results: int) -> list[dict]:
        if not self.tavily_api_key:
            return []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                    },
                )
                r.raise_for_status()
                items = r.json().get("results", [])
        except Exception as e:
            logger.warning("Tavily web search failed: %s", e)
            return []
        return [self._to_source(item) for item in items[:max_results]]

    async def _search_brave(self, query: str, max_results: int) -> list[dict]:
        if not self.brave_api_key:
            return []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": max_results},
                    headers={"X-Subscription-Token": self.brave_api_key, "Accept": "application/json"},
                )
                r.raise_for_status()
                items = r.json().get("web", {}).get("results", [])
        except Exception as e:
            logger.warning("Brave web search failed: %s", e)
            return []
        return [
            self._to_source({
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "content": item.get("description", ""),
            })
            for item in items[:max_results]
        ]

    def _to_source(self, item: dict) -> dict:
        url = item.get("url", "")
        has_author = bool(item.get("author"))
        return {
            "source_id": self.make_source_id(url),
            "url": url,
            "doi": None,
            "isbn": None,
            "title": item.get("title", ""),
            "authors": [item["author"]] if item.get("author") else [],
            "publisher": url.split("/")[2] if url.count("/") >= 2 else None,
            "year": None,
            "abstract": (item.get("content") or "")[:500],
            "source_type": "web",
            "reliability_score": self._score_reliability(url, has_author),
            "http_verified": True,
            "language": "en",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    async def health_check(self) -> bool:
        if self.tavily_api_key:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.post(
                        "https://api.tavily.com/search",
                        json={"api_key": self.tavily_api_key, "query": "test", "max_results": 1},
                    )
                    return r.status_code == 200
            except Exception:
                pass
        return bool(self.brave_api_key)
