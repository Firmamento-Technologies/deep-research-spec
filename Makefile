.PHONY: dev stop test lint run migrate clean help

# ── DRS Developer Makefile ───────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Infrastructure ───────────────────────────────────────────────────────────

dev: ## Start Docker services (PostgreSQL, Redis, MinIO)
	docker compose up -d
	@echo "Waiting for services..."
	@sleep 3
	@docker compose ps

stop: ## Stop Docker services
	docker compose down

clean: ## Stop services and remove volumes
	docker compose down -v
	@echo "Volumes removed"

# ── Database ─────────────────────────────────────────────────────────────────

migrate: ## Run Alembic migrations
	alembic upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new MSG="add_table")
	alembic revision --autogenerate -m "$(MSG)"

# ── Testing ──────────────────────────────────────────────────────────────────

test: ## Run all tests
	python -m pytest tests/ -v --tb=short

test-fast: ## Run tests (skip slow)
	python -m pytest tests/ -v --tb=short -m "not slow"

test-cov: ## Run tests with coverage
	python -m pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

# ── Linting ──────────────────────────────────────────────────────────────────

lint: ## Run ruff linter
	ruff check src/ tests/

lint-fix: ## Auto-fix lint issues
	ruff check src/ tests/ --fix

typecheck: ## Run mypy type checking
	mypy src/ --ignore-missing-imports

# ── Run Pipeline ─────────────────────────────────────────────────────────────

run: ## Run DRS pipeline (usage: make run TOPIC="Machine Learning")
	python -m src.main --topic "$(TOPIC)" --preset balanced --log-format text

run-economy: ## Run with economy preset
	python -m src.main --topic "$(TOPIC)" --preset economy --log-format text

run-premium: ## Run with premium preset
	python -m src.main --topic "$(TOPIC)" --preset premium --log-format text

# ── Utilities ────────────────────────────────────────────────────────────────

graph-viz: ## Export graph visualization (requires graphviz)
	python -c "from src.graph.graph import build_graph; g = build_graph(); print(g.get_graph().draw_mermaid())" > graph.mmd
	@echo "Graph exported to graph.mmd"
