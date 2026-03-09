# 🔬 Deep Research System (DRS)

> AI-powered long-form document generation with multi-agent quality assurance.

## Features

- **41-node LangGraph pipeline** — outline → research → write → jury → refine → publish
- **9-judge jury system** (3 Reasoning + 3 Factual + 3 Style) with CSS quality scoring
- **Dynamic model routing** — economy/balanced/premium presets for cost control
- **Prompt caching** — 90% cache-hit reduction on iterative drafts
- **Prometheus observability** — 12 metrics, Grafana dashboard
- **PostgreSQL checkpointing** — resume from any section
- **DOCX + Markdown output** — formatted, sourced, publication-ready

## Quick Start

```bash
# 1. Clone & setup
git clone https://github.com/lucadidomenicodopehubs/deep-research-spec.git
cd deep-research-spec
git checkout <your-branch>

# 2. Install dependencies
python3.11 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)

# 4. Start services
docker-compose up -d postgres

# 5. Smoke test
python -c "import sys; sys.path.insert(0,'backend'); import main; print('✓ Backend import ok')"

# 6. Run tests
python3 -m pytest tests/unit/test_budget_estimator_v2.py -q
```

## Architecture

```
┌─────────────────────────────────────────────┐
│               LangGraph Pipeline             │
│  Outliner → Researcher → Writer → Jury →     │
│  Reflector → Checkpoint → Publisher          │
├─────────┬───────────┬──────────┬────────────┤
│ LLM     │ Routing   │ RAG      │ Observ.    │
│ Client  │ (presets) │ (memvid) │ (Prom.)    │
├─────────┴───────────┴──────────┴────────────┤
│            PostgreSQL + Redis                │
└─────────────────────────────────────────────┘
```

## Configuration

Central config: `config/system.yaml`

```python
from src.config.loader import config

temperature = config.get("writer.temperature", 0.3)
preset_cost = config.get("budgets.economy.max_cost_per_section", 0.50)
```

## Quality Presets

| Preset | Jury Size | Cost/Section | Models |
|--------|-----------|-------------|--------|
| economy | 1 | ~$0.03 | Flash/tier1 |
| balanced | 2 | ~$0.40 | Mixed tiers |
| premium | 3 | ~$3.96 | o3/Pro/tier3 |

## API Server

```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000
# Docs: http://localhost:8000/docs

# Endpoints:
# POST /api/runs           — Start pipeline
# GET  /api/runs/{id}      — Check status
# GET  /api/runs           — List runs
# GET  /health             — Health check
# GET  :9090/metrics       — Prometheus metrics
```

## Style Profiles

Five built-in profiles in `config/style_profiles.yaml`:
- **academic** — formal, cited, passive voice
- **business** — executive summary, bullet points, ROI
- **technical** — code examples, step-by-step, prerequisites
- **journalistic** — inverted pyramid, quotes, short paragraphs
- **narrative** — storytelling, anecdotes, varied rhythm

## Testing

```bash
# Full suite
python3 -m pytest tests/unit/test_budget_estimator_v2.py -q

# With coverage
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Current: 156+ tests, 0 failures
```

## Docker

```bash
# Start all services
docker-compose up -d

# Services: PostgreSQL, Redis, MinIO, Prometheus, Grafana
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

## Project Structure

```
src/
├── api/           # FastAPI server
├── config/        # Schema + loader
├── graph/         # LangGraph pipeline
│   └── nodes/     # 41 nodes (writer, jury, researcher, etc.)
├── llm/           # Client, routing, resilience
├── observability/ # Prometheus metrics
├── connectors/    # Memvid, RAG
├── security/      # Injection guard
└── budget/        # Cost monitor + hard stops

config/
├── model_routing.yaml    # Model assignments per preset
├── style_profiles.yaml   # Writer style rules
└── system.yaml           # Central configuration

tests/              # 156+ tests
docker/init.sql     # PostgreSQL schema
```

## License

See LICENSE file.
