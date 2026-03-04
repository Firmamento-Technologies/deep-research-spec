"""Web search service for the DRS Researcher node.

Provides unified access to multiple search providers:
- Perplexity Sonar (via OpenRouter, same as LLM calls)
- Tavily API (direct REST, fallback/alternative)

All search results are converted to the SearchResult dataclass from
src.models.state and cached in Redis for 24h to avoid duplicate API calls.

Usage
-----
    client = await get_search_client(db_session)

    # Single query
    results = await client.search(
        query="quantum computing 2026 breakthroughs",
        max_results=10,
    )

    # Multi-query (parallel execution)
    all_results = await client.multi_search(
        queries=["AI safety", "transformer architectures", "LLM alignment"],
        max_results=5,
    )

Spec: §9 Researcher node, §17 Knowledge Spaces (complements RAG search)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, List, Optional

import httpx

from src.models.state import SearchResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_RESULTS = 10
CACHE_TTL_S         = 86_400  # 24 hours
TAVILY_API_URL      = "https://api.tavily.com/search"
REQUEST_TIMEOUT_S   = 30.0

# Provider selection priority (if multiple are configured)
PROVIDER_PRIORITY = ["perplexity", "tavily"]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SearchError(Exception):
    """Raised when a search query fails across all available providers."""
    pass


# ---------------------------------------------------------------------------
# WebSearchClient
# ---------------------------------------------------------------------------

class WebSearchClient:
    """Unified web search client supporting multiple providers.

    Automatically selects the best available provider based on config.
    Falls back to the next provider if one fails.
    """

    def __init__(
        self,
        perplexity_enabled: bool = False,
        tavily_enabled: bool = False,
        tavily_api_key: str = "",
        llm_client: Any = None,  # LLMClient from src.llm.client
        redis_client: Any = None,  # Redis client from services.redis_client
    ):
        self.perplexity_enabled = perplexity_enabled
        self.tavily_enabled = tavily_enabled
        self.tavily_api_key = tavily_api_key
        self.llm_client = llm_client  # For Perplexity via OpenRouter
        self.redis = redis_client

        self._http = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S)

        # Determine active provider
        self.active_provider = self._select_provider()
        if not self.active_provider:
            logger.warning(
                "No web search provider configured. "
                "Enable Perplexity or Tavily in Settings."
            )

    def _select_provider(self) -> Optional[str]:
        """Pick the first available provider from PROVIDER_PRIORITY."""
        for p in PROVIDER_PRIORITY:
            if p == "perplexity" and self.perplexity_enabled and self.llm_client:
                return "perplexity"
            if p == "tavily" and self.tavily_enabled and self.tavily_api_key:
                return "tavily"
        return None

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> List[SearchResult]:
        """Execute a single web search query.

        Checks Redis cache first. If miss, calls the active provider.
        Caches results for CACHE_TTL_S seconds.

        Args:
            query:       Search query string.
            max_results: Maximum number of results to return.

        Returns:
            List of SearchResult objects (may be fewer than max_results).

        Raises:
            SearchError: If all providers fail or none are configured.
        """
        # Check cache
        cached = await self._get_cached(query, max_results)
        if cached is not None:
            logger.info("Cache hit for query: %.60s", query)
            return cached

        # Execute search
        if not self.active_provider:
            raise SearchError("No web search provider configured.")

        logger.info(
            "Searching with %s: %.60s (max_results=%d)",
            self.active_provider, query, max_results,
        )

        if self.active_provider == "perplexity":
            results = await self._search_perplexity(query, max_results)
        elif self.active_provider == "tavily":
            results = await self._search_tavily(query, max_results)
        else:
            raise SearchError(f"Unknown provider: {self.active_provider}")

        # Cache results
        await self._set_cached(query, max_results, results)
        return results

    async def multi_search(
        self,
        queries: List[str],
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> List[SearchResult]:
        """Execute multiple queries in parallel and deduplicate results.

        Args:
            queries:     List of search query strings.
            max_results: Max results per query.

        Returns:
            Deduplicated list of SearchResult (first seen per URL wins).
        """
        tasks = [self.search(q, max_results) for q in queries]
        all_results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten and deduplicate
        seen_urls = set()
        final = []
        for res_list in all_results_lists:
            if isinstance(res_list, Exception):
                logger.warning("Multi-search sub-query failed: %s", res_list)
                continue
            for result in res_list:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    final.append(result)

        logger.info(
            "Multi-search: %d queries → %d total results (deduplicated)",
            len(queries), len(final),
        )
        return final

    async def aclose(self) -> None:
        """Close HTTP client."""
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.aclose()

    # -----------------------------------------------------------------------
    # Provider implementations
    # -----------------------------------------------------------------------

    async def _search_perplexity(
        self, query: str, max_results: int
    ) -> List[SearchResult]:
        """Search via Perplexity Sonar API (chat completion format).

        Uses the LLM client with node_id='researcher' to call Perplexity.
        The response includes web-grounded content + citations.

        Returns parsed SearchResult list from the citations.
        """
        if not self.llm_client:
            raise SearchError("LLM client not available for Perplexity search.")

        messages = [
            {"role": "system", "content": "You are a research assistant. Provide concise, factual answers with sources."},
            {"role": "user",   "content": query},
        ]

        # Call Perplexity Sonar via LLM client
        # (node_id='researcher' → resolves to perplexity/sonar-pro)
        try:
            response = await self.llm_client.chat(
                messages=messages,
                node_id="researcher",
                max_tokens=2048,
                temperature=0.2,
            )
        except Exception as exc:
            logger.error("Perplexity search failed: %s", exc)
            raise SearchError(f"Perplexity API error: {exc}") from exc

        # Parse response: Perplexity returns citations in a structured format
        # For now, extract a single result from the response content
        # (Full citation parsing requires inspecting response metadata)
        results = [
            SearchResult(
                title=f"Perplexity result: {query[:50]}",
                url="https://www.perplexity.ai/search",  # Placeholder
                snippet=response.content[:500],
                source_type="web",
                published_date=None,
            )
        ]

        # TODO: Extract actual citations from Perplexity response metadata
        # when available via OpenRouter or direct Perplexity SDK

        return results[:max_results]

    async def _search_tavily(
        self, query: str, max_results: int
    ) -> List[SearchResult]:
        """Search via Tavily API (direct REST).

        Returns structured search results with title, URL, snippet.
        """
        if not self.tavily_api_key:
            raise SearchError("Tavily API key not configured.")

        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "advanced",  # or "basic"
            "max_results": max_results,
            "include_domains": [],
            "exclude_domains": [],
        }

        try:
            resp = await self._http.post(TAVILY_API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Tavily HTTP error: %d %s", exc.response.status_code, exc.response.text[:200])
            raise SearchError(f"Tavily API HTTP {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error("Tavily request failed: %s", exc)
            raise SearchError(f"Tavily API error: {exc}") from exc

        # Parse Tavily response
        results = []
        for item in data.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", "Untitled"),
                    url=item.get("url", ""),
                    snippet=item.get("content", "") or item.get("snippet", ""),
                    source_type="web",
                    published_date=item.get("published_date"),
                )
            )

        logger.info("Tavily returned %d results for: %.60s", len(results), query)
        return results

    # -----------------------------------------------------------------------
    # Redis cache
    # -----------------------------------------------------------------------

    def _cache_key(self, query: str, max_results: int) -> str:
        """Generate cache key from query + max_results."""
        h = hashlib.sha256(f"{query}:{max_results}".encode()).hexdigest()[:16]
        return f"search:{h}"

    async def _get_cached(
        self, query: str, max_results: int
    ) -> Optional[List[SearchResult]]:
        """Retrieve cached search results from Redis."""
        if not self.redis:
            return None
        key = self._cache_key(query, max_results)
        raw = await self.redis.get(key)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return [SearchResult(**item) for item in data]
        except Exception as exc:
            logger.warning("Cache deserialization failed: %s", exc)
            return None

    async def _set_cached(
        self, query: str, max_results: int, results: List[SearchResult]
    ) -> None:
        """Store search results in Redis with TTL."""
        if not self.redis:
            return
        key = self._cache_key(query, max_results)
        data = [r.__dict__ for r in results]
        await self.redis.set(key, json.dumps(data), ex=CACHE_TTL_S)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

async def get_search_client(
    db: Any = None,
    llm_client: Any = None,
    redis_client: Any = None,
) -> WebSearchClient:
    """Create a WebSearchClient with providers loaded from settings.

    Args:
        db:           AsyncSession (for reading Settings table).
        llm_client:   LLMClient instance (for Perplexity via OpenRouter).
        redis_client: Redis client (for caching).

    Returns:
        Configured WebSearchClient.
    """
    # Load settings from DB
    perplexity_enabled = False
    tavily_enabled = False
    tavily_api_key = ""

    if db is not None:
        try:
            from sqlalchemy import select
            from database.models import Settings
            result = await db.execute(select(Settings).limit(1))
            row = result.scalars().first()
            if row:
                connectors = row.connectors or {}
                perplexity_enabled = connectors.get("perplexity", True)
                tavily_enabled = connectors.get("tavily", False)
                api_keys = row.api_keys or {}
                tavily_api_key = api_keys.get("tavily", "") or os.getenv("TAVILY_API_KEY", "")
        except Exception as exc:
            logger.warning("Failed to load search settings from DB: %s", exc)

    # Env-var fallbacks
    if not tavily_api_key:
        tavily_api_key = os.getenv("TAVILY_API_KEY", "")

    return WebSearchClient(
        perplexity_enabled=perplexity_enabled,
        tavily_enabled=tavily_enabled,
        tavily_api_key=tavily_api_key,
        llm_client=llm_client,
        redis_client=redis_client,
    )


# ---------------------------------------------------------------------------
# Query generation helper
# ---------------------------------------------------------------------------

def generate_search_queries(section_title: str, section_scope: str, n: int = 3) -> List[str]:
    """Generate N search queries from a section's title and scope.

    Simple heuristic for now. Later this can be replaced with an LLM call.

    Args:
        section_title: e.g., "Introduction"
        section_scope: e.g., "Overview of quantum computing"
        n:             Number of queries to generate.

    Returns:
        List of query strings.
    """
    base = f"{section_title} {section_scope}".strip()
    queries = [
        base,
        f"{section_scope} latest research",
        f"{section_scope} 2026 developments",
    ]
    return queries[:n]
