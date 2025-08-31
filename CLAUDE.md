# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- Use `uv` for package management: `uv add "package"` or `uv pip install`
- Start dev server: `uv run uvicorn app.main:app --reload`
- Alternative Streamlit UI: `uv run streamlit run app.py`

### Testing and Quality
- Run tests: `uv run pytest` or `PYTHONPATH=. uv run pytest tests`
- Run pre-commit checks: `uv run pre-commit run --all-files`
- Target: 90%+ test coverage with pytest

### Project Structure
- FastAPI backend server in `app/main.py`
- Legacy Streamlit UI in `app.py` (for reference)
- Test coverage goal: Pass `uv run pytest` with 90%+ coverage

## Architecture Overview

### Modular Pipeline Architecture
The application follows a **3-stage pipeline**:
1. **Planning**: Generate deck structure from user prompt (`app/core/planning/`)
2. **Selection**: Choose optimal layouts for each slide (`app/core/selection/`)
3. **Rendering**: Generate HTML content for slides (`app/core/rendering/`)

### Domain-Driven Design Migration
The codebase is migrating to clean architecture with:
- **Domain models**: Core business logic in `app/domain/`
- **Services**: Use case orchestration in `app/services/`
- **Ports**: Abstract interfaces in `app/ports/`
- **Adapters**: External integrations in `app/adapters/`
- **DTOs**: API-specific models in `app/api/v1/dto/`

### Key Components

#### Storage Layer
- **Dual storage**: Redis (when `USE_REDIS=true`) or in-memory fallback
- **Repositories**: Abstract deck storage via `DeckRepository` interface
- **Template Manager**: HTML template catalog management

#### API Structure
- **Modular endpoints**: Separate concerns (planning, rendering, deck management)
- **Streaming responses**: SSE for real-time progress updates
- **Quality tiers**: DRAFT/DEFAULT/PREMIUM with different models and concurrency

#### Infrastructure
- **Metrics**: Prometheus metrics at `/metrics` (toggleable via `ENABLE_METRICS`)
- **Event Bus**: Internal pub/sub for UI state synchronization
- **Logging**: Structured logging with rotation and configurable levels
- **Concurrency**: Bounded parallelism with semaphores for LLM calls

### Configuration
Environment settings in `app/core/infra/config.py`:
- LLM models per tier (configurable via env vars)
- Concurrency limits and operational toggles
- Redis connection settings
- Logging and metrics configuration

### System Design Guidelines
Follow principles in `what_is_good_system.md`:
- Single-purpose endpoints with typed inputs/outputs
- Observability with metrics for LLM usage (tokens, latency)
- Graceful fallbacks for optional dependencies
- Fast tests with mocks, avoid network calls in CI
- Bounded concurrency and timeouts for safety

### Legacy vs Modern Structure
- **Legacy**: Streamlit app (`app.py`) with direct pipeline calls
- **Modern**: FastAPI with domain separation, event streaming, and clean architecture patterns
- Focus development on the FastAPI app structure under `app/`
