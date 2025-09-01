"""Global test configuration and fixtures."""

import asyncio
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Dict, Any
from uuid import uuid4
from datetime import timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, Mock

# Set test environment
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["OPENAI_API_KEY"] = "test-openai-key"

from app.core.security import security_service
from app.domain.entities import Deck, DeckStatus, Slide, DeckEvent
from app.infrastructure.db.models import Base


# Pytest configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Database fixtures
@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing."""
    async_session = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


# Authentication fixtures
@pytest.fixture
def test_user_id() -> str:
    """Test user ID."""
    return "test-user-123"


@pytest.fixture
def another_user_id() -> str:
    """Another test user ID for authorization tests."""
    return "other-user-456"


@pytest.fixture
def jwt_token(test_user_id: str) -> str:
    """Valid JWT token for testing."""
    return security_service.create_access_token(
        data={"sub": test_user_id}, expires_delta=timedelta(hours=1)
    )


@pytest.fixture
def expired_jwt_token(test_user_id: str) -> str:
    """Expired JWT token for testing."""
    return security_service.create_access_token(
        data={"sub": test_user_id},
        expires_delta=timedelta(seconds=-1),  # Already expired
    )


@pytest.fixture
def auth_headers(jwt_token: str) -> Dict[str, str]:
    """Authorization headers for API requests."""
    return {"Authorization": f"Bearer {jwt_token}"}


# Domain entity fixtures
@pytest.fixture
def sample_deck(test_user_id: str) -> Deck:
    """Sample deck entity for testing."""
    return Deck(
        id=uuid4(),
        user_id=test_user_id,
        title="Test Presentation",
        status=DeckStatus.PENDING,
    )


@pytest.fixture
def completed_deck(test_user_id: str) -> Deck:
    """Completed deck entity for testing."""
    deck = Deck(
        id=uuid4(),
        user_id=test_user_id,
        title="Completed Presentation",
        status=DeckStatus.COMPLETED,
    )
    deck.deck_plan = {
        "title": "Completed Presentation",
        "slides": [
            {"slide_number": 1, "title": "Introduction"},
            {"slide_number": 2, "title": "Content"},
        ],
        "total_slides": 2,
    }
    return deck


@pytest.fixture
def sample_slide(sample_deck: Deck) -> Slide:
    """Sample slide entity for testing."""
    return Slide(
        id=uuid4(),
        deck_id=sample_deck.id,
        slide_order=1,
        html_content="<h1>Test Slide</h1><p>Content</p>",
        presenter_notes="Test presenter notes",
    )


@pytest.fixture
def sample_deck_event(sample_deck: Deck) -> DeckEvent:
    """Sample deck event for testing."""
    return DeckEvent(
        deck_id=sample_deck.id,
        version=1,
        event_type="DeckStarted",
        payload={"title": sample_deck.title},
    )


# Mock fixtures
@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    mock = Mock()
    mock.generate_deck_plan = AsyncMock()
    mock.generate_slide_content = AsyncMock()
    mock.update_slide_content = AsyncMock()
    return mock


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    mock = Mock()
    mock.initialize = AsyncMock()
    mock.close = AsyncMock()
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_stream_publisher():
    """Mock Redis stream publisher for testing."""
    mock = Mock()
    mock.publish_event = AsyncMock()
    return mock


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager for testing."""
    mock = Mock()
    mock.set_cancellation_flag = AsyncMock()
    mock.check_cancellation_flag = AsyncMock(return_value=False)
    mock.clear_cancellation_flag = AsyncMock()
    return mock


@pytest.fixture
def mock_arq_redis():
    """Mock ARQ Redis client for testing."""
    mock = Mock()
    mock.enqueue_job = AsyncMock()
    mock.close = AsyncMock()
    return mock


# API testing fixtures
@pytest.fixture
def deck_creation_request() -> Dict[str, Any]:
    """Valid deck creation request data."""
    return {
        "title": "Test Presentation",
        "topic": "How to test applications effectively",
        "audience": "Developers",
        "style": "technical",
        "slide_count": 5,
        "language": "en",
        "include_speaker_notes": True,
    }


@pytest.fixture
def invalid_deck_creation_request() -> Dict[str, Any]:
    """Invalid deck creation request data for validation testing."""
    return {
        "title": "",  # Empty title should fail validation
        "topic": "",  # Empty topic should fail validation
        "slide_count": 100,  # Too many slides
    }


# WebSocket testing fixtures
@pytest.fixture
def websocket_message() -> Dict[str, Any]:
    """Sample WebSocket message for testing."""
    return {
        "type": "update_slide",
        "data": {"slide_id": str(uuid4()), "prompt": "Make this slide more engaging"},
    }


# Test data factories
class TestDataFactory:
    """Factory for creating test data."""

    @staticmethod
    def create_deck(user_id: str = "test-user", **kwargs) -> Deck:
        """Create a test deck with optional overrides."""
        defaults = {
            "id": uuid4(),
            "user_id": user_id,
            "title": "Factory Test Deck",
            "status": DeckStatus.PENDING,
        }
        defaults.update(kwargs)
        return Deck(**defaults)

    @staticmethod
    def create_slide(deck_id, slide_order: int = 1, **kwargs) -> Slide:
        """Create a test slide with optional overrides."""
        defaults = {
            "id": uuid4(),
            "deck_id": deck_id,
            "slide_order": slide_order,
            "html_content": f"<h1>Test Slide {slide_order}</h1>",
            "presenter_notes": f"Notes for slide {slide_order}",
        }
        defaults.update(kwargs)
        return Slide(**defaults)

    @staticmethod
    def create_event(deck_id, version: int = 1, **kwargs) -> DeckEvent:
        """Create a test event with optional overrides."""
        defaults = {
            "deck_id": deck_id,
            "version": version,
            "event_type": "TestEvent",
            "payload": {"test": True},
        }
        defaults.update(kwargs)
        return DeckEvent(**defaults)


@pytest.fixture
def test_factory():
    """Test data factory fixture."""
    return TestDataFactory


# Async context managers for testing
@pytest_asyncio.fixture
async def async_mock_context():
    """Async context manager mock for testing."""

    async def mock_context_manager(*args, **kwargs):
        yield Mock()

    return mock_context_manager


# Performance testing fixtures
@pytest.fixture
def performance_test_data():
    """Data for performance testing."""
    return {
        "concurrent_users": 100,
        "requests_per_user": 10,
        "test_duration": 30,  # seconds
    }


# Error simulation fixtures
@pytest.fixture
def database_error():
    """Database error for testing error handling."""
    return Exception("Database connection failed")


@pytest.fixture
def redis_error():
    """Redis error for testing error handling."""
    return Exception("Redis connection failed")


@pytest.fixture
def llm_error():
    """LLM error for testing error handling."""
    return Exception("OpenAI API rate limit exceeded")


# Cleanup fixtures
@pytest.fixture(autouse=True)
async def cleanup_test_environment():
    """Cleanup test environment after each test."""
    yield
    # Cleanup code here if needed
    pass
