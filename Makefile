.PHONY: help install test lint format clean dev worker migrate docker-build docker-up

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies using uv
	uv sync

test: ## Run all tests
	uv run pytest -v

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -v

test-integration: ## Run integration tests only
	uv run pytest tests/integration/ -v

test-e2e: ## Run end-to-end tests only
	uv run pytest tests/e2e/ -v

test-coverage: ## Run tests with coverage report
	uv run pytest --cov=app --cov-report=html --cov-report=term

lint: ## Run code linting
	uv run ruff check app/ tests/
	uv run mypy app/

format: ## Format code
	uv run ruff format app/ tests/
	uv run ruff check --fix app/ tests/

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/

dev: ## Start development server
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Start ARQ worker
	uv run python worker.py

migrate: ## Run database migrations
	uv run alembic upgrade head

migrate-create: ## Create new migration (use: make migrate-create MESSAGE="description")
	uv run alembic revision --autogenerate -m "$(MESSAGE)"

# Docker commands
docker-build: ## Build Docker image
	docker build -t presto-deck:latest .

docker-up: ## Start services with docker-compose
	docker-compose up -d

docker-down: ## Stop docker-compose services
	docker-compose down

docker-logs: ## View docker-compose logs
	docker-compose logs -f

# Development database commands
db-setup: ## Setup local development database
	createdb presto_deck || true
	make migrate

db-reset: ## Reset development database
	dropdb presto_deck || true
	createdb presto_deck
	make migrate

db-seed: ## Seed database with test data
	uv run python -c "from scripts.seed_db import main; main()"

# Production commands
deploy: ## Deploy to production (placeholder)
	@echo "Production deployment not configured"

health: ## Check service health
	curl -f http://localhost:8000/health || exit 1

# Monitoring and debugging
logs: ## Show application logs
	tail -f logs/app.log

redis-cli: ## Connect to Redis CLI
	redis-cli

psql: ## Connect to PostgreSQL
	psql presto_deck

# Code quality
security-check: ## Run security checks
	uv run bandit -r app/

complexity-check: ## Check code complexity
	uv run radon cc app/ --min B

outdated: ## Check for outdated dependencies
	uv tree --outdated

ping-redis:
	uv run python -c "import redis; r = redis.Redis(host='localhost', port=6379); print(r.ping())"

pre-commit:
	uv run pre-commit run --all-files
