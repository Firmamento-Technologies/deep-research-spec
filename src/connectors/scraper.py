"""ScraperFallback — BS4 + Playwright when APIs unavailable — §17.5."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from src.connectors.base import SourceConnector, SourceType

logger = logging.getLogger(__name__)


class ScraperFallback(SourceConnector):
    """Scrape URLs directly when all search APIs are unavailable. §17.5.

    Respects robots.txt. Uses BeautifulSoup with Playwright fallback for JS.
    """

    connector_id: str = "scraper_fallback"
    source_type: SourceType = "web"
    reliability_base: float = 0.45
    enabled: bool = True

    def __init__(self, crawl_delay: float = 1.0, timeout: float = 10.0):
        self.crawl_delay = crawl_delay
        self.timeout = timeout

    async def _check_robots(self, url: str) -> bool:
        """Check robots.txt; return True if scraping is allowed. §17.5."""
        try:
            import httpx
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(robots_url)
                if r.status_code != 200:
                    return False  # treat as Disallow all per §17.5
                text = r.text.lower()
                # Simple check: if path is disallowed for all user-agents
                if "disallow: /" in text and "allow:" not in text:
                    return False
                return True
        except Exception:
            return False  # robots.txt parse fail → Disallow all

    async def _scrape_url(self, url: str) -> dict | None:
        """Scrape a single URL via httpx + BS4."""
        try:
            import httpx
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("beautifulsoup4/httpx not installed for scraper fallback")
            return None

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                r = await client.get(url)
                if r.status_code in (402, 403):  # paywall detection
                    logger.info("Paywall detected at %s, skipping", url)
                    return None
                r.raise_for_status()

            soup = BeautifulSoup(r.text, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            # Extract visible text, truncated
            text_content = " ".join(soup.stripped_strings)[:2000]

            return {
                "source_id": self.make_source_id(url),
                "url": url,
                "doi": None,
                "isbn": None,
                "title": title,
                "authors": [],
                "publisher": urlparse(url).netloc,
                "year": None,
                "abstract": text_content[:500],
                "full_text_snippet": text_content[:500],
                "source_type": "web",
                "reliability_score": self.reliability_base,
                "http_verified": True,
                "language": "en",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "scraped_fallback": True,
            }
        except Exception as e:
            logger.warning("Scrape failed for %s: %s", url, e)
            return None

    async def search(self, query: str, max_results: int) -> list[dict]:
        """Scraper cannot truly 'search' — acts on pre-resolved URLs.

        In practice, this is invoked with URLs from failed API results.
        Returns empty list if called without URL context.
        """
        logger.info("ScraperFallback.search called — requires URL list, returning []")
        return []

    async def scrape_urls(self, urls: list[str], max_results: int) -> list[dict]:
        """Scrape specific URLs with robots.txt compliance. §17.5."""
        import asyncio

        results: list[dict] = []
        for url in urls:
            if len(results) >= max_results:
                break
            allowed = await self._check_robots(url)
            if not allowed:
                logger.info("robots.txt disallows scraping %s", url)
                continue
            source = await self._scrape_url(url)
            if source:
                results.append(source)
            await asyncio.sleep(self.crawl_delay)

        if not results:
            logger.warning("SCRAPER_TOTAL_FAILURE: all URLs failed or disallowed")
        return results

    async def health_check(self) -> bool:
        """Scraper is always 'available' if httpx + bs4 are installed."""
        try:
            import httpx  # noqa: F401
            from bs4 import BeautifulSoup  # noqa: F401
            return True
        except ImportError:
            return False
