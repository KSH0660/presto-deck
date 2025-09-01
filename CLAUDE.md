# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Presto-Deck is an AI-powered presentation deck generation service using event-driven architecture. The service takes user prompts and generates high-quality presentation decks with real-time streaming updates.

## Architecture Overview

**Key Components:**
- **API Server (FastAPI)**: Handles HTTP/WebSocket requests, delegates heavy work to workers
- **Worker (ARQ + Python)**: Background processing for LLM calls and slide generation (idempotent operations)
- **PostgreSQL**: Single source of truth for all persistent data (Deck, Slide, User info, Events)
- **Redis**: Message broker (ARQ queues), event bus (Redis Streams), broadcast (Pub/Sub), caching

**Data Flow:**
1. Client creates deck → API stores in PostgreSQL → ARQ job queued
2. Worker processes job → Updates database → Publishes events to Redis Streams
3. API listens to Redis Streams → Broadcasts to WebSocket clients via Redis Pub/Sub

## Technology Stack

- **Python 3.13+** with **uv** for dependency management
- **FastAPI** with **Pydantic V2**
- **PostgreSQL 15+** with **SQLAlchemy 2.0** and **Alembic** migrations
- **Redis** for messaging and caching
- **ARQ** for async task queues
- **LangChain** for LLM integration
- **JWT** authentication with **python-jose**
- **pytest** with **pytest-asyncio** for testing

## Development Commands

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Run tests
uv run pytest

# Run single test
uv run pytest tests/test_specific.py::test_function_name

# Database migrations (when implemented)
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"

# Start API server (when implemented)
uv run uvicorn app.main:app --reload

# Start worker (when implemented)
uv run arq app.worker.WorkerSettings
```

## Project Structure (Hexagonal Architecture)

```
backend/
├── app/
│   ├── api/                # FastAPI routes and HTTP schemas
│   ├── application/        # Business logic and use cases
│   ├── domain/             # Core entities (Deck, Slide) and business rules
│   ├── infrastructure/     # External adapters (DB, LLM, Redis)
│   │   ├── db/             # PostgreSQL repositories
│   │   ├── llm/            # LangChain implementations
│   │   └── messaging/      # Redis messaging
│   └── core/               # Configuration and dependency injection
├── tests/
└── main.py
```

## Database Schema

**Core Tables:**
- `decks`: Main deck entity with status (PENDING/PLANNING/GENERATING/COMPLETED/FAILED/CANCELLED)
- `slides`: Individual slides with order, HTML content, presenter notes
- `deck_events`: Event sourcing for audit and replay capabilities

## Event-Driven Architecture

**Event Types:**
- `DeckStarted`, `PlanUpdated`, `SlideAdded`, `SlideUpdated`
- `DeckCompleted`, `DeckFailed`, `DeckCancelled`, `Heartbeat`

**WebSocket Event Replay:**
- Clients can reconnect with `last_version` parameter to replay missed events
- Events stored in both `deck_events` table and Redis Streams

## Security Requirements

- All endpoints require JWT authentication
- User ownership validation for deck access
- HTML content sanitization with `bleach` library for XSS prevention

## Key Implementation Patterns

**Idempotency**: All worker operations must be idempotent with proper state checking
**Error Handling**: Exponential backoff for LLM/external API failures
**Observability**: OpenTelemetry tracing with `deck_id` correlation, Prometheus metrics
**Concurrency**: Independent scaling of API servers and workers

## Testing Strategy

- **Unit Tests**: Mock LLM and database for service layer testing
- **Integration Tests**: Real PostgreSQL/Redis for full workflow testing
- **E2E Tests**: Complete client-to-worker scenarios including WebSocket event replay
- **Load Tests**: Use `Locust` or `k6` for concurrent WebSocket and deck creation testing
