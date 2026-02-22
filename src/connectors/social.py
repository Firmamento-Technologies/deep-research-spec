"""SocialConnector — Reddit/Twitter (opt-in only) — §17.6."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.connectors.base import SourceConnector, SourceType

logger = logging.getLogger(__name__)


class SocialConnector(SourceConnector):
    """Retrieve social media sources for sentiment and discourse analysis. §17.6.

    Requires explicit opt-in via config ``sources.social.enabled=true``.
    Reliability capped at [0.20, 0.40].
    """

    connector_id: str = "social"
    source_type: SourceType = "social"
    reliability_base: float = 0.25
    enabled: bool = False  # opt-in only

    def __init__(self, reddit_client_id: str | None = None, reddit_secret: str | None = None):
        self.reddit_client_id = reddit_client_id
        self.reddit_secret = reddit_secret

    async def search(self, query: str, max_results: int) -> list[dict]:
        """Search Reddit for relevant posts. §17.6."""
        if not self.enabled:
            return []
        try:
            return await self._search_reddit(query, max_results)
        except Exception as e:
            logger.warning("Reddit search failed: %s", e)
            return []

    async def _search_reddit(self, query: str, max_results: int) -> list[dict]:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://www.reddit.com/search.json",
                params={"q": query, "limit": max_results, "sort": "relevance", "t": "year"},
                headers={"User-Agent": "DRS/1.0"},
            )
            r.raise_for_status()
            posts = r.json().get("data", {}).get("children", [])

        sources = []
        for post in posts:
            data = post.get("data", {})
            url = f"https://reddit.com{data.get('permalink', '')}"
            sources.append({
                "source_id": self.make_source_id(url),
                "url": url,
                "doi": None,
                "isbn": None,
                "title": data.get("title", ""),
                "authors": [data.get("author", "anonymous")],
                "publisher": "Reddit",
                "year": None,
                "abstract": (data.get("selftext") or "")[:500],
                "source_type": "social",
                "reliability_score": min(0.40, max(0.20, 0.20 + data.get("score", 0) / 10000)),
                "http_verified": True,
                "language": "en",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
        return sources

    async def health_check(self) -> bool:
        if not self.enabled:
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(
                    "https://www.reddit.com/r/test.json",
                    headers={"User-Agent": "DRS/1.0"},
                )
                return r.status_code == 200
        except Exception:
            return False
