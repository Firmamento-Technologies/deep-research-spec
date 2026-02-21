# 18_citations.md — Citation Management & Verification

## §18.1 Citation Mappa e Formattazione (CitationManager)

```python
from typing import Literal, Optional
from pydantic import BaseModel, HttpUrl

CitationStyle = Literal["Harvard", "APA", "Chicago", "Vancouver"]
SourceType = Literal["academic", "institutional", "web", "social", "book", "archive"]

class Source(BaseModel):
    source_id: str
    title: str
    authors: list[str]
    year: int
    publisher: Optional[str]
    url: Optional[HttpUrl]
    doi: Optional[str]
    isbn: Optional[str]
    source_type: SourceType
    reliability_score: float  # 0.0–1.0

class CitationEntry(BaseModel):
    source_id: str
    inline: str       # e.g. "(Smith, 2021)"
    bibliography: str # full formatted string

class CitationMap(BaseModel):
    style: CitationStyle
    entries: dict[str, CitationEntry]  # source_id -> CitationEntry
```

**Format rules per stile:**

| Style | Inline | Key rule |
|-------|--------|----------|
| Harvard | `(Author, Year)` | Author SURNAME, Initial. (Year). *Title*. Publisher. |
| APA | `(Author, Year, p.N)` | Author, A. B. (Year). *Title*. DOI/URL |
| Chicago | Footnote superscript | SURNAME, *Title* (City: Publisher, Year), p.N |
| Vancouver | `[N]` | N. Author AB. Title. *Journal*. Year;Vol(Issue):pages. |

**Fonti senza URL (§18.4):** ISBN → formatted via `isbnlib`; archival → `repository + call_number`; conference proceedings → `venue + year + page_range`. HTTP check skipped; DOI check applied if present.

---

AGENT: CitationManager [§18.1]
RESPONSIBILITY: Build citation map from source list using configured style
MODEL: deterministic (no LLM) / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  sources: list[Source]
  style: CitationStyle
OUTPUT: CitationMap
CONSTRAINTS:
  MUST format every source_id in sources into CitationEntry
  MUST use ISBN path for SourceType=="book" when doi is None
  NEVER hallucinate author or year — use source fields verbatim
  ALWAYS produce both inline and bibliography fields
ERROR_HANDLING:
  missing required field (title|year) -> log WARNING + placeholder "[INCOMPLETE_CITATION_{source_id}]" -> include in map with ghost_flag=True
  unsupported style value -> raise ValueError immediately -> fallback style="APA"
CONSUMES: [current_sources] from DocumentState
PRODUCES: [citation_map] -> DocumentState

---

## §18.2 Verifica Deterministica

```python
class DeterministicVerifyResult(BaseModel):
    source_id: str
    http_ok: bool           # HTTP HEAD returned 200 or 301/302→200
    doi_resolved: bool      # doi.org/{doi} returns 200
    title_match: bool       # title from CrossRef matches ±85% fuzzy
    verified: bool          # http_ok AND (doi_resolved if doi else True) AND title_match
```

**HTTP check:** `HEAD {url}` timeout=5s; follow redirects max 2; accept 200/301/302→200. DOI resolve: `GET https://doi.org/{doi}` timeout=8s; accept 200.

---

## §18.3 NLI Entailment Check

```python
class EntailmentLabel = Literal["entailment", "neutral", "contradiction"]

class NLIResult(BaseModel):
    source_id: str
    claim_text: str
    source_snippet: str      # ≤512 tokens from source body
    label: EntailmentLabel
    confidence: float        # 0.0–1.0 from softmax
    temporal_ok: bool        # claim date consistent with source date
    quantitative_ok: bool    # numbers in claim match source ±5%

class CitationVerifyResult(BaseModel):
    source_id: str
    deterministic: DeterministicVerifyResult
    nli: Optional[NLIResult]  # None if source body unavailable
    classification: Literal["valid", "mismatch", "ghost"]
    ghost_flag: bool
```

**Model:** `microsoft/deberta-v3-large-mnli` local inference, batch_size=8.

**Classification logic:**

| Condition | Classification | Behavior |
|-----------|---------------|----------|
| `deterministic.verified=True` AND `nli.label="entailment"` AND `temporal_ok` AND `quantitative_ok` | `valid` | Pass |
| `deterministic.verified=True` AND `nli.label in ["neutral","contradiction"]` | `mismatch` | Flag to Judge F; Writer instructed to attenuate claim |
| `deterministic.verified=False` OR `doi_resolved=False` | `ghost` | Route to §18.5 tracker; trigger missing_evidence path |

**Temporal consistency:** extract year from claim text via regex `\b(19|20)\d{2}\b`; compare to `source.year`; flag if claim asserts fact as current but source.year < current_year - 3.

**Quantitative consistency:** extract numerics from claim and source_snippet; match with ±5% tolerance; flag if deviation > 5%.

---

AGENT: CitationVerifier [§18.3]
RESPONSIBILITY: Verify each citation via HTTP, DOI, NLI entailment, temporal/quantitative checks
MODEL: deberta-v3-large-mnli (local) / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  sources: list[Source]
  draft_claims: list[dict]  # [{claim_text: str, source_id: str}]
OUTPUT: list[CitationVerifyResult]
CONSTRAINTS:
  MUST run HTTP check before NLI (skip NLI if ghost detected)
  NEVER send source body > 512 tokens to DeBERTa
  ALWAYS set ghost_flag=True when classification=="ghost"
  MUST apply quantitative check only when numerics present in both claim and snippet
  NEVER classify as "valid" if temporal_ok=False
ERROR_HANDLING:
  HTTP timeout > 5s -> http_ok=False -> classification="ghost" -> log
  DeBERTa inference error -> nli=None -> classification based on deterministic only -> WARNING log
  source body unavailable -> skip nli -> set classification="neutral_unverified" treated as "mismatch"
CONSUMES: [current_sources, current_draft] from DocumentState
PRODUCES: [citation_verify_results] -> DocumentState

---

## §18.4 Gestione Fonti senza URL

```python
class ArchivalSource(BaseModel):
    source_id: str
    isbn: Optional[str]
    repository: Optional[str]
    call_number: Optional[str]
    conference: Optional[str]
    pages: Optional[str]

def verify_archival(src: ArchivalSource) -> DeterministicVerifyResult:
    doi_resolved = False
    http_ok = False  # no URL available
    title_match = True  # accepted on face value
    if src.isbn:
        title_match = _isbnlib_lookup(src.isbn)  # bool
    return DeterministicVerifyResult(
        source_id=src.source_id,
        http_ok=http_ok,
        doi_resolved=doi_resolved,
        title_match=title_match,
        verified=title_match  # special rule: verified if ISBN confirms title
    )
```

---

## §18.5 HallucinationRateTracker

```sql
-- PostgreSQL schema
CREATE TABLE hallucination_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id       UUID NOT NULL REFERENCES runs(id),
    section_idx  INTEGER NOT NULL,
    model_id     TEXT NOT NULL,       -- e.g. "anthropic/claude-opus-4-5"
    agent_role   TEXT NOT NULL,       -- "writer" | "judge_f" | "researcher"
    ghost_count  INTEGER NOT NULL DEFAULT 0,
    total_citations INTEGER NOT NULL,
    hallucination_rate DECIMAL(5,4) GENERATED ALWAYS AS
                    (ghost_count::decimal / NULLIF(total_citations,0)) STORED,
    detected_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_hallucination_model ON hallucination_events(model_id, detected_at);

-- Rolling 10-run rate view
CREATE VIEW model_hallucination_rolling AS
SELECT
    model_id,
    COUNT(*) AS run_count,
    AVG(hallucination_rate) AS avg_rate,
    MAX(detected_at) AS last_seen
FROM hallucination_events
GROUP BY model_id
HAVING COUNT(*) >= 10;
```

**Alert threshold:** `avg_rate > 0.05` on `run_count >= 10` → emit Prometheus alert `drs_hallucination_rate_critical{model_id}` → Grafana dashboard (see §23.3) → recommendation: evaluate model replacement.

**missing_evidence path:** when `classification=="ghost"` detected by CitationVerifier:

```python
# In Aggregator routing (see §9.4)
if any(r.classification == "ghost" for r in citation_verify_results):
    # Route to targeted Researcher before Reflector
    return "fail_missing_ev"  # -> researcher_rerun node
```

Researcher receives `targeted_queries: list[str]` derived from ghost claim text; max 3 alternative queries per ghost citation; results re-enter CitationVerifier before Writer.

**Grafana panel config (abbreviated):**

```yaml
panel:
  title: "Hallucination Rate by Model (10-run rolling)"
  type: bargauge
  query: "SELECT model_id, avg_rate FROM model_hallucination_rolling"
  thresholds:
    - value: 0.0,  color: green
    - value: 0.03, color: yellow
    - value: 0.05, color: red     # alert fires here
  alert:
    condition: "avg_rate > 0.05 AND run_count >= 10"
    severity: HIGH
    channel: slack
```

<!-- SPEC_COMPLETE -->