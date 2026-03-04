# Graph Nodes

Core LangGraph node implementations for the DRS research pipeline.

## Node Execution Flow

```
START
  ↓
[Planner] → Generates 4-12 section outline
  ↓ (HITL approval)
  ↓
FOR EACH SECTION:
  |
  ├─ [Researcher] → Gathers web + RAG sources
  |
  ├─ [Writer] → Generates Markdown content
  |    ↓ (HITL approval)
  |
  └─ [Critic] → Evaluates quality
       ├─ APPROVE → Next section
       └─ REWRITE → Back to Writer
  ↓
[Finalizer] → Assembles complete document
  ↓
END
```

## Nodes

### 1. Planner Node
**File:** `planner_node.py`
**Model:** o1-mini
**Purpose:** Generate structured document outline

**Input:**
- state["topic"]
- state["target_words"]
- state["quality_preset"]

**Output:**
- state["outline"] (list of Section objects)
- state["sections"] (initial empty content)
- state["total_sections"]

**Key Logic:**
1. Call LLM with planner_system.txt prompt
2. Parse JSON outline
3. Validate 4-12 sections
4. Auto-adjust word counts to match target
5. Wait for HITL approval (stub)

**Events:**
- NODE_STARTED
- HUMAN_REQUIRED (outline_approval)
- NODE_COMPLETED

---

### 2. Researcher Node
**File:** `researcher_node.py`
**Model:** gpt-4o-mini (for query generation)
**Purpose:** Gather relevant sources for section

**Input:**
- state["sections"][current_section]
- state["knowledge_space_id"] (optional)

**Output:**
- sections[i].search_results (list of SearchResult)

**Key Logic:**
1. Generate 3-5 search queries from section title/scope
2. Execute web search (Perplexity/Tavily)
3. Execute RAG search (if space_id present)
4. Merge and deduplicate (by URL/chunk_id)
5. Rank: RAG high-sim > RAG low-sim > web
6. Return max 20 results

**Events:**
- NODE_STARTED
- RESEARCHER_PROGRESS (web_search, rag_search)
- NODE_COMPLETED

---

### 3. Writer Node
**File:** `writer_node.py`
**Model:** claude-opus-4-5
**Purpose:** Generate section content from sources

**Input:**
- sections[current_section] (with search_results)
- state["style_profile"]

**Output:**
- sections[i].content (Markdown string)
- sections[i].word_count
- sections[i].cost_usd

**Key Logic:**
1. Format sources as numbered citations
2. Build context-rich prompt
3. Call LLM to generate Markdown
4. Validate word count (±15% of target)
5. Wait for HITL approval (stub)

**Events:**
- NODE_STARTED
- SECTION_DRAFTED
- HUMAN_REQUIRED (section_approval)
- NODE_COMPLETED

---

### 4. Critic Node
**File:** `critic_node.py`
**Model:** o1-mini
**Purpose:** Evaluate content quality and decide approve/rewrite

**Input:**
- sections[current_section].content
- state["quality_preset"]

**Output:**
- sections[i].feedback (JSON dict)
- sections[i].final_score (0-10)
- sections[i].iterations (incremented on rewrite)
- state["rewrite_required"] (bool flag)

**Key Logic:**
1. Call LLM with critic_system.txt rubric
2. Parse structured JSON feedback
3. Check score vs. threshold (6.0/7.0/8.0)
4. If score >= threshold: APPROVE
5. If score < threshold: REWRITE (return to Writer)
6. Force-approve after max iterations

**Events:**
- NODE_STARTED
- CRITIC_FEEDBACK (score, issues, suggestions)
- REWRITE_REQUIRED (if rewrite needed)
- NODE_COMPLETED

---

## Implementation Notes

### LLM Integration
All nodes use `src.llm.client.get_llm_client()` for:
- Automatic model resolution via settings.model_assignments
- Budget tracking and hard stop
- Token counting and cost calculation
- Exponential backoff retry

### Budget Tracking
Every LLM call updates `state["budget_spent"]` and `state["budget_remaining_pct"]`. When budget is exhausted, `BudgetExceededError` is raised.

### SSE Events
Nodes emit events via `state["broker"].emit()` for real-time frontend updates.

### HITL Stubs
MVP uses `await asyncio.sleep(1.0)` to simulate user approval. Replace with LangGraph interrupt API for production.

### Error Handling
- `LLMError`: Raised after 3 retry attempts
- `ValueError`: Invalid JSON, validation failures
- `BudgetExceededError`: Budget hard stop

---

## Testing

Run integration tests:
```bash
cd backend
pytest tests/test_full_pipeline.py -v
```

Test individual node:
```python
import asyncio
from src.graph.nodes import planner_node
from src.models.state import build_initial_state

state = build_initial_state(
    doc_id="test",
    topic="AI Ethics",
    target_words=2000,
)

result = asyncio.run(planner_node(state))
print(f"Generated {len(result['sections'])} sections")
```

---

## Next Steps

1. **HITL Implementation:** Replace stubs with LangGraph interrupt
2. **RAG Integration:** Implement semantic_search.py
3. **Prompt Refinement:** Tune prompts for better quality
4. **Streaming:** Add token streaming for real-time content
5. **Caching:** Cache LLM responses for identical prompts
