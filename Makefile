.PHONY: help dev stop restart logs clean build up down ps stats
.PHONY: test test-unit test-integration test-e2e test-cov
.PHONY: lint lint-fix typecheck
.PHONY: migrate migrate-new migrate-rollback db-backup db-restore seed-db
.PHONY: deploy-dev deploy-staging deploy-prod health-check rollback
.PHONY: ci-build ci-test ci-lint ci-deploy
.PHONY: logs-backend logs-frontend logs-postgres logs-redis
.PHONY: prune reset graph-viz

# =============================================================================
# DRS Makefile — Deployment & Development
# =============================================================================

# ── Colors ───────────────────────────────────────────────────────────────────
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

# ── Configuration ────────────────────────────────────────────────────────────
ENV ?= development
TAIL ?= 50
VERSION ?= latest

help: ## Show this help
	@echo "$(CYAN)DRS Makefile — Available targets:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'


# =============================================================================
# Docker — Build & Run
# =============================================================================

build: ## Build all Docker images
	@echo "$(CYAN)Building Docker images...$(RESET)"
	export DOCKER_BUILDKIT=1 && docker-compose build --parallel

up: ## Start all services (detached)
	@echo "$(CYAN)Starting DRS stack...$(RESET)"
	docker-compose up -d
	@echo "$(GREEN)Services started. Run 'make ps' to check status.$(RESET)"

dev: up ## Alias for 'up' (development mode)

down: ## Stop all services
	@echo "$(CYAN)Stopping DRS stack...$(RESET)"
	docker-compose down

restart: down up ## Restart all services

ps: ## Show running containers
	docker-compose ps

stats: ## Show Docker resource stats
	docker stats --no-stream

logs: ## Tail logs (all services, use TAIL=N to limit)
	docker-compose logs --tail=$(TAIL) -f

logs-backend: ## Tail backend logs
	docker-compose logs --tail=$(TAIL) -f backend

logs-frontend: ## Tail frontend logs
	docker-compose logs --tail=$(TAIL) -f frontend

logs-postgres: ## Tail PostgreSQL logs
	docker-compose logs --tail=$(TAIL) -f postgres

logs-redis: ## Tail Redis logs
	docker-compose logs --tail=$(TAIL) -f redis

clean: ## Stop services and remove volumes
	@echo "$(YELLOW)Stopping services and removing volumes...$(RESET)"
	docker-compose down -v
	@echo "$(GREEN)Clean complete.$(RESET)"

prune: ## Remove unused Docker images and volumes
	@echo "$(YELLOW)Pruning Docker system...$(RESET)"
	docker system prune -af --volumes
	@echo "$(GREEN)Prune complete.$(RESET)"

reset: clean build up ## Full reset: clean, rebuild, start


# =============================================================================
# Database
# =============================================================================

migrate: ## Run Alembic migrations (upgrade to head)
	@echo "$(CYAN)Running database migrations...$(RESET)"
	docker-compose exec backend alembic upgrade head
	@echo "$(GREEN)Migrations complete.$(RESET)"

migrate-new: ## Create new migration (usage: make migrate-new MSG="add_table")
	@echo "$(CYAN)Creating migration: $(MSG)$(RESET)"
	docker-compose exec backend alembic revision --autogenerate -m "$(MSG)"

migrate-rollback: ## Rollback N migrations (usage: make migrate-rollback N=1)
	@echo "$(YELLOW)Rolling back $(N) migration(s)...$(RESET)"
	docker-compose exec backend alembic downgrade -$(N)

db-backup: ## Backup database to backups/
	@echo "$(CYAN)Creating database backup...$(RESET)"
	@mkdir -p backups
	@bash scripts/backup.sh
	@echo "$(GREEN)Backup complete.$(RESET)"

db-restore: ## Restore database (usage: make db-restore FILE=backups/xxx.sql.gz)
	@echo "$(YELLOW)Restoring database from $(FILE)...$(RESET)"
	@bash scripts/restore.sh $(FILE)
	@echo "$(GREEN)Restore complete.$(RESET)"

seed-db: ## Seed database with sample data
	@echo "$(CYAN)Seeding database...$(RESET)"
	@bash scripts/seed-db.sh
	@echo "$(GREEN)Seed complete.$(RESET)"


# =============================================================================
# Testing
# =============================================================================

test: test-all ## Alias for test-all

test-all: ## Run all tests (unit + integration + e2e)
	@echo "$(CYAN)Running all tests...$(RESET)"
	cd backend && pytest tests/ -v

test-unit: ## Run unit tests only
	@echo "$(CYAN)Running unit tests...$(RESET)"
	cd backend && pytest tests/unit/ -v -m unit

test-integration: ## Run integration tests
	@echo "$(CYAN)Running integration tests...$(RESET)"
	cd backend && pytest tests/integration/ -v -m integration

test-e2e: ## Run end-to-end tests
	@echo "$(CYAN)Running E2E tests...$(RESET)"
	cd backend && pytest tests/e2e/ -v -m e2e

test-cov: ## Run tests with coverage report
	@echo "$(CYAN)Running tests with coverage...$(RESET)"
	cd backend && pytest tests/ -v --cov --cov-report=html
	@echo "$(GREEN)Coverage report: backend/htmlcov/index.html$(RESET)"


# =============================================================================
# Linting & Type Checking
# =============================================================================

lint: ## Run ruff linter
	@echo "$(CYAN)Running linter...$(RESET)"
	cd backend && ruff check src/ api/ services/ tests/

lint-fix: ## Auto-fix lint issues
	@echo "$(CYAN)Fixing lint issues...$(RESET)"
	cd backend && ruff check src/ api/ services/ tests/ --fix

typecheck: ## Run mypy type checking
	@echo "$(CYAN)Running type checker...$(RESET)"
	cd backend && mypy src/ api/ services/ --ignore-missing-imports


# =============================================================================
# Deployment
# =============================================================================

deploy-dev: ## Deploy to development
	@echo "$(CYAN)Deploying to development...$(RESET)"
	@ENV=development bash scripts/deploy.sh

deploy-staging: ## Deploy to staging
	@echo "$(CYAN)Deploying to staging...$(RESET)"
	@ENV=staging bash scripts/deploy.sh

deploy-prod: ## Deploy to production
	@echo "$(YELLOW)Deploying to production...$(RESET)"
	@ENV=production bash scripts/deploy.sh

health-check: ## Verify all services are healthy
	@echo "$(CYAN)Running health checks...$(RESET)"
	@bash scripts/health-check.sh

rollback: ## Rollback to previous version (usage: make rollback VERSION=v1.2.2)
	@echo "$(YELLOW)Rolling back to $(VERSION)...$(RESET)"
	@bash scripts/rollback.sh $(VERSION)


# =============================================================================
# CI/CD
# =============================================================================

ci-build: build ## CI: Build images

ci-test: test-all ## CI: Run all tests

ci-lint: lint typecheck ## CI: Lint + type check

ci-deploy: ## CI: Deploy (usage: make ci-deploy ENV=staging)
	@echo "$(CYAN)CI deploying to $(ENV)...$(RESET)"
	@bash scripts/deploy.sh


# =============================================================================
# Utilities
# =============================================================================

graph-viz: ## Export LangGraph visualization to graph.mmd
	@echo "$(CYAN)Generating graph visualization...$(RESET)"
	python -c "from src.graph.graph import build_graph; g = build_graph(); print(g.get_graph().draw_mermaid())" > graph.mmd
	@echo "$(GREEN)Graph exported to graph.mmd$(RESET)"
