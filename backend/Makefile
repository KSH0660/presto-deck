# Simple Makefile for Presto Deck POC

.PHONY: help setup dev test clean

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

test: ## Run basic tests
	uv run pytest -v

clean: ## Clean up cache and temp files
	rm -rf .pytest_cache/ __pycache__/ htmlcov/ .coverage
	rm -f test_*.db *.log
	find . -name "*.pyc" -delete

# Database helpers
db-init: ## Initialize database
	uv run python -c "from app.infra.config.database import create_tables; import asyncio; asyncio.run(create_tables())"

# Code quality
lint: ## Check code quality
	uv run ruff check .
	uv run black --check .

format: ## Format code
	uv run black .
	uv run ruff --fix .
