# §37 Extensibility and Plugin System

## §37.0 Shared Types

```python
from abc import ABC, abstractmethod
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

SourceType = Literal["academic", "institutional", "web", "social", "custom"]
VerdictOutcome = Literal["PASS", "FAIL", "VETO"]
VetoCategory = Literal["fabricated_source", "factual_error", "logical_contradiction", "plagiarism", "domain_violation"]
FormatID = Literal["docx", "pdf", "markdown", "latex", "html", "json", "custom"]
ConfidenceLevel = Literal["low", "medium", "high"]
JudgeDomain = Literal["general", "legal", "medical", "financial", "technical"]
SeriesRole = Literal["primary", "secondary", "reference"]
```

---

## §37.1 SourceConnector Interface

```python
class Source(BaseModel):
    """Canonical source record. See §17 for reliability scoring."""
    url: Optional[str]
    doi: Optional[str]
    isbn: Optional[str]
    title: str
    authors: list[str]
    publisher: str
    published_at: Optional[str]           # ISO 8601
    source_type: SourceType
    reliability_score: float              # 0.0–1.0; see §17 for defaults
    abstract: Optional[str]
    full_text_snippet: Optional[str]      # max 500 chars
    connector_id: str                     # identifies which plugin produced this
    metadata: dict[str, Any]             # connector-specific extras

class SourceConnector(ABC):
    """
    Plugin interface for custom data sources.

    Discovery: place module in src/connectors/plugins/; system loads all
    subclasses at startup via importlib. connector_id must be unique across
    all registered plugins.

    Custom reliability_score defaults may be set via YAML
    sources.reliability_overrides (see §29.4).
    """

    @property
    @abstractmethod
    def connector_id(self) -> str:
        """Unique slug, e.g. 'corporate_db', 'pubmed', 'bloomberg'."""
        ...

    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        """Declared type governs diversity accounting; see §17.8."""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
        *,
        section_scope: Optional[str] = None,  # section title for targeted search
        filters: Optional[dict[str, Any]] = None,
    ) -> list[Source]:
        """
        Return up to max_results Sources ranked by relevance.
        MUST: return [] on zero results (never raise for empty).
        NEVER: exceed max_results.
        ALWAYS: populate reliability_score and connector_id.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if backend is reachable. Called during pre-flight (§4.1)."""
        ...
```

### §37.1.1 Corporate DB Connector Example

```python
import asyncpg
from src.connectors.base import SourceConnector, Source

class CorporateDatabaseConnector(SourceConnector):
    """
    Example: internal PostgreSQL knowledge base.
    Reliability override recommended in YAML: sources.reliability_overrides.
    """

    def __init__(self, dsn: str, reliability: float = 0.95):
        self._dsn = dsn
        self._reliability = reliability  # enterprise source: high trust

    @property
    def connector_id(self) -> str:
        return "corporate_db"

    @property
    def source_type(self) -> SourceType:
        return "custom"

    async def search(
        self,
        query: str,
        max_results: int = 10,
        *,
        section_scope: Optional[str] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[Source]:
        pool = await asyncpg.create_pool(self._dsn)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT title, authors, published_at, content, doc_url, department
                FROM knowledge_base
                WHERE to_tsvector('english', content) @@ plainto_tsquery($1)
                ORDER BY ts_rank(to_tsvector('english', content),
                                 plainto_tsquery($1)) DESC
                LIMIT $2
                """,
                query, max_results,
            )
        await pool.close()
        return [
            Source(
                url=r["doc_url"],
                title=r["title"],
                authors=r["authors"] or [],
                publisher=r["department"] or "Internal",
                published_at=r["published_at"].isoformat() if r["published_at"] else None,
                source_type=self.source_type,
                reliability_score=self._reliability,
                full_text_snippet=r["content"][:500],
                connector_id=self.connector_id,
                metadata={"department": r["department"]},
            )
            for r in rows
        ]

    async def health_check(self) -> bool:
        try:
            pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=1)
            await pool.fetchval("SELECT 1")
            await pool.close()
            return True
        except Exception:
            return False
```

**YAML registration** (§29.4):
```yaml
sources:
  custom_connectors:
    - module: "src.connectors.plugins.corporate_db"
      class: "CorporateDatabaseConnector"
      config:
        dsn: "${CORPORATE_DB_DSN}"
        reliability: 0.95
  reliability_overrides:
    "corporate_db": 0.95
```

---

## §37.2 Judge Interface

```python
class JuryInput(BaseModel):
    draft: str
    section_title: str
    section_scope: str
    sources: list[Source]
    citation_map: dict[str, str]          # source_id -> formatted citation
    style_profile: dict[str, Any]         # see §26
    style_exemplar: Optional[str]
    iteration: int
    approved_sections_summary: str        # compressed context; see §14
    outline: list[dict[str, Any]]
    custom_rubric: Optional[dict[str, Any]]  # domain-specific; see §37.2.1

class DimensionScore(BaseModel):
    name: str
    score: float                          # 0.0–10.0
    weight: float                         # contribution to judge's composite

class VerdictSchema(BaseModel):
    """Canonical output contract for ALL Judge implementations."""
    judge_id: str
    domain: JudgeDomain
    outcome: VerdictOutcome
    veto_category: Optional[VetoCategory]  # required if outcome == "VETO"
    confidence: ConfidenceLevel
    dimension_scores: list[DimensionScore]
    composite_score: float                # 0.0–10.0; weighted avg of dimensions
    motivation: str                       # max 400 chars; actionable
    failed_claims: list[str]             # verbatim text spans
    missing_evidence: list[str]          # query hints for Researcher
    external_sources_consulted: list[str] # URLs; Judge F micro-search; see §8.2.1
    suggested_span_edits: list[dict[str, str]]  # {affected_text, action}

class Judge(ABC):
    """
    Plugin interface for domain-specific jury members.

    Integration with Aggregator (see §9): Aggregator calls
    Judge.evaluate() and inserts VerdictSchema into jury_verdicts list.
    CSS calculation (see §9.1) uses outcome field directly.
    No Aggregator changes needed to add a new Judge subclass.

    Domain judges slot into existing mini-jury positions OR form a
    fourth mini-jury (jury_weights must sum to 1.0 after addition; see §9.2).
    """

    @property
    @abstractmethod
    def judge_id(self) -> str:
        """Unique slug, e.g. 'legal_compliance', 'medical_accuracy'."""
        ...

    @property
    @abstractmethod
    def domain(self) -> JudgeDomain:
        ...

    @property
    @abstractmethod
    def mini_jury_slot(self) -> Literal["R", "F", "S", "custom"]:
        """
        'R'|'F'|'S': replaces one tier slot in existing mini-jury (see §8).
        'custom': registers as fourth mini-jury; update jury_weights in §9.2.
        """
        ...

    @abstractmethod
    async def evaluate(self, input: JuryInput) -> VerdictSchema:
        """
        MUST: return VerdictSchema with all required fields populated.
        MUST: set veto_category if outcome == 'VETO'.
        NEVER: return outcome='PASS' with composite_score < 5.0.
        ALWAYS: populate motivation with actionable text (not vague).
        ERROR: parse failure -> return FAIL outcome with confidence='low'.
        """
        ...
```

### §37.2.1 Domain-Specific Judge Example: Legal/Medical

```python
LEGAL_RUBRIC: dict[str, Any] = {
    "dimensions": [
        {"name": "citation_to_statute", "weight": 0.35,
         "prompt_hint": "Every legal claim must cite statute, regulation, or case law."},
        {"name": "jurisdiction_accuracy", "weight": 0.30,
         "prompt_hint": "Claims must specify jurisdiction; do not generalize across systems."},
        {"name": "disclaimer_presence", "weight": 0.20,
         "prompt_hint": "Document must include 'not legal advice' disclaimer if advisory tone."},
        {"name": "temporal_validity", "weight": 0.15,
         "prompt_hint": "Laws cited must be in force at document date; flag repealed statutes."},
    ],
    "veto_triggers": [
        "fabricated_case_law",
        "wrong_jurisdiction_applied",
    ],
}

MEDICAL_RUBRIC: dict[str, Any] = {
    "dimensions": [
        {"name": "clinical_evidence_level", "weight": 0.40,
         "prompt_hint": "Prefer RCT/meta-analysis; flag expert opinion as lower evidence."},
        {"name": "dosage_accuracy", "weight": 0.25,
         "prompt_hint": "Any dosage claim must cite primary source; flag ranges vs. absolutes."},
        {"name": "contraindication_disclosure", "weight": 0.20,
         "prompt_hint": "Treatments must disclose known contraindications from source."},
        {"name": "disclaimer_presence", "weight": 0.15,
         "prompt_hint": "Must include 'consult physician' if patient-facing content."},
    ],
    "veto_triggers": [
        "fabricated_clinical_trial",
        "dosage_error",
    ],
}

class DomainJudge(Judge):
    """
    Legal or Medical domain judge.
    Slots into mini_jury_slot='custom' (fourth mini-jury).
    Aggregator integration: zero changes needed; see §9.
    Add to jury_weights YAML (see §29.3): domain_legal: 0.20,
    adjusting other weights so sum == 1.0.
    """

    def __init__(
        self,
        judge_id: str,
        domain: JudgeDomain,
        rubric: dict[str, Any],
        llm_client,  # injected; see §25.10
        model: str = "openai/o3",
    ):
        self._judge_id = judge_id
        self._domain = domain
        self._rubric = rubric
        self._llm = llm_client
        self._model = model

    @property
    def judge_id(self) -> str:
        return self._judge_id

    @property
    def domain(self) -> JudgeDomain:
        return self._domain

    @property
    def mini_jury_slot(self) -> Literal["R", "F", "S", "custom"]:
        return "custom"

    async def evaluate(self, input: JuryInput) -> VerdictSchema:
        rubric_text = "\n".join(
            f"- {d['name']} (weight {d['weight']}): {d['prompt_hint']}"
            for d in self._rubric["dimensions"]
        )
        prompt = (
            f"You are a {self._domain} domain reviewer. "
            f"Evaluate the draft STRICTLY against this rubric:\n{rubric_text}\n\n"
            "Return JSON matching VerdictSchema. "
            "VETO if any veto_trigger condition is met: "
            f"{self._rubric['veto_triggers']}.\n\n"
            f"DRAFT:\n{input.draft}"
        )
        raw = await self._llm.call(
            model=self._model,
            system_prompt=f"Domain judge: {self._domain}. Output valid JSON only.",
            user_prompt=prompt,
            temperature=0.1,
            max_tokens=1024,
        )
        try:
            data = _parse_json(raw["content"])
            return VerdictSchema(judge_id=self._judge_id, domain=self._domain, **data)
        except Exception:
            return VerdictSchema(
                judge_id=self._judge_id, domain=self._domain,
                outcome="FAIL", confidence="low",
                composite_score=0.0, dimension_scores=[],
                motivation="Parse error during evaluation.",
                failed_claims=[], missing_evidence=[],
                external_sources_consulted=[], suggested_span_edits=[],
            )
```

**Aggregator integration** — zero code changes to Aggregator (§9):

```yaml
# §29.3 — add domain jury weight; all weights must sum to 1.0
convergence:
  jury_weights:
    reasoning: 0.28
    factual:   0.36
    style:     0.16
    domain_legal: 0.20   # new; Aggregator reads dynamically
```

```python
# Aggregator reads jury_weights from config; no hardcoded keys.
# DomainJudge.evaluate() returns VerdictSchema; Aggregator treats
# outcome field identically to built-in judges.
```

---

## §37.3 OutputFormatter Interface

```python
class FormattedDocument(BaseModel):
    format_id: str
    content: bytes
    mime_type: str
    filename: str
    encoding: str = "utf-8"
    metadata: dict[str, Any]

class DocumentPayload(BaseModel):
    """Input to every OutputFormatter."""
    sections: list[dict[str, Any]]        # ApprovedSection list; see §4.6
    bibliography: list[dict[str, Any]]    # formatted citation entries
    outline: list[dict[str, Any]]
    topic: str
    style_profile: dict[str, Any]
    run_report: dict[str, Any]
    target_words: int
    language: str

class OutputFormatter(ABC):
    """
    Plugin interface for custom export formats.
    Discovery: same mechanism as SourceConnector (§37.1).
    Publisher (§5.19) calls format() for each registered formatter.
    """

    @property
    @abstractmethod
    def format_id(self) -> str:
        """Must not collide with built-in IDs: docx, pdf, markdown, latex, html, json."""
        ...

    @property
    @abstractmethod
    def mime_type(self) -> str:
        ...

    @abstractmethod
    async def format(self, payload: DocumentPayload) -> FormattedDocument:
        """
        MUST: return FormattedDocument with non-empty content bytes.
        NEVER: modify payload in place.
        ERROR: raise ValueError with descriptive message; Publisher catches
               and logs; other formats still produced.
        """
        ...
```

### §37.3.1 Custom Format Example: Notion Export

```python
import httpx, json

class NotionFormatter(OutputFormatter):
    """Exports document as Notion page blocks via Notion API."""

    def __init__(self, notion_token: str, parent_page_id: str):
        self._token = notion_token
        self._parent = parent_page_id

    @property
    def format_id(self) -> str:
        return "notion"

    @property
    def mime_type(self) -> str:
        return "application/json"

    async def format(self, payload: DocumentPayload) -> FormattedDocument:
        blocks = []
        for section in payload.sections:
            blocks.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": section["title"]}}]},
            })
            for para in section["content"].split("\n\n"):
                if para.strip():
                    blocks.append({
                        "object": "block", "type": "paragraph",
                        "paragraph": {"rich_text": [{"text": {"content": para.strip()}}]},
                    })

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.notion.com/v1/pages",
                headers={"Authorization": f"Bearer {self._token}",
                         "Notion-Version": "2022-06-28"},
                json={
                    "parent": {"page_id": self._parent},
                    "properties": {"title": {"title": [{"text": {"content": payload.topic}}]}},
                    "children": blocks[:100],  # Notion API limit
                },
            )
        resp.raise_for_status()
        page_data = resp.json()
        return FormattedDocument(
            format_id=self.format_id,
            content=json.dumps(page_data).encode(),
            mime_type=self.mime_type,
            filename=f"{payload.topic[:50]}_notion.json",
            metadata={"notion_page_id": page_data.get("id")},
        )
```

---

## §37.4 Multi-Document Mode

### §37.4.1 Shared Glossary Schema

```python
class GlossaryTerm(BaseModel):
    term: str
    definition: str                       # max 200 chars; single sentence
    first_defined_in: str                 # document_id
    section_idx: int
    aliases: list[str]
    domain: Optional[str]

class SeriesGlossary(BaseModel):
    series_id: str
    terms: dict[str, GlossaryTerm]        # key = canonical term (lowercase)
    last_updated: str                     # ISO 8601

    def merge(self, new_terms: list[GlossaryTerm]) -> list[str]:
        """
        Add new_terms; skip if term already exists with same definition.
        Return list of conflict terms requiring human resolution.
        """
        conflicts = []
        for t in new_terms:
            key = t.term.lower()
            if key in self.terms and self.terms[key].definition != t.definition:
                conflicts.append(key)
            else:
                self.terms[key] = t
        return conflicts
```

**Persistence**: `series_glossary` table in PostgreSQL; Writer receives glossary as
`{term: definition}` dict injected into context prompt after Style Exemplar (§3B.2).

### §37.4.2 Citation Reuse — Verified Sources Not Re-Processed

```python
class VerifiedSourceCache(BaseModel):
    """
    Redis key: series:{series_id}:verified_sources
    TTL: 30 days (see §21.3).
    """
    doi: Optional[str]
    url: Optional[str]
    title: str
    nli_entailment_score: float           # from Citation Verifier (§5.4)
    http_verified: bool
    ghost_flag: bool
    verified_at: str                      # ISO 8601
    verified_in_doc: str                  # document_id of first verification
    citation_string: dict[str, str]       # style_id -> formatted string
    reliability_score: float

class SeriesCitationManager:
    """
    Before Citation Verifier (§5.4) runs on a source, check cache.
    Cache hit (cosine_similarity >= 0.90 on title embedding): skip
    HTTP + NLI checks; reuse stored nli_entailment_score and citation_string.
    Cache miss: run full verification pipeline; write result to cache.
    NEVER reuse a cached source with ghost_flag == True.
    """

    async def lookup(
        self,
        series_id: str,
        source: Source,
        style_id: str,
    ) -> Optional[VerifiedSourceCache]:
        ...  # cosine similarity check on title embedding; threshold >= 0.90

    async def store(
        self,
        series_id: str,
        verified: VerifiedSourceCache,
    ) -> None:
        ...
```

### §37.4.3 Cross-Referencing System

```python
class CrossReference(BaseModel):
    from_doc_id: str
    from_section_idx: int
    to_doc_id: str
    to_section_idx: int
    reference_text: str                   # inline anchor, e.g. "see Doc-2 §3"
    relation: Literal["supports", "extends", "contrasts", "defines"]

class SeriesCrossReferenceIndex(BaseModel):
    series_id: str
    references: list[CrossReference]

    def get_references_for_section(
        self, doc_id: str, section_idx: int
    ) -> list[CrossReference]:
        return [r for r in self.references
                if r.from_doc_id == doc_id and r.from_section_idx == section_idx]
```

Writer receives `cross_reference_hints: list[CrossReference]` in context prompt
when writing sections with `relation in ["supports","extends"]` to prior documents.
Coherence Guard (§5.17 / §15.1) verifies `relation="contrasts"` references do not
introduce unresolved contradictions flagged as `HARD` conflicts.

### §37.4.4 Style Consistency Cross-Document

```python
class SeriesStyleContract(BaseModel):
    """
    Frozen at first document approval; see §3B.3 for freeze mechanism.
    Injected into Style Calibration Gate (§3B) of all subsequent documents.
    """
    series_id: str
    style_exemplar: str                   # 250-word approved sample; see §3B.2
    frozen_ruleset: dict[str, Any]        # L1/L2/L3 rules; see §26.1
    style_profile_id: str                 # see §26
    series_role: SeriesRole
    frozen_at: str                        # ISO 8601; document_id that froze it
    allowed_overrides: list[str]          # rule IDs that secondary docs may relax

    def validate_new_doc_config(self, config: dict[str, Any]) -> list[str]:
        """
        Return list of violations if new document config conflicts with contract.
        Violations: different style_profile_id, L1 rules removed, exemplar replaced.
        Warnings (not violations): L3 guide rules relaxed if in allowed_overrides.
        """
        violations = []
        if config.get("style_profile") != self.style_profile_id:
            violations.append(
                f"style_profile mismatch: contract={self.style_profile_id}"
            )
        return violations
```

**Lifecycle**:

| Event | Action |
|---|---|
| Series created (doc 1) | `SeriesStyleContract` created after §3B approval |
| Doc 2+ starts | Contract injected into §3B; Style Calibration Gate skips regeneration |
| Doc 2+ Style Linter (§5.9) | Validates against `frozen_ruleset`; `allowed_overrides` exempted |
| Style conflict detected | Run Companion (§6) notifies user; `validate_new_doc_config` violations block run |

**DocumentState fields added for series mode** (extends §4.6):

```python
# Additional fields in DocumentState for multi-document mode
series_id: Optional[str]
series_role: Optional[SeriesRole]
series_glossary: Optional[dict[str, str]]          # term -> definition
series_style_contract: Optional[dict[str, Any]]    # SeriesStyleContract
cross_reference_index: Optional[list[dict]]        # CrossReference list
citation_cache_hits: int                           # count for Run Report
citation_cache_misses: int
```

<!-- SPEC_COMPLETE -->