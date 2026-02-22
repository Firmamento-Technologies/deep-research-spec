"""SourceConnector ABC, SourceRanker, DiversityAnalyzer — §17.1, §17.8, §17.9."""
from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Source Types (C01 resolved: "web" not "general"; "upload" not "uploaded") ─
SourceType = Literal["academic", "institutional", "web", "social", "upload"]

# ── Reliability base ranges by type — §17.1 ─────────────────────────────────
RELIABILITY_BASE: dict[SourceType, tuple[float, float]] = {
    "academic": (0.80, 0.95),
    "institutional": (0.85, 0.95),
    "web": (0.40, 0.70),
    "social": (0.20, 0.40),
    "upload": (1.00, 1.00),
}

# ── Ranking weights — §17.9 ─────────────────────────────────────────────────
RANKING_WEIGHTS: dict[str, float] = {
    "reliability": 0.40,
    "relevance": 0.35,
    "recency": 0.15,
    "abstract_quality": 0.10,
}

# ── Diversity thresholds — §17.8 ────────────────────────────────────────────
DIVERSITY_THRESHOLDS: dict[str, float] = {
    "max_publisher_fraction": 0.40,
    "max_author_fraction": 0.30,
    "max_year_fraction": 0.50,
}


# ── Models ───────────────────────────────────────────────────────────────────

class RankedSource(BaseModel):
    """§17.9 — Source with ranking metadata."""
    source_id: str
    url: str | None = None
    doi: str | None = None
    isbn: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    publisher: str | None = None
    year: int | None = None
    abstract: str | None = None
    full_text_snippet: str | None = None
    source_type: SourceType
    reliability_score: float = Field(ge=0.0, le=1.0)
    http_verified: bool = False
    language: str = "en"
    fetched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Ranking fields
    relevance_score: float = 0.5
    quality_score: float = 0.5
    recency_weight: float = 0.5
    composite_rank: float = 0.0
    is_duplicate: bool = False
    duplicate_of: str | None = None


class DiversityReport(BaseModel):
    """§17.8 — Source diversity analysis."""
    publisher_concentration: float = 0.0
    author_concentration: float = 0.0
    year_concentration: float = 0.0
    diversity_score: float = 1.0
    violations: list[Literal[
        "PUBLISHER_CONCENTRATION",
        "AUTHOR_CONCENTRATION",
        "YEAR_CONCENTRATION",
    ]] = Field(default_factory=list)
    diversification_required: bool = False
    diversification_query_hint: str = ""


# ── SourceConnector ABC — §17.1 ─────────────────────────────────────────────

class SourceConnector(ABC):
    """Abstract base for all source connectors. §17.1."""

    connector_id: str
    source_type: SourceType
    reliability_base: float
    enabled: bool = True

    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[dict]:
        """Search for sources matching *query*. Returns raw source dicts."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the connector is reachable."""
        ...

    @staticmethod
    def make_source_id(identifier: str) -> str:
        """Generate deterministic source_id from URL, DOI, or file path."""
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]


# ── SourceRanker — §17.9 ────────────────────────────────────────────────────

class SourceRanker:
    """Score, deduplicate, and rank sources. §17.9.

    Uses sentence-transformers for relevance when available;
    falls back to reliability-only ranking if embedding model is unavailable.
    """

    def __init__(self, max_output: int = 15, dedup_threshold: float = 0.90):
        self.max_output = max_output
        self.dedup_threshold = dedup_threshold
        self._embedder = None

    def _get_embedder(self):
        """Lazy-load sentence-transformers embedding model."""
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                logger.warning("RANKER_EMBEDDING_UNAVAILABLE: sentence-transformers not installed")
                self._embedder = False  # sentinel
        return self._embedder if self._embedder is not False else None

    def _compute_relevance(self, query: str, text: str) -> float:
        """Cosine similarity between query and text embeddings."""
        embedder = self._get_embedder()
        if embedder is None:
            return 0.5  # fallback
        try:
            from sentence_transformers.util import cos_sim
            q_emb = embedder.encode(query, convert_to_tensor=True)
            t_emb = embedder.encode(text, convert_to_tensor=True)
            return float(cos_sim(q_emb, t_emb).item())
        except Exception:
            logger.warning("Relevance computation failed, using default 0.5")
            return 0.5

    def _compute_recency(self, year: int | None) -> float:
        """Recency weight: max(0, 1 - (current_year - year) / 20). §17.9."""
        if year is None:
            return 0.3  # default for unknown year
        current_year = datetime.now(timezone.utc).year
        return max(0.0, 1.0 - (current_year - year) / 20.0)

    def rank(self, sources: list[dict], query: str) -> list[RankedSource]:
        """Score, dedup, rank, and truncate to max_output. §17.9."""
        if not sources:
            return []

        ranked: list[RankedSource] = []
        seen_titles: dict[str, str] = {}  # normalized_title → source_id

        for s in sources:
            sid = s.get("source_id", SourceConnector.make_source_id(
                s.get("url") or s.get("doi") or s.get("title", "")
            ))
            text = s.get("abstract") or s.get("title", "")
            rel = s.get("reliability_score", 0.5)
            relevance = self._compute_relevance(query, text)
            recency = self._compute_recency(s.get("year"))
            abstract_quality = min(1.0, len(text) / 500) if text else 0.0

            composite = (
                RANKING_WEIGHTS["reliability"] * rel
                + RANKING_WEIGHTS["relevance"] * relevance
                + RANKING_WEIGHTS["recency"] * recency
                + RANKING_WEIGHTS["abstract_quality"] * abstract_quality
            )

            # Simple title-based dedup
            norm_title = (s.get("title") or "").lower().strip()
            is_dup = False
            dup_of = None
            if norm_title in seen_titles:
                is_dup = True
                dup_of = seen_titles[norm_title]
            else:
                seen_titles[norm_title] = sid

            rs = RankedSource(
                source_id=sid,
                url=s.get("url"),
                doi=s.get("doi"),
                isbn=s.get("isbn"),
                title=s.get("title", ""),
                authors=s.get("authors", []),
                publisher=s.get("publisher"),
                year=s.get("year"),
                abstract=s.get("abstract"),
                full_text_snippet=s.get("full_text_snippet"),
                source_type=s.get("source_type", "web"),
                reliability_score=rel,
                http_verified=s.get("http_verified", False),
                language=s.get("language", "en"),
                relevance_score=relevance,
                quality_score=abstract_quality,
                recency_weight=recency,
                composite_rank=composite,
                is_duplicate=is_dup,
                duplicate_of=dup_of,
            )
            ranked.append(rs)

        # Remove duplicates, sort descending by composite, truncate
        unique = [r for r in ranked if not r.is_duplicate]
        unique.sort(key=lambda r: r.composite_rank, reverse=True)
        return unique[: self.max_output]


# ── DiversityAnalyzer — §17.8 ───────────────────────────────────────────────

class DiversityAnalyzer:
    """Detect concentration in source pool and generate diversification hints. §17.8."""

    def __init__(self, thresholds: dict[str, float] | None = None):
        self.thresholds = thresholds or DIVERSITY_THRESHOLDS

    def analyze(self, sources: list[dict], section_query: str = "") -> DiversityReport:
        """Compute diversity report. §17.8."""
        if not sources:
            return DiversityReport()

        n = len(sources)
        violations: list[str] = []

        # Publisher concentration
        pubs = [s.get("publisher") or "unknown" for s in sources]
        pub_counts = {}
        for p in pubs:
            pub_counts[p] = pub_counts.get(p, 0) + 1
        pub_conc = max(pub_counts.values()) / n
        top_pub = max(pub_counts, key=pub_counts.get)
        if pub_conc > self.thresholds["max_publisher_fraction"]:
            violations.append("PUBLISHER_CONCENTRATION")

        # Author concentration (first author)
        authors = [s.get("authors", ["unknown"])[0] if s.get("authors") else "unknown" for s in sources]
        auth_counts = {}
        for a in authors:
            auth_counts[a] = auth_counts.get(a, 0) + 1
        auth_conc = max(auth_counts.values()) / n
        top_author = max(auth_counts, key=auth_counts.get)
        if auth_conc > self.thresholds["max_author_fraction"]:
            violations.append("AUTHOR_CONCENTRATION")

        # Year concentration
        years = [s.get("year") for s in sources if s.get("year") is not None]
        if years:
            year_counts = {}
            for y in years:
                year_counts[y] = year_counts.get(y, 0) + 1
            year_conc = max(year_counts.values()) / n
            top_year = max(year_counts, key=year_counts.get)
            if year_conc > self.thresholds["max_year_fraction"]:
                violations.append("YEAR_CONCENTRATION")
        else:
            year_conc = 0.0
            top_year = "N/A"

        diversity_score = 1.0 - max(pub_conc, auth_conc, year_conc)
        diversification_required = len(violations) > 0

        hint = ""
        if diversification_required:
            parts = []
            if "PUBLISHER_CONCENTRATION" in violations:
                parts.append(f"Exclude publisher:{top_pub}.")
            if "YEAR_CONCENTRATION" in violations:
                parts.append(f"Prioritize sources from years other than {top_year}.")
            if "AUTHOR_CONCENTRATION" in violations:
                parts.append(f"Seek sources by authors other than {top_author}.")
            hint = " ".join(parts)

        return DiversityReport(
            publisher_concentration=pub_conc,
            author_concentration=auth_conc,
            year_concentration=year_conc,
            diversity_score=diversity_score,
            violations=violations,  # type: ignore[arg-type]
            diversification_required=diversification_required,
            diversification_query_hint=hint,
        )
