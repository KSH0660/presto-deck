# Makefile for Presto Deck testing and development

# Default Python and pytest commands
PYTHON := uv run python
PYTEST := uv run pytest

# Test categories
.PHONY: help test test-unit test-integration test-e2e test-external test-llm test-cache test-all
.PHONY: test-fast test-slow test-coverage test-watch
.PHONY: dev setup clean lint format check

help: ## Show this help message
	@echo "Presto Deck Testing Commands"
	@echo "============================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Test execution commands
test: test-unit ## Run unit tests (default)

test-unit: ## Run unit tests only (fast, isolated)
	$(PYTEST) -m "unit" -v

test-integration: ## Run integration tests (with external dependencies)
	$(PYTEST) -m "integration" -v --tb=short

test-e2e: ## Run end-to-end tests (full application flow)
	$(PYTEST) -m "e2e" -v --tb=short -s

test-external: ## Run tests requiring external services (Redis, LLM API)
	$(PYTEST) -m "external" -v --tb=short

test-llm: ## Run tests that make real LLM API calls (requires API key)
	$(PYTEST) -m "llm" -v --tb=short -s

test-cache: ## Run LLM caching related tests
	$(PYTEST) -m "cache" -v

test-all: ## Run all tests
	$(PYTEST) -v

test-fast: ## Run only fast tests (unit + cache)
	$(PYTEST) -m "unit or cache" -v

test-slow: ## Run slow tests (integration + e2e + external)
	$(PYTEST) -m "slow" -v --tb=short -s

# Test coverage
test-coverage: ## Run tests with coverage report
	$(PYTEST) --cov=app --cov-report=html --cov-report=term-missing --cov-branch

test-coverage-unit: ## Run unit tests with coverage
	$(PYTEST) -m "unit" --cov=app --cov-report=html --cov-report=term-missing

# Interactive testing
test-watch: ## Watch for changes and re-run tests
	$(PYTEST) -f -m "unit"

test-debug: ## Run tests with debugging enabled
	$(PYTEST) -v -s --pdb

# Specific test files
test-llm-integration: ## Run LLM integration tests specifically
	$(PYTEST) tests/integration/test_llm_integration.py -v

test-db-integration: ## Run database integration tests specifically
	$(PYTEST) tests/integration/test_database_integration.py -v

test-redis-integration: ## Run Redis integration tests specifically
	$(PYTEST) tests/integration/test_redis_integration.py -v

test-system-integration: ## Run system integration tests specifically
	$(PYTEST) tests/integration/test_system_integration.py -v

test-deck-e2e: ## Run deck generation E2E tests specifically
	$(PYTEST) tests/e2e/test_deck_generation_e2e.py -v -s

# Environment-specific testing
test-with-real-llm: ## Run tests with real LLM API (set OPENAI_API_KEY)
	@echo "Running tests with real LLM API..."
	@echo "Make sure OPENAI_API_KEY is set in environment"
	$(PYTEST) -m "llm" --tb=short -v -s

test-with-redis: ## Run tests requiring Redis (ensure Redis is running)
	@echo "Running tests with Redis..."
	@echo "Make sure Redis is running on localhost:6379"
	$(PYTEST) -m "external" --tb=short -v

test-full-system: ## Run comprehensive system tests (requires all external services)
	@echo "Running full system tests..."
	@echo "Requirements: Redis running, OPENAI_API_KEY set"
	$(PYTEST) -m "integration or e2e" --tb=short -v -s

# Development helpers
setup: ## Install dependencies and setup development environment
	uv sync
	pre-commit install

dev: ## Start development server
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

clean: ## Clean up test artifacts and cache files
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -f test_presto_deck.db
	rm -f test_llm_cache.db
	rm -rf __pycache__/
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete

# Code quality
lint: ## Run linting checks
	uv run ruff check .
	uv run black --check .

format: ## Format code
	uv run black .
	uv run ruff --fix .

check: lint ## Run all code quality checks

# Test reporting and CI
test-ci: ## Run tests suitable for CI environment
	$(PYTEST) -m "unit or (integration and not external)" --tb=short --strict-markers

test-ci-external: ## Run external tests in CI (requires services)
	$(PYTEST) -m "external" --tb=short --strict-markers

# Cache management
cache-clear: ## Clear LLM cache
	$(PYTHON) -c "from app.infra.llm.cache_manager import clear_llm_cache; clear_llm_cache()"

cache-stats: ## Show LLM cache statistics
	$(PYTHON) -c "from app.infra.llm.cache_utils import inspect_cache; import json; print(json.dumps(inspect_cache(), indent=2))"

# Database management
db-create: ## Create database tables
	$(PYTHON) -c "from app.infra.config.database import create_tables; import asyncio; asyncio.run(create_tables())"

db-reset: ## Reset test database
	rm -f test_presto_deck.db
	$(MAKE) db-create

# Redis management
redis-flush: ## Flush Redis test database
	redis-cli -n 1 FLUSHDB

# Documentation
test-examples: ## Show test execution examples
	@echo "Test Execution Examples:"
	@echo "======================="
	@echo ""
	@echo "# Run only unit tests (fast):"
	@echo "make test-unit"
	@echo ""
	@echo "# Run integration tests with caching:"
	@echo "make test-cache"
	@echo ""
	@echo "# Run E2E tests with real LLM (requires API key):"
	@echo "OPENAI_API_KEY=your-key make test-llm"
	@echo ""
	@echo "# Run specific test file:"
	@echo "make test-llm-integration"
	@echo ""
	@echo "# Run tests with coverage:"
	@echo "make test-coverage"
	@echo ""
	@echo "# Clean up and run fresh tests:"
	@echo "make clean && make test-all"
