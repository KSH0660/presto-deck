"""
Pytest configuration and fixtures.
"""

import pytest
import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

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


# ---------- INTEGRATION TEST FIXTURES ----------


@pytest.fixture(scope="session")
def test_database():
    """Set up test database for integration tests."""
    # This would create a test database
    # For now, just return None to avoid errors
    return None


@pytest.fixture
def test_redis():
    """Set up test Redis for integration tests."""
    # This would set up Redis connection for testing
    return None


# ---------- ASYNC TESTING UTILITIES ----------


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
