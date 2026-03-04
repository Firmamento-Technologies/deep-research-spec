"""Researcher node — gathers sources for a document section.

The Researcher combines web search and Knowledge Space (RAG) retrieval to
collect relevant sources for a given section. It generates multiple search
queries from the section's title and scope, executes them in parallel, and
returns a ranked, deduplicated list of SearchResult objects.

Web search providers:
- Perplexity Sonar (via OpenRouter)
- Tavily (direct API)

RAG search:
- Semantic similarity search over Knowledge Space chunks (if configured)

The Researcher does NOT call the LLM for summarization — it only retrieves
and ranks sources. The Writer node will consume these sources to generate
the actual section content.

Spec: §9 Researcher node, §17 Knowledge Spaces, §19 Budget tracking
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.models.state import ResearchState, Section

from src.models.state import SearchResult
from src.services.web_search import get_search_client, generate_search_queries

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_QUERIES_PER_SECTION = 5   # Max web queries to generate
RESULTS_PER_QUERY       = 5   # Results per web query
RAG_TOP_K               = 10  # RAG chunks to retrieve
RAG_MIN_SIMILARITY      = 0.5 # Cosine similarity threshold
MAX_TOTAL_RESULTS       = 20  # Cap on final merged results

# Ranking weights
RAG_BOOST_THRESHOLD = 0.7  # RAG results with sim > 0.7 get priority


# ---------------------------------------------------------------------------
# Researcher Node
# ---------------------------------------------------------------------------

async def researcher_node(state: ResearchState) -> dict:
    """Gather sources for the current section.

    Flow:
    1. Get current section from state
    2. Generate 3-5 search queries from section.title + scope
    3. Execute web search (multi_search)
    4. Execute RAG search (if knowledge_space_id present)
    5. Merge and deduplicate results
    6. Rank results (RAG > web, similarity-weighted)
    7. Update section.search_results
    8. Emit SSE events (progress + completion)

    Args:
        state: ResearchState with current_section index.

    Returns:
        Partial state update with sections[i].search_results populated.

    Raises:
        ValueError: If current_section is out of bounds.
    """
    doc_id         = state["doc_id"]
    sections       = state.get("sections", [])
    current_idx    = state.get("current_section", 0)
    knowledge_space_id = state.get("knowledge_space_id")
    broker         = state.get("broker")

    if current_idx >= len(sections):
        raise ValueError(
            f"current_section={current_idx} out of bounds (sections={len(sections)})"
        )

    section = sections[current_idx]

    logger.info(
        "[%s] Researcher started for section %d: '%s'",
        doc_id, current_idx, section.title,
    )

    t0 = time.monotonic()

    # Emit NODE_STARTED
    if broker:
        await broker.emit(doc_id, "NODE_STARTED", {
            "node": "researcher",
            "section_idx": current_idx,
            "section_title": section.title,
        })

    # --- 1. Generate queries ---
    queries = _generate_queries(section)
    logger.info("[%s] Generated %d queries: %s", doc_id, len(queries), queries)

    # --- 2. Web search ---
    web_results = await _web_search(
        state=state,
        queries=queries,
        doc_id=doc_id,
        broker=broker,
    )

    # --- 3. RAG search (if enabled) ---
    rag_results = []
    if knowledge_space_id:
        rag_results = await _rag_search(
            state=state,
            section=section,
            space_id=knowledge_space_id,
            doc_id=doc_id,
            broker=broker,
        )

    # --- 4. Merge and rank ---
    all_results = _merge_and_rank(web_results, rag_results)

    logger.info(
        "[%s] Researcher gathered %d results (web=%d, rag=%d)",
        doc_id, len(all_results), len(web_results), len(rag_results),
    )

    # --- 5. Update section ---
    section.search_results = all_results
    section.status = "researching"  # Mark as in-progress

    # --- 6. Emit NODE_COMPLETED ---
    duration = time.monotonic() - t0
    if broker:
        await broker.emit(doc_id, "NODE_COMPLETED", {
            "node": "researcher",
            "section_idx": current_idx,
            "duration_s": round(duration, 2),
            "results_count": len(all_results),
            "web_count": len(web_results),
            "rag_count": len(rag_results),
        })

    logger.info(
        "[%s] Researcher completed in %.2fs (%d results)",
        doc_id, duration, len(all_results),
    )

    # Return state updates
    return {
        "sections": sections,  # Updated in-place
        "status": "researching",
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _generate_queries(section) -> List[str]:
    """Generate 3-5 search queries from section title and scope.

    Uses the helper from web_search.py and adds a few variations.
    """
    # Base queries from helper
    base = generate_search_queries(
        section.title, section.scope, n=3
    )

    # Add a couple more specific queries
    extra = []
    if section.scope:
        # Query focused on scope only
        extra.append(f"{section.scope} research")
    if len(base) < MAX_QUERIES_PER_SECTION:
        # Query with "latest" keyword for recency
        extra.append(f"{section.title} {section.scope} latest")

    all_queries = base + extra
    return all_queries[:MAX_QUERIES_PER_SECTION]


async def _web_search(
    state: ResearchState,
    queries: List[str],
    doc_id: str,
    broker,
) -> List[SearchResult]:
    """Execute web search for all queries in parallel.

    Returns:
        List of SearchResult objects from web sources.
    """
    # Get search client (loads settings from DB)
    from src.llm.client import get_llm_client
    from services.redis_client import redis

    llm_client = await get_llm_client(db=None)  # TODO: inject db session
    search_client = await get_search_client(
        db=None,
        llm_client=llm_client,
        redis_client=redis,
    )

    # Emit progress
    if broker:
        await broker.emit(doc_id, "RESEARCHER_PROGRESS", {
            "step": "web_search",
            "queries_count": len(queries),
        })

    try:
        results = await search_client.multi_search(
            queries=queries,
            max_results=RESULTS_PER_QUERY,
        )
    finally:
        await search_client.aclose()

    logger.info("[%s] Web search returned %d results", doc_id, len(results))
    return results


async def _rag_search(
    state: ResearchState,
    section,
    space_id: str,
    doc_id: str,
    broker,
) -> List[SearchResult]:
    """Execute RAG search over Knowledge Space.

    Returns:
        List of SearchResult objects from RAG chunks.
    """
    from database.connection import get_db
    from services.semantic_search import search_chunks

    # Construct query from section
    query = f"{section.title} {section.scope}".strip()

    # Emit progress
    if broker:
        await broker.emit(doc_id, "RESEARCHER_PROGRESS", {
            "step": "rag_search",
            "space_id": space_id,
            "query": query[:60],
        })

    # Call semantic search
    async for db in get_db():
        try:
            chunks = await search_chunks(
                session=db,
                query=query,
                space_id=space_id,
                top_k=RAG_TOP_K,
                min_similarity=RAG_MIN_SIMILARITY,
            )
        except Exception as exc:
            logger.error("[%s] RAG search failed: %s", doc_id, exc)
            return []

    # Convert chunks to SearchResult
    results = []
    for chunk in chunks:
        results.append(
            SearchResult(
                title=f"RAG: {chunk['content'][:50]}...",
                url=f"chunk://{chunk['id']}",  # Internal chunk URI
                snippet=chunk["content"],
                source_type="rag",
                similarity=chunk["similarity"],
                chunk_id=chunk["id"],
            )
        )

    logger.info(
        "[%s] RAG search returned %d chunks (space=%s)",
        doc_id, len(results), space_id,
    )
    return results


def _merge_and_rank(
    web_results: List[SearchResult],
    rag_results: List[SearchResult],
) -> List[SearchResult]:
    """Merge web and RAG results, deduplicate, and rank.

    Ranking logic:
    1. RAG results with similarity > RAG_BOOST_THRESHOLD (priority)
    2. Remaining RAG results
    3. Web results

    Deduplication:
    - By URL for web results
    - By chunk_id for RAG results

    Returns:
        Ranked list of SearchResult (max MAX_TOTAL_RESULTS).
    """
    # Deduplicate web results by URL
    seen_urls = set()
    web_dedup = []
    for r in web_results:
        if r.url not in seen_urls:
            seen_urls.add(r.url)
            web_dedup.append(r)

    # Deduplicate RAG results by chunk_id
    seen_chunks = set()
    rag_dedup = []
    for r in rag_results:
        chunk_id = r.chunk_id or r.url  # fallback to URL
        if chunk_id not in seen_chunks:
            seen_chunks.add(chunk_id)
            rag_dedup.append(r)

    # Partition RAG results by similarity
    rag_high = [r for r in rag_dedup if (r.similarity or 0) > RAG_BOOST_THRESHOLD]
    rag_low  = [r for r in rag_dedup if (r.similarity or 0) <= RAG_BOOST_THRESHOLD]

    # Sort each partition
    rag_high.sort(key=lambda r: r.similarity or 0, reverse=True)
    rag_low.sort(key=lambda r: r.similarity or 0, reverse=True)
    web_dedup.sort(key=lambda r: r.title)  # Alphabetical fallback

    # Merge: high-sim RAG → low-sim RAG → web
    merged = rag_high + rag_low + web_dedup

    # Cap total results
    return merged[:MAX_TOTAL_RESULTS]
