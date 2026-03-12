# 🎯 COMPLETION ROADMAP — Path to 100%

> **Current Status:** 85% Complete (41/41 nodes implemented, 0% tested)  
> **Target:** 100% Production-Ready System  
> **Time Estimate:** 40-120 hours (1-4 weeks)  
> **Last Updated:** 2026-02-24

---

## 📊 Executive Summary

**What's Done:**
- ✅ All 41 nodes implemented
- ✅ Graph architecture complete (32 nodes wired)
- ✅ LLM client with prompt caching (§29.1)
- ✅ Model routing with presets (§29.3)
- ✅ RAG + SHINE infrastructure

**What's Missing:**
- 🔴 **0% test coverage** (BLOCKER)
- 🔴 **Jury tiering not active** (cost 15x higher)
- 🟡 **SHINE not functional** (only fallback works)
- 🟡 **Database schema undefined**
- 🟡 **Observability incomplete**

**Path Forward:** 3 phases over 1-4 weeks depending on scope.

---

## 🚦 PHASE 1: BLOCKERS (Week 1) — MANDATORY

**Goal:** Sistema funzionante end-to-end con costi sotto controllo.

**Effort:** 20-30 hours  
**Blockers Resolved:** Test suite passing, Jury optimized, DB ready, fail-safe errors

---

### Task 1.1: Run Test Suite & Fix Bugs ⭐ CRITICAL

**Priority:** S (BLOCKER)  
**Effort:** 8-12 hours  
**Blocking:** Everything

**Why Critical:**
- Code never executed → unknown bugs
- Import errors likely
- Type mismatches possible
- Integration failures probable

**Steps:**

```bash
# 1. Setup test environment
cd /path/to/deep-research-spec
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-shine.txt  # Optional, for SHINE tests
pip install pytest pytest-cov pytest-asyncio

# 3. Verify imports (quick smoke test)
python -c "from src.graph.graph import build_graph; print('✓ Graph imports OK')"
python -c "from src.graph.nodes.writer import writer_node; print('✓ Writer imports OK')"
python -c "from src.graph.nodes.jury import jury_node; print('✓ Jury imports OK')"
python -c "from src.llm.client import llm_client; print('✓ LLM client imports OK')"

# 4. Run test suite
pytest tests/ -v --tb=short --cov=src --cov-report=html

# 5. Expected issues (budget 10-15 bugs):
# - Import errors (missing __init__.py, wrong paths)
# - Type mismatches (dict vs TypedDict)
# - Missing environment variables (API keys)
# - Async/sync conflicts
# - JSON parsing failures
```

**Common Bugs & Fixes:**

```python
# Bug 1: ImportError in graph.py
# Fix: Add to src/graph/__init__.py
from .graph import build_graph
from .state import DocumentState

# Bug 2: TypedDict compatibility
# Fix: Use dict instead of TypedDict in function signatures
def writer_node(state: dict) -> dict:  # Not DocumentState
    ...

# Bug 3: Missing API keys in tests
# Fix: Add to tests/conftest.py
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Bug 4: Async context issues in jury.py
# Fix: Already handled with ThreadPoolExecutor fallback

# Bug 5: JSON parsing in judges
# Fix: Add try/except with structured outputs
try:
    verdict = json.loads(response["text"])
except json.JSONDecodeError:
    # Use structured output or regex fallback
    verdict = extract_verdict_regex(response["text"])
```

**Acceptance Criteria:**
- [ ] `pytest tests/` passes with 0 failures
- [ ] Code coverage > 60%
- [ ] All imports work
- [ ] No showstopper bugs

**Output:** `test-results-$(date).html` with coverage report

---

### Task 1.2: Integrate Routing in Jury (Cost Optimization) ⭐ HIGH ROI

**Priority:** A (HIGH ROI)  
**Effort:** 2-3 hours  
**Impact:** -91% jury cost ($3.96 → $0.35 per section)

**Problem:**
```python
# Current (jury.py line 19-21):
_MODEL_R = "openai/o3"  # Hardcoded tier3 ❌
_MODEL_F = "google/gemini-2.5-pro"  # Hardcoded tier3 ❌
_MODEL_S = "google/gemini-2.5-flash"  # Hardcoded tier2 ❌

# Result: Economy preset still pays $3.96/section
```

**Solution:**

```python
# File: src/graph/nodes/jury.py
# Lines to change: 19-21, 52-54

# 1. Import routing
from src.llm.routing import route_model

# 2. Remove hardcoded models
# DELETE:
# _MODEL_R = "openai/o3"
# _MODEL_F = "google/gemini-2.5-pro"
# _MODEL_S = "google/gemini-2.5-flash"

# 3. Update jury_node function (line 52-54)
def jury_node(state: dict) -> dict:
    # ... existing code ...
    
    # Get preset from state
    preset = state.get("quality_preset", "balanced")
    
    # Dynamic model routing (NEW)
    model_r = route_model("jury_r", preset)
    model_f = route_model("jury_f", preset)
    model_s = route_model("jury_s", preset)
    
    # Initialize judges with dynamic models
    judges_r = [JudgeR(f"R{i+1}", model_r) for i in range(jury_size)]
    judges_f = [JudgeF(f"F{i+1}", model_f) for i in range(jury_size)]
    judges_s = [JudgeS(f"S{i+1}", model_s, style_rules=style_rules) for i in range(jury_size)]
    
    # ... rest unchanged ...
```

**Test:**
```python
# tests/unit/test_jury_routing.py (NEW FILE)
def test_jury_uses_routing():
    from src.graph.nodes.jury import jury_node
    
    state = {
        "quality_preset": "economy",
        "current_draft": "test draft",
        "current_sources": [],
        "budget": {"jury_size": 1},
        "outline": [{"scope": "test"}],
        "current_section_idx": 0,
    }
    
    # Should not crash and should use economy models
    result = jury_node(state)
    assert "jury_verdicts" in result
    # Verify cost is low (requires mock LLM client)
```

**Acceptance Criteria:**
- [ ] Jury uses `route_model()` for all 3 dimensions
- [ ] Economy preset uses flash models
- [ ] Premium preset uses o3/gemini-pro
- [ ] Test passes

**Expected Cost Reduction:**
```
Before: 9 judges × tier3 = $3.96/section
After (economy): 9 judges × tier1 = $0.03/section
After (balanced): 3×tier1 + 3×tier2 + 3×tier3 = $0.40/section
After (premium): 9×tier3 = $3.96/section (unchanged)

Average savings: -85%
```

---

### Task 1.3: Setup PostgreSQL Schema ⭐ REQUIRED

**Priority:** A (BLOCKER for persistence)  
**Effort:** 1-2 hours  
**Blocking:** Checkpoint saves, cost tracking

**Problem:**
- Docker Compose has PostgreSQL, but no tables
- `section_checkpoint.py` tries to save → crashes

**Solution:**

```bash
# 1. Create init script
touch docker/init.sql
```

```sql
-- File: docker/init.sql

-- Document metadata
CREATE TABLE IF NOT EXISTS documents (
    doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic TEXT NOT NULL,
    target_words INT NOT NULL,
    quality_preset VARCHAR(20) DEFAULT 'balanced',
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    total_cost_usd FLOAT DEFAULT 0.0,
    status VARCHAR(20) DEFAULT 'in_progress'
);

-- Section checkpoints
CREATE TABLE IF NOT EXISTS sections (
    doc_id UUID NOT NULL,
    section_idx INT NOT NULL,
    section_scope TEXT,
    target_words INT,
    draft TEXT,
    css_final FLOAT,
    iteration_count INT DEFAULT 0,
    approved_at TIMESTAMP,
    PRIMARY KEY (doc_id, section_idx),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

-- LLM call tracking
CREATE TABLE IF NOT EXISTS llm_calls (
    id SERIAL PRIMARY KEY,
    doc_id UUID,
    section_idx INT,
    iteration INT,
    agent VARCHAR(100),
    model VARCHAR(100),
    tokens_in INT,
    tokens_out INT,
    cache_read_tokens INT DEFAULT 0,
    cache_creation_tokens INT DEFAULT 0,
    cost_usd FLOAT,
    latency_ms INT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

-- Jury verdicts history
CREATE TABLE IF NOT EXISTS verdicts (
    id SERIAL PRIMARY KEY,
    doc_id UUID,
    section_idx INT,
    iteration INT,
    judge_slot VARCHAR(10),
    dimension VARCHAR(10),
    pass_fail BOOLEAN,
    css_contribution FLOAT,
    confidence VARCHAR(20),
    veto_category VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_llm_calls_doc ON llm_calls(doc_id, section_idx);
CREATE INDEX idx_verdicts_doc ON verdicts(doc_id, section_idx);
CREATE INDEX idx_sections_doc ON sections(doc_id);

-- Cost aggregation view
CREATE OR REPLACE VIEW document_costs AS
SELECT 
    doc_id,
    COUNT(DISTINCT section_idx) as sections_completed,
    SUM(cost_usd) as total_cost,
    AVG(cost_usd) as avg_cost_per_call,
    SUM(cache_read_tokens) as total_cache_hits,
    SUM(cache_creation_tokens) as total_cache_writes
FROM llm_calls
GROUP BY doc_id;
```

**Update docker-compose.yml:**

```yaml
# File: docker-compose.yml (add volumes section)

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: drs
      POSTGRES_USER: drs
      POSTGRES_PASSWORD: drs_dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/init.sql:/docker-entrypoint-initdb.d/init.sql  # ← ADD THIS
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U drs"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**Test Connection:**

```bash
# 1. Start database
docker-compose up -d postgres

# 2. Wait for healthy
docker-compose ps postgres  # Should show "healthy"

# 3. Verify schema
docker exec -it $(docker ps -qf "name=postgres") psql -U drs -d drs -c "\dt"

# Expected output:
#              List of relations
#  Schema |    Name     | Type  | Owner 
# --------+-------------+-------+-------
#  public | documents   | table | drs
#  public | llm_calls   | table | drs
#  public | sections    | table | drs
#  public | verdicts    | table | drs
```

**Update section_checkpoint.py:**

```python
# File: src/graph/nodes/section_checkpoint.py
# Add connection string from environment

import os
import psycopg2
from psycopg2.extras import Json

def run(state: dict) -> dict:
    # ... existing code ...
    
    # Save to PostgreSQL
    conn_string = os.getenv(
        "DATABASE_URL",
        "postgresql://drs:drs_dev_password@localhost:5432/drs"
    )
    
    try:
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        
        # Insert/update section
        cur.execute("""
            INSERT INTO sections (doc_id, section_idx, section_scope, draft, css_final, approved_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (doc_id, section_idx) 
            DO UPDATE SET draft = EXCLUDED.draft, css_final = EXCLUDED.css_final
        """, (
            state["doc_id"],
            state["current_section_idx"],
            section["scope"],
            state["current_draft"],
            final_css
        ))
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")
    
    # ... rest unchanged ...
```

**Acceptance Criteria:**
- [ ] PostgreSQL starts with schema
- [ ] Tables created successfully
- [ ] `section_checkpoint.py` saves without error
- [ ] Query `SELECT * FROM sections` returns data

---

### Task 1.4: Fix Fail-Open Error Handling ⭐ SAFETY

**Priority:** A (SAFETY)  
**Effort:** 1 hour  
**Risk:** System degrades silently, poor quality approved

**Problem:**

```python
# File: src/graph/nodes/jury.py (lines 85-97)
# When judge fails:
verdicts.append({
    "pass_fail": True,  # ← APPROVES on error! ❌
    "css_contribution": 0.70,
    "confidence": "low",
    "motivation": f"[ERROR] {r}",
})
```

**Impact:** Infrastructure errors → draft approved → bad output delivered

**Solution:**

```python
# File: src/graph/nodes/jury.py
# Change lines 85-97:

if isinstance(r, Exception):
    logger.error("Judge evaluation failed: %s", r)
    # FAIL CLOSED: veto on error
    verdicts.append({
        "judge_slot": "error",
        "model": "error",
        "dimension_scores": {},
        "pass_fail": False,  # ← FAIL CLOSED ✓
        "veto_category": "technical_failure",  # ← Force rejection
        "confidence": "error",
        "motivation": f"[SYSTEM ERROR] Judge crashed: {str(r)[:200]}",
        "failed_claims": [],
        "missing_evidence": [],
        "external_sources_consulted": [],
        "css_contribution": 0.0,  # ← Zero contribution
    })
```

**Add Retry Logic (Optional but Recommended):**

```python
# File: src/graph/nodes/jury_base.py
# Add to JudgeBase class:

from tenacity import retry, stop_after_attempt, wait_exponential

class JudgeBase:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def evaluate(self, draft: str, sources: list, scope: str) -> dict:
        # Existing implementation with retry wrapper
        ...
```

**Test:**

```python
# tests/unit/test_jury_error_handling.py (NEW)
def test_jury_fails_closed_on_error():
    from src.graph.nodes.jury import jury_node
    from unittest.mock import patch
    
    # Mock judge to raise exception
    with patch("src.graph.nodes.judge_r.JudgeR.evaluate", side_effect=Exception("API Error")):
        state = {...}  # Valid state
        result = jury_node(state)
        
        # Should have error verdict with pass_fail=False
        verdicts = result["jury_verdicts"]
        error_verdicts = [v for v in verdicts if v.get("veto_category") == "technical_failure"]
        assert len(error_verdicts) > 0
        assert all(not v["pass_fail"] for v in error_verdicts)
```

**Acceptance Criteria:**
- [ ] Judge errors → `pass_fail=False`
- [ ] Veto category set to `technical_failure`
- [ ] CSS contribution = 0.0
- [ ] Test passes

---

### Task 1.5: Add Missing Dependencies to requirements.txt

**Priority:** B  
**Effort:** 30 minutes  

**Problem:** Some imports may fail if dependencies missing.

**Check & Fix:**

```bash
# 1. Verify all imports
python -c "import psycopg2; print('✓ psycopg2')" || pip install psycopg2-binary
python -c "import yaml; print('✓ yaml')" || pip install pyyaml
python -c "import tenacity; print('✓ tenacity')" || pip install tenacity
python -c "from FlagEmbedding import FlagModel; print('✓ FlagEmbedding')" || pip install FlagEmbedding

# 2. Freeze to requirements
pip freeze > requirements-frozen.txt

# 3. Update requirements.txt with missing entries
cat >> requirements.txt << EOF
psycopg2-binary==2.9.9
pyyaml==6.0.1
tenacity==8.2.3
FlagEmbedding==1.2.0
EOF
```

**Acceptance Criteria:**
- [ ] All imports work
- [ ] `pip install -r requirements.txt` succeeds
- [ ] No missing module errors

---

## ✅ PHASE 1 DELIVERABLE

**After completing tasks 1.1-1.5:**

```
✅ Test suite passing (60%+ coverage)
✅ Jury cost optimized (-85%)
✅ PostgreSQL ready with schema
✅ Fail-safe error handling
✅ All dependencies installed

STATUS: MVP Production-Ready System
COST: ~$2.00-3.00 per document (economy preset)
TIME: 20-30 hours
```

**You can SHIP THIS and iterate later.**

---

## 🚀 PHASE 2: OPTIMIZATIONS (Week 2) — HIGH ROI

**Goal:** Riduzione costi -60%, observability completa.

**Effort:** 15-20 hours  
**Optional but Recommended**

---

### Task 2.1: Complete SHINE Integration ⭐ HIGH ROI

**Priority:** A (40% cost reduction)  
**Effort:** 4-6 hours  
**Impact:** Writer cost $8.00 → $4.68 (-41%)

**Problem:** SHINE adapter exists but LoRA not applied to LLM calls.

**Solution:**

```python
# File: src/llm/client.py
# Add LoRA support (SHINE-specific)

def call(
    self,
    model: str,
    messages: list[dict],
    system: str | list[dict] | None = None,
    lora_adapter: Any | None = None,  # ← NEW
    **kwargs
) -> dict:
    # ... existing code ...
    
    if model.startswith("anthropic/"):
        # Check if LoRA active
        if lora_adapter is not None:
            # SHINE LoRA integration
            # NOTE: This requires custom Anthropic API support
            # For now: log and proceed without LoRA
            logger.info("LoRA adapter active (SHINE mode)")
            # TODO: Apply LoRA via custom endpoint or adapter injection
        
        response = self.anthropic.messages.create(...)
```

**Alternative (Recommended): Use SHINE as Preprocessing**

```python
# File: src/graph/nodes/shine_adapter.py
# Instead of generating LoRA for LLM, generate compressed context

def run(self, state: DocumentState) -> dict:
    corpus = state.get("compressed_corpus", "")
    
    if SHINE_AVAILABLE and len(corpus) > 4000:
        # Use SHINE to compress corpus further
        compressed = self.shine.compress(corpus, target_length=1200)
        logger.info(f"SHINE compressed {len(corpus)} → {len(compressed)} tokens")
        
        return {
            "compressed_corpus": compressed,  # Override with SHINE output
            "shine_active": True,
        }
    else:
        return {"shine_active": False}
```

**Test:**

```bash
# 1. Install SHINE (optional, requires GPU)
git clone https://github.com/Yewei-Liu/SHINE.git
pip install -e SHINE/

# 2. Test compression
python -c "
from src.graph.nodes.shine_adapter import shine_adapter_node
state = {'compressed_corpus': 'test ' * 2000}
result = shine_adapter_node(state)
print('SHINE active:', result.get('shine_active'))
"

# 3. Measure token reduction
# Before: 8000 tokens → $0.12 per writer call
# After: 1200 tokens → $0.018 per writer call (-85%)
```

**Acceptance Criteria:**
- [ ] SHINE compresses corpus when >4000 tokens
- [ ] Writer receives compressed corpus
- [ ] Token count reduced by 70-80%
- [ ] Test passes

---

### Task 2.2: Load Style Profile Rules from Config

**Priority:** B  
**Effort:** 2-3 hours  
**Impact:** Better Writer output → fewer iterations

**Problem:** Writer uses generic fallback instead of L1/L2 rules.

**Solution:**

```yaml
# File: config/style_profiles.yaml (NEW)

academic:
  name: "Academic Research Paper"
  rules:
    - "Use passive voice for methodology"
    - "Cite every claim with [source_id]"
    - "Avoid first-person pronouns"
    - "Use formal vocabulary"
    - "Structure: Introduction → Methods → Results → Discussion"
  
business:
  name: "Business Report"
  rules:
    - "Executive summary at top"
    - "Use bullet points for key findings"
    - "Include actionable recommendations"
    - "Charts and tables for data"
    - "Professional but conversational tone"

technical:
  name: "Technical Documentation"
  rules:
    - "Code examples inline"
    - "Step-by-step instructions"
    - "Prerequisites section"
    - "Troubleshooting section"
    - "Clear headings and subheadings"
```

```python
# File: src/graph/nodes/writer.py
# Update _get_style_profile_rules:

import yaml
from pathlib import Path

def _get_style_profile_rules(style_profile: Any) -> str:
    # Load from config
    config_path = Path("config/style_profiles.yaml")
    
    if config_path.exists():
        with open(config_path) as f:
            profiles = yaml.safe_load(f)
        
        # Get profile name
        profile_name = (
            style_profile if isinstance(style_profile, str)
            else style_profile.get("name", "academic")
        )
        
        # Load rules
        profile = profiles.get(profile_name, profiles.get("academic", {}))
        rules = profile.get("rules", [])
        
        if rules:
            return "Style rules:\n" + "\n".join(f"- {r}" for r in rules)
    
    # Fallback
    return "Follow academic writing conventions. Be precise and well-sourced."
```

**Acceptance Criteria:**
- [ ] `config/style_profiles.yaml` created with 3+ profiles
- [ ] Writer loads rules correctly
- [ ] Test with academic/business/technical profiles
- [ ] Fallback works if file missing

---

### Task 2.3: Build Knowledge Base (Memvid)

**Priority:** B  
**Effort:** 30 minutes  
**Impact:** -50% researcher cost, better accuracy

**Steps:**

```bash
# 1. Collect documents
mkdir -p knowledge_base
cp docs/*.md knowledge_base/
cp specs/*.md knowledge_base/
# Add any PDFs, papers, or domain knowledge

# 2. Run builder script
python scripts/build_memvid_kb.py \
  --input knowledge_base/ \
  --output drs_knowledge.mp4 \
  --chunk-size 500 \
  --overlap 50

# 3. Verify KB
python -c "
from src.connectors.memvid_connector import MemvidConnector
connector = MemvidConnector('drs_knowledge.mp4')
results = connector.search('What is CSS score?', k=3)
print(f'Found {len(results)} results')
for r in results:
    print(f'- {r[\"title\"]}: {r[\"content\"][:100]}...')
"

# 4. Update researcher to use KB
# Already integrated in researcher.py (memvid_local connector)
```

**Acceptance Criteria:**
- [ ] `drs_knowledge.mp4` file exists
- [ ] Search returns relevant results
- [ ] Researcher prioritizes local sources
- [ ] External API calls reduced by 50%

---

### Task 2.4: Add Prometheus Metrics

**Priority:** B  
**Effort:** 4-6 hours  
**Impact:** Real-time cost visibility, performance monitoring

**Implementation:**

```python
# File: src/observability/metrics.py (NEW)

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import time

registry = CollectorRegistry()

# LLM metrics
llm_cost_total = Counter(
    "llm_cost_usd_total",
    "Total LLM cost in USD",
    ["model", "agent", "preset"],
    registry=registry
)

llm_tokens_input = Counter(
    "llm_tokens_input_total",
    "Total input tokens",
    ["model", "agent"],
    registry=registry
)

llm_tokens_output = Counter(
    "llm_tokens_output_total",
    "Total output tokens",
    ["model", "agent"],
    registry=registry
)

llm_cache_hits = Counter(
    "llm_cache_read_tokens_total",
    "Total cache hit tokens",
    ["model"],
    registry=registry
)

llm_latency = Histogram(
    "llm_call_latency_seconds",
    "LLM call latency",
    ["model", "agent"],
    registry=registry
)

# Document metrics
document_sections_completed = Gauge(
    "document_sections_completed",
    "Sections completed per document",
    ["doc_id"],
    registry=registry
)

document_cost = Gauge(
    "document_cost_usd",
    "Current document cost",
    ["doc_id"],
    registry=registry
)

# Jury metrics
jury_pass_rate = Gauge(
    "jury_pass_rate",
    "Jury approval rate",
    ["preset"],
    registry=registry
)
```

```python
# File: src/llm/client.py
# Update call method:

from src.observability.metrics import (
    llm_cost_total, llm_tokens_input, llm_tokens_output,
    llm_cache_hits, llm_latency
)

def call(self, model, messages, agent="unknown", preset="balanced", **kwargs):
    start = time.time()
    
    # ... existing call logic ...
    
    # Record metrics
    llm_cost_total.labels(
        model=model,
        agent=agent,
        preset=preset
    ).inc(response["cost_usd"])
    
    llm_tokens_input.labels(model=model, agent=agent).inc(response["tokens_in"])
    llm_tokens_output.labels(model=model, agent=agent).inc(response["tokens_out"])
    llm_cache_hits.labels(model=model).inc(response.get("cache_read_tokens", 0))
    
    latency = time.time() - start
    llm_latency.labels(model=model, agent=agent).observe(latency)
    
    return response
```

```python
# File: src/api/metrics_endpoint.py (NEW)

from fastapi import FastAPI
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from src.observability.metrics import registry

app = FastAPI()

@app.get("/metrics")
def metrics():
    return Response(
        generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9090)
```

**Run Metrics Server:**

```bash
# Terminal 1: Start metrics endpoint
python src/api/metrics_endpoint.py

# Terminal 2: Test metrics
curl http://localhost:9090/metrics

# Expected output:
# llm_cost_usd_total{model="anthropic/claude-opus-4-5",agent="writer",preset="balanced"} 0.52
# llm_tokens_input_total{model="anthropic/claude-opus-4-5",agent="writer"} 12450
# ...
```

**Setup Grafana Dashboard:**

```yaml
# File: docker/grafana/dashboard.json (simplified)
{
  "dashboard": {
    "title": "DRS Metrics",
    "panels": [
      {
        "title": "Cost per Document",
        "targets": [{
          "expr": "sum(llm_cost_usd_total) by (doc_id)"
        }]
      },
      {
        "title": "Cache Hit Rate",
        "targets": [{
          "expr": "rate(llm_cache_read_tokens_total[5m]) / rate(llm_tokens_input_total[5m])"
        }]
      },
      {
        "title": "Latency by Agent",
        "targets": [{
          "expr": "histogram_quantile(0.95, llm_call_latency_seconds)"
        }]
      }
    ]
  }
}
```

**Acceptance Criteria:**
- [ ] Metrics endpoint running on :9090
- [ ] Metrics recorded for LLM calls
- [ ] Grafana dashboard shows real-time data
- [ ] Cost tracking per document visible

---

### Task 2.5: Centralize Configuration

**Priority:** C  
**Effort:** 3-4 hours  

**Create Central Config:**

```yaml
# File: config/system.yaml (NEW)

system:
  version: "1.0.0"
  environment: "development"  # or "production"
  
llm:
  default_temperature: 0.3
  default_max_tokens: 8192
  retry_attempts: 3
  timeout_seconds: 120
  
writer:
  temperature: 0.3
  max_tokens: 8192
  word_count_tolerance: 0.15
  
jury:
  default_size: 1  # economy
  timeout_per_judge: 60
  
budgets:
  economy:
    max_cost_per_section: 0.50
    jury_size: 1
  balanced:
    max_cost_per_section: 2.00
    jury_size: 2
  premium:
    max_cost_per_section: 10.00
    jury_size: 3
    
database:
  url: "${DATABASE_URL:-postgresql://drs:drs_dev_password@localhost:5432/drs}"
  pool_size: 10
  
cache:
  ttl_seconds: 300
  
shine:
  enabled: true
  min_corpus_tokens: 4000
  target_compression: 1200
```

**Load Config:**

```python
# File: src/config/loader.py (NEW)

import yaml
import os
from pathlib import Path
from typing import Any

class Config:
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._load()
        return cls._instance
    
    @classmethod
    def _load(cls):
        config_path = Path("config/system.yaml")
        with open(config_path) as f:
            cls._config = yaml.safe_load(f)
        
        # Environment variable substitution
        cls._substitute_env_vars(cls._config)
    
    @classmethod
    def _substitute_env_vars(cls, obj: Any):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and v.startswith("${"):
                    # Extract ${VAR:-default}
                    var_expr = v[2:-1]
                    if ":-" in var_expr:
                        var, default = var_expr.split(":-")
                        obj[k] = os.getenv(var, default)
                    else:
                        obj[k] = os.getenv(var_expr)
                else:
                    cls._substitute_env_vars(v)
        elif isinstance(obj, list):
            for item in obj:
                cls._substitute_env_vars(item)
    
    def get(self, key: str, default=None):
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

# Singleton instance
config = Config()
```

**Usage:**

```python
# In any module:
from src.config.loader import config

temperature = config.get("writer.temperature", 0.3)
max_cost = config.get("budgets.economy.max_cost_per_section", 0.50)
db_url = config.get("database.url")
```

**Acceptance Criteria:**
- [ ] `config/system.yaml` created
- [ ] Config loader works
- [ ] Environment variables substituted
- [ ] All modules use config instead of hardcoded values

---

## ✅ PHASE 2 DELIVERABLE

**After completing tasks 2.1-2.5:**

```
✅ SHINE compression active (-40% tokens)
✅ Style profiles loaded from config
✅ Knowledge base built and used
✅ Prometheus metrics live
✅ Configuration centralized

STATUS: Optimized Production System
COST: ~$0.80-1.20 per document (economy + optimizations)
TIME: +15-20 hours (total 35-50h)
```

---

## 🎨 PHASE 3: POLISH (Week 3-4) — NICE-TO-HAVE

**Goal:** User-friendly, resilient, fully monitored.

**Effort:** 10-15 hours  
**Optional**

---

### Task 3.1: Human-in-the-Loop UI (Streamlit)

**Priority:** C  
**Effort:** 6-8 hours  

**Implementation:**

```python
# File: src/ui/app.py (NEW)

import streamlit as st
from src.graph.graph import build_graph
from langgraph.checkpoint.postgres import AsyncPostgresSaver

st.title("🔬 Deep Research System")

# Sidebar: Configuration
with st.sidebar:
    st.header("Configuration")
    topic = st.text_input("Topic", "Climate change impacts")
    target_words = st.number_input("Target Words", 5000, 50000, 10000)
    preset = st.selectbox("Quality Preset", ["economy", "balanced", "premium"])
    
    if st.button("Start Generation"):
        st.session_state.doc_id = f"doc_{int(time.time())}"
        st.session_state.running = True

# Main area: Status
if "running" in st.session_state and st.session_state.running:
    st.header("Generation in Progress")
    
    # Progress bar
    progress = st.progress(0)
    status = st.empty()
    
    # Run graph
    graph = build_graph(checkpointer=AsyncPostgresSaver(...))
    
    async def run_with_progress():
        async for event in graph.astream({
            "topic": topic,
            "target_words": target_words,
            "quality_preset": preset,
        }):
            # Update progress
            if "current_section_idx" in event:
                idx = event["current_section_idx"]
                total = len(event.get("outline", []))
                progress.progress(idx / total)
                status.text(f"Section {idx+1}/{total}: {event.get('outline', [])[idx].get('scope', '...')}")
    
    asyncio.run(run_with_progress())
    
    st.success("✅ Generation Complete!")
    st.download_button("Download DOCX", data=..., file_name="output.docx")

# Human review section
if "awaiting_human" in st.session_state:
    st.header("⚠️ Human Review Required")
    st.write(st.session_state.draft)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve"):
            # Resume graph with force_approve
            ...
    with col2:
        feedback = st.text_area("Feedback")
        if st.button("📝 Request Revision"):
            # Resume with feedback
            ...
```

**Run:**

```bash
streamlit run src/ui/app.py
# Opens on http://localhost:8501
```

---

### Task 3.2: Retry Logic with Exponential Backoff

**Priority:** B  
**Effort:** 2 hours  

```python
# File: src/llm/client.py
# Wrap all API calls:

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import anthropic
import openai

class LLMClient:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((
            anthropic.RateLimitError,
            anthropic.APITimeoutError,
            openai.RateLimitError,
            openai.APITimeoutError,
        ))
    )
    def call(self, model, messages, **kwargs):
        # ... existing implementation ...
        pass
```

---

### Task 3.3: CI/CD Pipeline

**Priority:** C  
**Effort:** 4 hours  

```yaml
# File: .github/workflows/ci.yml (NEW)

name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_DB: drs_test
          POSTGRES_USER: drs
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql://drs:test@localhost:5432/drs_test
        run: |
          pytest tests/ -v --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

### Task 3.4: Documentation Update

**Priority:** C  
**Effort:** 2 hours  

Update:
- README.md with quick start
- docs/API.md with endpoints
- docs/DEPLOYMENT.md with production guide
- docs/TROUBLESHOOTING.md with common issues

---

## ✅ PHASE 3 DELIVERABLE

**After completing tasks 3.1-3.4:**

```
✅ Streamlit UI for human review
✅ Retry logic for resilience
✅ CI/CD automated testing
✅ Documentation complete

STATUS: Production-Grade System
COST: ~$0.50-1.00 per document (fully optimized)
TIME: +10-15 hours (total 45-65h)
```

---

## 🎯 SUMMARY ROADMAP

| Phase | Time | Output | Can Ship? |
|-------|------|--------|-----------|
| **Phase 1: Blockers** | 20-30h | MVP Functional | ✅ YES |
| **Phase 2: Optimizations** | +15-20h | Optimized System | ✅ YES (recommended) |
| **Phase 3: Polish** | +10-15h | Production-Grade | ✅ YES (ideal) |

---

## 📊 TRACKING PROGRESS

**Create GitHub Project:**

```bash
# Tasks to track:
- [ ] 1.1 Run test suite & fix bugs (S)
- [ ] 1.2 Integrate routing in Jury (A)
- [ ] 1.3 Setup PostgreSQL schema (A)
- [ ] 1.4 Fix fail-open error handling (A)
- [ ] 1.5 Add missing dependencies (B)
- [ ] 2.1 Complete SHINE integration (A)
- [ ] 2.2 Load style profile rules (B)
- [ ] 2.3 Build knowledge base (B)
- [ ] 2.4 Add Prometheus metrics (B)
- [ ] 2.5 Centralize configuration (C)
- [ ] 3.1 Human-in-the-loop UI (C)
- [ ] 3.2 Retry logic (B)
- [ ] 3.3 CI/CD pipeline (C)
- [ ] 3.4 Documentation update (C)
```

**Daily Standup Template:**

```
## Day X Progress

### Completed:
- Task X.Y: [description] ✅

### In Progress:
- Task X.Z: [description] [60% done]

### Blocked:
- Task X.W: Waiting on [dependency]

### Next:
- Task X.A
- Task X.B

### Metrics:
- Tests passing: X/Y
- Cost per doc: $X.XX
- Coverage: XX%
```

---

## 🚀 GETTING STARTED

**Today (Day 1):**

```bash
# 1. Pull latest
git pull origin struct

# 2. Create feature branch
git checkout -b feature/completion-phase1

# 3. Start with Task 1.1
pytest tests/ -v --tb=short

# 4. Fix first bug, commit
git commit -m "fix: resolve import error in graph.py"

# 5. Repeat until all tests pass
```

**This Week (Days 1-5):**
- Complete Phase 1 (tasks 1.1-1.5)
- Ship MVP to staging
- Validate end-to-end

**Next Week (Days 6-10):**
- Complete Phase 2 (tasks 2.1-2.5)
- Measure cost reduction
- Ship to production

**Optional (Days 11-15):**
- Complete Phase 3 (tasks 3.1-3.4)
- Polish UX
- Full production deployment

---

## 📞 SUPPORT

**If stuck:**
1. Check logs: `tail -f logs/drs.log`
2. Review metrics: `curl localhost:9090/metrics`
3. Check database: `docker exec -it postgres psql -U drs -d drs`
4. Ask for help with specific error message

**Common Issues:**
- Import errors → Task 1.5 (dependencies)
- Test failures → Task 1.1 (fix bugs)
- High costs → Task 1.2 (jury routing)
- Database errors → Task 1.3 (schema)

---

**Last Updated:** 2026-02-24  
**Status:** Ready for Implementation  
**Est. Completion:** 1-4 weeks depending on phase selection
