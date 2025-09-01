import pytest
import pytest_asyncio
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.config import settings


@pytest_asyncio.fixture
async def test_app():
    """Create test FastAPI application."""
    from app.core import dependencies
    from app.infrastructure.db.database import Database

    # Use fakes for Redis and ARQ to avoid real network access in tests

    # Use in-memory databases for testing
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    settings.redis_url = "redis://localhost:6379/15"  # Not used; faked

    # Initialize test dependencies manually (since TestClient doesn't run lifespan)
    dependencies.database = Database(settings.database_url, echo=False)
    await dependencies.database.initialize()

    # Create tables for test database
    from app.infrastructure.db.models import Base

    async with dependencies.database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    class _FakeRedisInner:
        def __init__(self):
            self._store = {}

        async def xadd(self, *args, **kwargs):
            return "0-1"

        async def publish(self, channel, message):
            return 1

        async def set(self, key, value, ex=None):
            self._store[key] = value
            return True

        async def get(self, key):
            return self._store.get(key)

        async def delete(self, key):
            self._store.pop(key, None)
            return 1

    class _FakeRedisClient:
        def __init__(self):
            self._client = _FakeRedisInner()

        async def initialize(self):
            return None

        async def close(self):
            return None

        async def health_check(self):
            return True

        def get_client(self):
            return self._client

    dependencies.redis_client = _FakeRedisClient()

    # Fake ARQ redis with enqueue_job stub
    class _FakeArq:
        async def enqueue_job(self, *args, **kwargs):
            return None

        async def aclose(self):
            return None

    dependencies.arq_redis = _FakeArq()

    app = create_app()
    yield app

    # Cleanup
    if dependencies.database:
        await dependencies.database.close()
    if dependencies.redis_client:
        await dependencies.redis_client.close()
    if dependencies.arq_redis:
        await dependencies.arq_redis.aclose()


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def auth_headers():
    """Create authorization headers with test JWT token."""
    from app.core.security import security_service

    token = security_service.create_access_token({"sub": "test-user-123"})
    return {"Authorization": f"Bearer {token}"}


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "services" in data
    assert "version" in data


def test_create_deck_endpoint(client, auth_headers):
    """Test deck creation endpoint."""
    deck_data = {
        "title": "Test Presentation",
        "topic": "Testing FastAPI applications",
        "audience": "Developers",
        "style": "technical",
        "slide_count": 5,
        "language": "en",
        "include_speaker_notes": True,
    }

    response = client.post("/api/v1/decks/", json=deck_data, headers=auth_headers)

    if response.status_code != 202:
        print(f"Error response: {response.status_code} - {response.text}")

    assert response.status_code == 202
    data = response.json()
    assert "deck_id" in data
    assert "status" in data
    assert data["status"] == "PENDING"
    assert "message" in data


def test_create_deck_validation_error(client, auth_headers):
    """Test deck creation with invalid data."""
    invalid_data = {
        "title": "",  # Empty title should fail validation
        "topic": "Test topic",
    }

    response = client.post("/api/v1/decks/", json=invalid_data, headers=auth_headers)

    assert response.status_code == 422  # Validation error


def test_create_deck_unauthorized(client):
    """Test deck creation without authentication."""
    deck_data = {
        "title": "Test Presentation",
        "topic": "Testing FastAPI applications",
    }

    response = client.post("/api/v1/decks/", json=deck_data)
    assert response.status_code == 401


def test_get_deck_not_found(client, auth_headers):
    """Test getting non-existent deck."""
    fake_deck_id = str(uuid4())
    response = client.get(f"/api/v1/decks/{fake_deck_id}", headers=auth_headers)
    assert response.status_code == 404


def test_list_decks_endpoint(client, auth_headers):
    """Test listing user's decks."""
    response = client.get("/api/v1/decks/", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)


def test_list_decks_with_pagination(client, auth_headers):
    """Test listing decks with pagination parameters."""
    response = client.get("/api/v1/decks/?limit=5&offset=0", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5


def test_cancel_deck_not_found(client, auth_headers):
    """Test canceling non-existent deck."""
    fake_deck_id = str(uuid4())
    response = client.post(f"/api/v1/decks/{fake_deck_id}/cancel", headers=auth_headers)
    assert response.status_code == 404


def test_get_deck_events_not_found(client, auth_headers):
    """Test getting events for non-existent deck."""
    fake_deck_id = str(uuid4())
    response = client.get(f"/api/v1/decks/{fake_deck_id}/events", headers=auth_headers)
    assert response.status_code == 404


def test_cors_headers(client):
    """Test CORS headers are present."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in (200, 204)
    assert "access-control-allow-origin" in response.headers


def test_invalid_uuid_format(client, auth_headers):
    """Test handling invalid UUID format in URL."""
    response = client.get("/api/v1/decks/invalid-uuid", headers=auth_headers)
    assert response.status_code == 422  # Validation error for invalid UUID


def test_malformed_jwt_token(client):
    """Test handling malformed JWT token."""
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.get("/api/v1/decks/", headers=headers)
    assert response.status_code == 401


def test_missing_authorization_header(client):
    """Test endpoints require authorization header."""
    response = client.get("/api/v1/decks/")
    assert response.status_code == 401
