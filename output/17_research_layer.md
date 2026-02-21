# 17_research_layer.md
## §17 — Research Layer: Source Connectors, Ranking, and Diversity

---

### §17.0 Shared Types

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

SourceType = Literal["academic", "institutional", "web_general", "social", "user_upload"]
ReliabilityScore = float  # range [0.0, 1.0]

class Source(BaseModel):
    source_id: str                          # sha256(url or doi or file_path)
    url: Optional[str]
    doi: Optional[str]
    isbn: Optional[str]
    title: str
    authors: list[str]
    publisher: str
    year: Optional[int]
    abstract: Optional[str]
    full_text_snippet: Optional[str]        # ≤500 words extracted
    source_type: SourceType
    reliability_score: ReliabilityScore
    fetched_at: str                         # ISO 8601
    http_verified: bool
    language: str                           # ISO 639-1

class RankedSource(Source):
    relevance_score: float                  # [0.0, 1.0]
    quality_score: float                    # [0.0, 1.0]
    recency_weight: float                   # [0.0, 1.0]
    composite_rank: float                   # weighted aggregate
    is_duplicate: bool
    duplicate_of: Optional[str]             # source_id

class DiversityReport(BaseModel):
    publisher_concentration: float          # highest single-publisher fraction
    author_concentration: float
    year_concentration: float               # highest single-year fraction
    diversity_score: float                  # [0.0, 1.0], 1.0 = perfectly diverse
    violations: list[Literal[
        "PUBLISHER_CONCENTRATION",
        "AUTHOR_CONCENTRATION",
        "YEAR_CONCENTRATION"
    ]]
    diversification_required: bool
    diversification_query_hint: str         # injected into targeted Researcher call
```

---

### §17.1 SourceConnector Interface

Every connector MUST implement this protocol. Plugin discovery via Python entry_points group `drs.source_connectors`.

```python
from abc import abstractmethod
from typing import Protocol

class SourceConnector(Protocol):
    connector_id: str
    source_type: SourceType
    reliability_base: ReliabilityScore      # floor before content scoring
    enabled: bool

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int,
    ) -> list[Source]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
```

Reliability ranges by type (used as `reliability_base`):

| `source_type` | Range |
|---|---|
| `academic` | 0.80 – 0.95 |
| `institutional` | 0.85 – 0.95 |
| `web_general` | 0.40 – 0.70 |
| `social` | 0.20 – 0.40 |
| `user_upload` | 1.00 (treated as ground truth) |

---

### §17.2 AcademicConnector

```python
class AcademicConnectorConfig(BaseModel):
    crossref_mailto: str
    semantic_scholar_api_key: Optional[str]
    arxiv_enabled: bool = True
    doaj_enabled: bool = True
    max_results_per_provider: int = 10

AGENT: AcademicConnector [§17.2]
RESPONSIBILITY: search academic databases and return verified peer-reviewed sources
MODEL: deterministic HTTP client / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  query: str
  max_results: int
OUTPUT: list[Source]
CONSTRAINTS:
  MUST set reliability_score >= 0.80 for DOI-verified sources
  MUST set http_verified=True only after HTTP 200 or DOI resolution confirms existence
  MUST populate doi field when available
  NEVER fabricate author, year, or title fields
  ALWAYS respect CrossRef polite pool rate: 50 req/s with CROSSREF_MAILTO header
ERROR_HANDLING:
  CrossRef 429 -> exponential backoff 2s/4s/8s -> fallback to Semantic Scholar
  Semantic Scholar 503 -> circuit breaker 5min -> proceed with CrossRef results only
  Zero results -> return [] (caller handles gap via §17.8)
CONSUMES: [query, max_results] from caller
PRODUCES: list[Source] with source_type="academic"
```

---

### §17.3 InstitutionalConnector

```python
INSTITUTIONAL_DOMAIN_ALLOWLIST: list[str] = [
    ".gov", ".eu", ".un.org", ".who.int", ".oecd.org",
    ".worldbank.org", ".imf.org", ".nato.int"
]

AGENT: InstitutionalConnector [§17.3]
RESPONSIBILITY: retrieve sources from institutional and government domains
MODEL: Tavily API with domain filter / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  query: str
  max_results: int
OUTPUT: list[Source]
CONSTRAINTS:
  MUST filter results to INSTITUTIONAL_DOMAIN_ALLOWLIST
  MUST set reliability_score >= 0.85
  MUST verify domain suffix matches allowlist before including result
  NEVER include results from domains not in allowlist
ERROR_HANDLING:
  Tavily 429 -> wait Retry-After header value -> retry once -> return []
  Domain filter returns zero -> return [] (no relaxation of domain constraint)
CONSUMES: [query, max_results]
PRODUCES: list[Source] with source_type="institutional"
```

---

### §17.4 WebGeneralConnector

```python
AGENT: WebGeneralConnector [§17.4]
RESPONSIBILITY: retrieve general web sources via Tavily with Brave fallback
MODEL: Tavily API primary / Brave Search API fallback / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  query: str
  max_results: int
OUTPUT: list[Source]
CONSTRAINTS:
  MUST assign reliability_score using heuristic: HTTPS=+0.10, news_domain=+0.05,
    known_wiki=-0.05 (Wikipedia treated as lead not citation), no_author=-0.15
  MUST cap reliability_score at 0.70
  NEVER set reliability_score > 0.70 for web_general sources
ERROR_HANDLING:
  Tavily down -> Brave Search API -> if both down -> ScraperFallback (§17.5)
  Both APIs 429 simultaneously -> ScraperFallback (§17.5)
CONSUMES: [query, max_results]
PRODUCES: list[Source] with source_type="web_general"
```

---

### §17.5 ScraperFallback

```python
AGENT: ScraperFallback [§17.5]
RESPONSIBILITY: scrape URLs directly when all search APIs are unavailable
MODEL: BeautifulSoup + Playwright / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  query: str
  max_results: int
OUTPUT: list[Source]
CONSTRAINTS:
  MUST check robots.txt before scraping; skip URL if Disallow matches path
  MUST set reliability_score = reliability from WebGeneralConnector heuristics
  MUST add warning flag in source metadata: scraped_fallback=True
  NEVER scrape paywalled content (detect 402/paywall patterns, skip)
  ALWAYS respect crawl-delay directive in robots.txt; default 1.0s if absent
ERROR_HANDLING:
  Playwright timeout > 10s -> skip URL, continue to next
  robots.txt parse failure -> treat as Disallow all, skip URL
  All URLs fail -> return [] with log SCRAPER_TOTAL_FAILURE
CONSUMES: [query, max_results]
PRODUCES: list[Source] with source_type="web_general", scraped_fallback=True
```

---

### §17.6 SocialConnector

```python
AGENT: SocialConnector [§17.6]
RESPONSIBILITY: retrieve social media sources for sentiment and discourse analysis
MODEL: Reddit API / Twitter Academic API / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  query: str
  max_results: int
OUTPUT: list[Source]
CONSTRAINTS:
  MUST set reliability_score in [0.20, 0.40]
  MUST require explicit source_filter="social" in config to activate
  MUST set source_type="social"
  NEVER use social sources for factual claims without corroboration from reliability_score >= 0.70 source
ERROR_HANDLING:
  Twitter API 403 -> skip Twitter, proceed with Reddit only
  Rate limit -> return partial results collected so far
CONSUMES: [query, max_results]
PRODUCES: list[Source] with source_type="social"
```

---

### §17.7 UserUploadConnector

Processing is **fully local**. No content sent to external providers.

```python
class UploadedSourceMetadata(BaseModel):
    file_id: str
    filename: str
    file_type: Literal["pdf", "docx", "txt", "md"]
    upload_timestamp: str
    chunk_count: int
    embedding_model: str                    # local model id

AGENT: UserUploadConnector [§17.7]
RESPONSIBILITY: process user-uploaded files locally and return as Sources with reliability=1.0
MODEL: local embedding model (sentence-transformers/all-MiniLM-L6-v2) / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  query: str
  max_results: int
  uploaded_source_ids: list[str]
OUTPUT: list[Source]
CONSTRAINTS:
  MUST process files locally; NEVER send file content to any external API
  MUST set reliability_score = 1.0 (user content = ground truth per §17.0)
  MUST chunk documents at 512 tokens with 64-token overlap
  MUST use cosine similarity >= 0.75 threshold for chunk retrieval
  ALWAYS set source_type="user_upload"
ERROR_HANDLING:
  PDF parse failure -> attempt text extraction via pdfminer -> log warning, return []
  Embedding model unavailable -> raise CRITICAL, block run (no fallback: local-only constraint)
CONSUMES: [query, max_results, uploaded_source_ids] from DocumentState
PRODUCES: list[Source] with source_type="user_upload", reliability_score=1.0
```

---

### §17.8 SourceDiversityAnalyzer

```python
DIVERSITY_THRESHOLDS = {
    "max_publisher_fraction": 0.40,     # > 40% same publisher -> violation
    "max_author_fraction": 0.30,        # > 30% same first-author -> violation
    "max_year_fraction": 0.50,          # > 50% same publication year -> violation
}

AGENT: SourceDiversityAnalyzer [§17.8]
RESPONSIBILITY: detect concentration in source pool and trigger diversification
MODEL: deterministic / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  sources: list[Source]
  section_query: str
OUTPUT: DiversityReport
CONSTRAINTS:
  MUST compute publisher_concentration as max(count(s.publisher) for s in sources) / len(sources)
  MUST compute author_concentration using first author of each source
  MUST compute year_concentration as max(count(s.year) for s in sources) / len(sources)
  MUST set diversification_required=True if ANY threshold exceeded
  MUST generate diversification_query_hint when diversification_required=True;
    hint format: "Exclude publisher:{top_publisher}. Prioritize sources from
    years other than {top_year}. Seek sources by authors other than {top_author}."
  NEVER block the pipeline if diversification_required=True; only set flag and hint
  ALWAYS include diversity_score = 1.0 - max(three concentrations)
ERROR_HANDLING:
  sources empty list -> return DiversityReport with diversity_score=1.0,
    diversification_required=False, violations=[]
  year field None for all sources -> skip year_concentration check
CONSUMES: [current_sources] from DocumentState
PRODUCES: [diversity_report] -> DocumentState; if diversification_required=True,
  triggers Researcher re-run with diversification_query_hint injected
```

Action on concentration: set `diversification_required=True` → Researcher re-activated with `diversification_query_hint`. Max 1 diversification re-run per section. Result merged with original pool; duplicates removed by SourceRanker (§17.9).

---

### §17.9 SourceRanker

```python
RANKING_WEIGHTS = {
    "reliability": 0.40,
    "relevance": 0.35,
    "recency": 0.15,
    "abstract_quality": 0.10,
}

AGENT: SourceRanker [§17.9]
RESPONSIBILITY: score, deduplicate, and rank sources before passing to Writer pipeline
MODEL: sentence-transformers/all-MiniLM-L6-v2 (local) + deterministic scoring / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  sources: list[Source]
  section_query: str
  max_output: int                         # from config, default 15
OUTPUT: list[RankedSource]
CONSTRAINTS:
  MUST compute relevance_score via cosine similarity between
    sentence-embedding(section_query) and sentence-embedding(source.abstract or source.title)
  MUST compute recency_weight = max(0, 1 - (current_year - source.year) / 20) when year present
  MUST set is_duplicate=True and duplicate_of=canonical_source_id when cosine_similarity
    between two sources' abstracts >= 0.90; retain source with higher reliability_score
  MUST compute composite_rank = sum(weight * score for weight, score in RANKING_WEIGHTS)
  MUST return sorted descending by composite_rank, length capped at max_output
  MUST flag adversarial sources: if source contradicts >= 2 other sources on same claim
    (detected by cosine similarity of negated claim embedding < 0.30), set
    adversarial_flag=True in metadata
  NEVER return duplicate sources (is_duplicate=True excluded from output)
ERROR_HANDLING:
  Embedding model failure -> fall back to reliability_score-only ranking (set
    relevance_score=0.5 for all, log RANKER_EMBEDDING_UNAVAILABLE)
  sources empty -> return []
CONSUMES: [current_sources] from DocumentState
PRODUCES: [ranked_sources] -> DocumentState
```

---

### §17.M Connector Config (YAML fragment)

```yaml
sources:
  reliability_overrides:
    "yourdomain.com": 0.95
    "twitter.com": 0.25

  academic:
    crossref_mailto: "${CROSSREF_MAILTO}"
    semantic_scholar_api_key: "${SEMANTIC_SCHOLAR_API_KEY}"
    arxiv_enabled: true
    doaj_enabled: true
    max_results_per_provider: 10

  institutional:
    domain_allowlist_extend: []             # append to default list

  web_general:
    primary: "tavily"
    fallback: "brave"

  social:
    enabled: false                          # requires explicit opt-in

  user_upload:
    chunk_size_tokens: 512
    chunk_overlap_tokens: 64
    similarity_threshold: 0.75

  ranking:
    max_sources_per_section: 15
    dedup_cosine_threshold: 0.90
    adversarial_detection: true

  diversity:
    max_publisher_fraction: 0.40
    max_author_fraction: 0.30
    max_year_fraction: 0.50
    max_diversification_reruns: 1
```

---

### §17.M DocumentState fields produced by this layer

```python
# Fields written to DocumentState (see §4.6 for full schema)
current_sources: list[Source]               # raw from connectors
ranked_sources: list[RankedSource]          # after §17.9
diversity_report: DiversityReport           # after §17.8
```

<!-- SPEC_COMPLETE -->