"""
Pytest configuration and fixtures.
"""

import os
import pytest
import sys
import asyncio
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

# Add the backend directory to Python path so imports work
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Import after path setup
try:
    from app.api.schemas import DeckStatus
    from app.domain_core.value_objects.template_type import TemplateType
except ImportError as e:
    # This will help debug import issues
    print(f"Import error: {e}")
    print(f"Python path: {sys.path}")
    print(f"Backend dir: {backend_dir}")
    raise


@pytest.fixture
def sample_deck_data():
    """Sample deck data for testing."""
    return {
        "prompt": "Create a presentation about machine learning basics",
        "style_preferences": {"theme": "professional", "color_scheme": "blue"},
        "status": DeckStatus.PENDING,
    }


@pytest.fixture
def sample_slide_data():
    """Sample slide data for testing."""
    return {
        "title": "Introduction to Machine Learning",
        "content_outline": "Overview of ML concepts, types of learning, and basic algorithms",
        "presenter_notes": "Welcome the audience and provide agenda",
        "template_type": TemplateType.PROFESSIONAL,
        "order": 1,
    }


@pytest.fixture
def sample_deck_plan():
    """Sample LLM-generated deck plan for testing."""
    return {
        "title": "Machine Learning Fundamentals",
        "theme": "professional",
        "slides": [
            {
                "title": "Introduction",
                "content": "Overview of machine learning and its applications",
                "notes": "Welcome and set expectations",
            },
            {
                "title": "Types of Learning",
                "content": "Supervised, unsupervised, and reinforcement learning",
                "notes": "Explain each type with examples",
            },
            {
                "title": "Common Algorithms",
                "content": "Linear regression, decision trees, neural networks",
                "notes": "Focus on practical applications",
            },
        ],
    }


# ---------- API TESTING FIXTURES ----------


@pytest.fixture
def app():
    """FastAPI application instance for testing."""
    from app.main import app

    return app


@pytest.fixture
def client(app):
    """FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(app):
    """Async FastAPI test client for WebSocket and async tests."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
def mock_dependencies(app):
    """Mock all external dependencies for API testing."""
    # Mock LLM client
    mock_llm_client = AsyncMock()
    mock_llm_client.invoke_text.return_value = "Mock LLM response"
    mock_llm_client.invoke_structured.return_value = MagicMock()

    # Mock WebSocket broadcaster
    mock_ws_broadcaster = AsyncMock()

    # Mock ARQ client
    mock_arq_client = AsyncMock()
    mock_arq_client.enqueue.return_value = "job_123"

    # Mock database session
    mock_db_session = AsyncMock()

    # Mock repositories
    mock_deck_repo = AsyncMock()
    mock_slide_repo = AsyncMock()
    mock_event_repo = AsyncMock()

    # Override dependencies in the app
    from app.infra.config.dependencies import (
        get_current_user_id,
        get_llm_client,
        get_websocket_broadcaster,
        get_arq_client,
    )
    from app.infra.config.database import get_db_session

    app.dependency_overrides[get_current_user_id] = (
        lambda: "12345678-1234-5678-9012-123456789012"
    )
    app.dependency_overrides[get_llm_client] = lambda: mock_llm_client
    app.dependency_overrides[get_websocket_broadcaster] = lambda: mock_ws_broadcaster
    app.dependency_overrides[get_arq_client] = lambda: mock_arq_client
    app.dependency_overrides[get_db_session] = lambda: mock_db_session

    yield {
        "llm_client": mock_llm_client,
        "ws_broadcaster": mock_ws_broadcaster,
        "arq_client": mock_arq_client,
        "db_session": mock_db_session,
        "deck_repo": mock_deck_repo,
        "slide_repo": mock_slide_repo,
        "event_repo": mock_event_repo,
    }

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Authentication headers for API requests."""
    return {
        "Authorization": "Bearer test_token_12345",
        "Content-Type": "application/json",
    }


@pytest.fixture
def sample_deck_create_request():
    """Sample deck creation request payload."""
    return {
        "prompt": "Create a presentation about machine learning basics for beginners",
        "style_preferences": {"theme": "professional", "color_scheme": "blue"},
        "template_type": "corporate",
        "slide_count": 8,
        "sources": [
            {
                "kind": "url",
                "url": "https://example.com/ml-guide",
                "title": "ML Beginner Guide",
            },
            {
                "kind": "text",
                "text": "Focus on practical applications and real-world examples",
                "title": "Additional Context",
            },
        ],
    }


@pytest.fixture
def sample_slide_data_api():
    """Sample slide data for API responses."""
    return {
        "id": "slide_123",
        "deck_id": "deck_456",
        "order": 1,
        "title": "Introduction to Machine Learning",
        "content_outline": "Overview of ML concepts, types, and applications",
        "html_content": "<h1>Introduction</h1><p>Machine Learning overview...</p>",
        "presenter_notes": "Welcome audience and introduce key concepts",
        "template_type": "professional",
        "created_at": "2023-12-01T10:00:00Z",
        "updated_at": "2023-12-01T10:30:00Z",
    }


@pytest.fixture
def sample_slide_patch_request():
    """Sample slide patch request payload."""
    return {
        "title": "Updated Slide Title",
        "content_outline": "Updated content outline with more details",
        "presenter_notes": "Updated presenter notes",
        "reason": "user_edit",
    }


# ---------- INTEGRATION/E2E TEST SETUP ----------


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    # Ensure we're in test mode
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["DEBUG"] = "true"

    # Use test database
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_presto_deck.db"

    # Use test Redis (or mock if not available)
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"  # Use DB 1 for tests

    # Cache settings for testing
    os.environ["LLM_CACHE_ENABLED"] = "true"
    os.environ["LLM_CACHE_TYPE"] = "sqlite"
    os.environ["LLM_CACHE_SQLITE_PATH"] = "./test_llm_cache.db"

    # Disable auth for easier testing (can be overridden per test)
    os.environ["DISABLE_AUTH"] = "true"

    yield

    # Cleanup test files
    test_files = ["test_presto_deck.db", "test_llm_cache.db"]
    for file in test_files:
        if Path(file).exists():
            Path(file).unlink()


@pytest.fixture
async def test_db_engine():
    """Create test database engine."""
    from app.infra.config.settings import get_settings
    from app.infra.db.models import Base

    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug_sql,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async with AsyncSession(test_db_engine) as session:
        yield session


@pytest.fixture
async def test_redis_client():
    """Create test Redis client."""
    from app.infra.config.settings import get_settings

    settings = get_settings()
    client = redis.from_url(settings.redis_url)

    try:
        await client.ping()
        yield client
    except redis.ConnectionError:
        pytest.skip("Redis not available for testing")
    finally:
        await client.flushdb()  # Clear test data
        await client.close()


@pytest.fixture
def clean_cache():
    """Provide clean LLM cache for each test."""
    from tests.utils.cache_helpers import clean_llm_cache

    with clean_llm_cache():
        yield


@pytest.fixture
def enable_llm_cache():
    """Enable LLM cache for testing."""
    from app.infra.llm.cache_manager import initialize_llm_cache, clear_llm_cache

    initialize_llm_cache()
    yield
    clear_llm_cache()


# External service check fixtures
@pytest.fixture(scope="session")
def check_redis_available():
    """Check if Redis is available for testing."""
    try:
        client = redis.from_url("redis://localhost:6379/1")
        asyncio.run(client.ping())
        asyncio.run(client.close())
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def check_llm_api_available():
    """Check if LLM API is available (has real API key)."""
    from app.infra.config.settings import get_settings

    settings = get_settings()
    # Only run LLM tests if we have a real API key
    return settings.openai_api_key != "dummy-key-for-test"


@pytest.fixture
def mock_llm_responses():
    """Mock LLM responses for consistent testing."""
    return {
        "deck_plan": {
            "title": "Machine Learning Fundamentals",
            "description": "Introduction to ML concepts and algorithms",
            "target_audience": "Beginner developers",
            "estimated_duration": 45,
            "slides": [
                {
                    "order": 1,
                    "title": "What is Machine Learning?",
                    "content_outline": "Definition and basic concepts",
                    "presenter_notes": "Start with simple, relatable examples",
                }
            ],
        },
        "slide_content": """
        <div class="slide">
            <h1>What is Machine Learning?</h1>
            <div class="content">
                <p>Machine Learning is a subset of AI that enables computers to learn without explicit programming.</p>
                <ul>
                    <li>Supervised Learning</li>
                    <li>Unsupervised Learning</li>
                    <li>Reinforcement Learning</li>
                </ul>
            </div>
        </div>
        """,
    }


# ---------- PYTEST CONFIGURATION ----------


def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Add custom markers if not already present
    markers = [
        "unit: Unit tests (fast, isolated)",
        "integration: Integration tests (slower, with dependencies)",
        "e2e: End-to-end tests (full application flow)",
        "external: Tests requiring external services",
        "llm: Tests that make real LLM API calls",
        "cache: Tests related to LLM caching behavior",
    ]

    for marker in markers:
        config.addinivalue_line("markers", marker)


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        if "external" in item.name or "llm" in item.name:
            item.add_marker(pytest.mark.external)
        if "cache" in item.name:
            item.add_marker(pytest.mark.cache)


# ---------- ASYNC TESTING UTILITIES ----------


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
