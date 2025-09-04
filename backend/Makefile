# Simple Makefile for Presto Deck POC

.PHONY: help setup dev test clean db-init db-reset db-shell db-status worker worker-status redis-shell

help: ## Show available commands
	@echo "Presto Deck POC Commands"
	@echo "========================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Install dependencies and setup environment
	uv sync
	@echo "✅ Dependencies installed!"
	@echo "📝 Copy .env.example to .env and configure your settings"
	@echo "🔑 Set your OPENAI_API_KEY or OPENAI_BASE_URL for custom LLM servers"

dev: ## Start development server
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Start ARQ background worker
	PYTHONPATH=. uv run arq app.worker.WorkerSettings --verbose

worker-status: ## Show worker queue status
	@echo "🔍 ARQ Worker Queue Status:"
	@redis-cli -h localhost -p 6379 -n 0 llen arq:queue || echo "❌ Redis connection failed"
	@echo "📊 Job Keys:"
	@redis-cli -h localhost -p 6379 -n 0 keys "arq:*" || echo "❌ No jobs found"

redis-shell: ## Connect to Redis CLI
	redis-cli -h localhost -p 6379 -n 0

test: ## Run basic tests
	uv run pytest -v

clean: ## Clean up cache and temp files
	rm -rf .pytest_cache/ __pycache__/ htmlcov/ .coverage
	rm -f test_*.db *.log
	find . -name "*.pyc" -delete

# Database helpers
db-init: ## Initialize database tables
	PYTHONPATH=. uv run python -c "from app.infra.config.database import create_tables; import asyncio; asyncio.run(create_tables())"

db-reset: ## Reset database (drop + recreate + init)
	@psql -h localhost -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'presto_deck' AND pid <> pg_backend_pid();" || true
	@dropdb -h localhost -U postgres presto_deck || true
	@createdb -h localhost -U postgres presto_deck
	@$(MAKE) db-init

db-shell: ## Open database shell
	psql -h localhost -U postgres -d presto_deck

db-status: ## Show database tables
	psql -h localhost -U postgres -d presto_deck -c "\d"

# Code quality
lint: ## Check code quality
	uv run ruff check .
	uv run black --check .

format: ## Format code
	uv run black .
	uv run ruff --fix .
